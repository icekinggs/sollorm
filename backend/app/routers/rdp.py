import asyncio

from fastapi import Query, WebSocket, status
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Agent, User
from app.security import decode_access_token


# ─── Guacamole protocol ───────────────────────────────────────────────────────

def _encode(*args) -> bytes:
    return (",".join(f"{len(str(a))}.{a}" for a in args) + ";").encode()


def _parse(raw: str) -> list[str]:
    parts, data = [], raw.rstrip(";")
    while data:
        try:
            dot = data.index(".")
            length = int(data[:dot])
            value = data[dot + 1: dot + 1 + length]
            parts.append(value)
            tail = data[dot + 1 + length:]
            data = tail[1:] if tail.startswith(",") else ""
        except (ValueError, IndexError):
            break
    return parts


class _Guacd:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._r = reader
        self._w = writer
        self._buf = ""

    async def send(self, *args) -> None:
        self._w.write(_encode(*args))
        await self._w.drain()

    async def recv(self) -> list[str]:
        while ";" not in self._buf:
            chunk = await asyncio.wait_for(self._r.read(4096), timeout=15)
            if not chunk:
                raise ConnectionError("guacd fechou a conexão")
            self._buf += chunk.decode("utf-8", errors="replace")
        instr, _, self._buf = self._buf.partition(";")
        return _parse(instr)

    def drain_buf(self) -> str:
        data, self._buf = self._buf, ""
        return data

    async def close(self) -> None:
        try:
            self._w.close()
            await self._w.wait_closed()
        except Exception:
            pass


_RDP_DEFAULTS = {
    "ignore-cert": "true",
    "security": "any",
    "color-depth": "32",
    "dpi": "96",
    "resize-method": "reconnect",
    "enable-font-smoothing": "true",
    "enable-wallpaper": "false",
    "enable-theming": "true",
}


async def _handshake(
    guacd: _Guacd,
    host: str,
    port: int,
    username: str,
    password: str,
    domain: str,
    width: int,
    height: int,
) -> None:
    await guacd.send("select", "rdp")

    args_instr = await guacd.recv()
    if not args_instr or args_instr[0] != "args":
        raise RuntimeError(f"guacd retornou inesperado: {args_instr}")

    value_map = {
        "hostname": host,
        "port": str(port),
        "username": username,
        "password": password,
        "domain": domain,
        "width": str(width),
        "height": str(height),
        **_RDP_DEFAULTS,
    }
    values = [value_map.get(p, "") for p in args_instr[1:]]
    await guacd.send("connect", *values)

    ready = await guacd.recv()
    if not ready or ready[0] != "ready":
        raise RuntimeError(f"guacd não enviou ready: {ready}")


# ─── WebSocket endpoint ───────────────────────────────────────────────────────

async def rdp_websocket(
    websocket: WebSocket,
    agent_id: str,
    token: str = Query(...),
    host: str = Query(""),
    port: int = Query(3389),
    username: str = Query(""),
    password: str = Query(""),
    domain: str = Query(""),
    width: int = Query(1280),
    height: int = Query(720),
):
    # Auth
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    async with AsyncSessionLocal() as db:
        user_res = await db.execute(select(User).where(User.id == payload["sub"]))
        user = user_res.scalar_one_or_none()
        if user is None or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if not host:
            agent_res = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = agent_res.scalar_one_or_none()
            if agent:
                host = agent.last_ip or agent.hostname or ""

    if not host:
        await websocket.close(code=4004)
        return

    # Connect to guacd
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(settings.guacd_host, settings.guacd_port),
            timeout=5,
        )
    except (OSError, asyncio.TimeoutError):
        await websocket.close(code=4002)
        return

    guacd = _Guacd(reader, writer)
    try:
        await _handshake(guacd, host, port, username, password, domain, width, height)
    except Exception:
        await guacd.close()
        await websocket.close(code=4003)
        return

    await websocket.accept(subprotocol="guacamole")

    leftover = guacd.drain_buf()

    async def browser_to_guacd():
        try:
            while True:
                data = await websocket.receive_text()
                writer.write(data.encode())
                await writer.drain()
        except (WebSocketDisconnect, RuntimeError):
            pass

    async def guacd_to_browser():
        try:
            if leftover:
                await websocket.send_text(leftover)
            while True:
                chunk = await reader.read(8192)
                if not chunk:
                    break
                await websocket.send_text(chunk.decode("utf-8", errors="replace"))
        except (WebSocketDisconnect, RuntimeError):
            pass

    try:
        await asyncio.gather(browser_to_guacd(), guacd_to_browser())
    finally:
        await guacd.close()
        try:
            await websocket.close()
        except Exception:
            pass
