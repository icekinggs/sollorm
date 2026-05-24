import asyncio

from fastapi import Query, WebSocket, status
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.database import AsyncSessionLocal
from app.models import User
from app.security import decode_access_token

_connections: list[WebSocket] = []
_lock = asyncio.Lock()


async def broadcast(event: dict) -> None:
    async with _lock:
        conns = list(_connections)
    dead: list[WebSocket] = []
    for ws in conns:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    if dead:
        async with _lock:
            for ws in dead:
                try:
                    _connections.remove(ws)
                except ValueError:
                    pass


async def notifications_websocket(websocket: WebSocket, token: str = Query(...)):
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
    async with _lock:
        _connections.append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        async with _lock:
            try:
                _connections.remove(websocket)
            except ValueError:
                pass
