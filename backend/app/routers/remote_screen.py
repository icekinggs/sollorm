import asyncio
from typing import Dict, List

from fastapi import Query, WebSocket, status
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.database import AsyncSessionLocal
from app.models import User
from app.security import decode_access_token

# ─── Frame distribution ───────────────────────────────────────────────────────
# Maps agent_id → list of asyncio.Queue objects (one per connected browser viewer)

_viewers: Dict[str, List[asyncio.Queue]] = {}
_viewers_lock = asyncio.Lock()


async def _add_viewer(agent_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=3)
    async with _viewers_lock:
        _viewers.setdefault(agent_id, []).append(q)
    return q


async def _remove_viewer(agent_id: str, q: asyncio.Queue) -> None:
    async with _viewers_lock:
        lst = _viewers.get(agent_id, [])
        try:
            lst.remove(q)
        except ValueError:
            pass
        if not lst:
            _viewers.pop(agent_id, None)


async def _has_viewers(agent_id: str) -> bool:
    async with _viewers_lock:
        return bool(_viewers.get(agent_id))


async def dispatch_frame(agent_id: str, payload: dict) -> None:
    """Called by the agent WebSocket loop when a remote_frame arrives."""
    async with _viewers_lock:
        queues = list(_viewers.get(agent_id, []))
    for q in queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass  # drop frame — viewer is lagging


# ─── WebSocket endpoint ───────────────────────────────────────────────────────

async def remote_screen_websocket(
    websocket: WebSocket,
    agent_id: str,
    token: str = Query(...),
    fps: int = Query(10),
    quality: int = Query(65),
):
    # JWT auth
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.id == payload["sub"]))
        user = res.scalar_one_or_none()
        if user is None or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await websocket.accept()

    # Tell agent to start capture
    from app.routers.script_executions import manager  # lazy to avoid circular import

    started = await manager.send_command(agent_id, {
        "type": "start_remote",
        "fps": max(1, min(fps, 30)),
        "quality": max(10, min(quality, 90)),
    })
    if not started:
        await websocket.send_json({"type": "error", "message": "Agente não está conectado"})
        try:
            await websocket.close()
        except Exception:
            pass
        return

    q = await _add_viewer(agent_id)

    async def send_frames():
        try:
            while True:
                frame = await q.get()
                await websocket.send_json(frame)
        except (WebSocketDisconnect, RuntimeError):
            pass

    async def receive_commands():
        try:
            while True:
                msg = await websocket.receive_json()
                if msg.get("type") in ("remote_mouse", "remote_key"):
                    await manager.send_command(agent_id, msg)
        except (WebSocketDisconnect, RuntimeError):
            pass

    try:
        await asyncio.gather(send_frames(), receive_commands())
    finally:
        await _remove_viewer(agent_id, q)
        # Stop capture if no more viewers
        if not await _has_viewers(agent_id):
            await manager.send_command(agent_id, {"type": "stop_remote"})
        try:
            await websocket.close()
        except Exception:
            pass
