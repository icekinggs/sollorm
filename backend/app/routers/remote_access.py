import asyncio

import asyncssh
from fastapi import Query, WebSocket, status
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Agent, User
from app.security import decode_access_token


async def _authenticate_websocket(websocket: WebSocket, token: str) -> User | None:
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
        return user


async def ssh_websocket(websocket: WebSocket, agent_id: str, token: str = Query(...)):
    user = await _authenticate_websocket(websocket, token)
    if user is None:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await websocket.accept()

    try:
        init = await asyncio.wait_for(websocket.receive_json(), timeout=30)
        if init.get("type") != "connect":
            await websocket.send_json({"type": "error", "message": "Mensagem inicial inválida"})
            return

        host = str(init.get("host") or "").strip()
        username = str(init.get("username") or "").strip()
        password = str(init.get("password") or "")
        port = int(init.get("port") or 22)

        if not host or not username:
            await websocket.send_json({"type": "error", "message": "Host e usuário são obrigatórios"})
            return

        async with asyncssh.connect(
            host,
            port=port,
            username=username,
            password=password or None,
            known_hosts=None,
        ) as conn:
            process = await conn.create_process(
                term_type="xterm",
                term_size=(120, 32),
            )
            await websocket.send_json({"type": "connected"})

            async def read_output():
                while not process.stdout.at_eof():
                    data = await process.stdout.read(1024)
                    if data:
                        await websocket.send_json({"type": "output", "data": data})

            async def read_input():
                while True:
                    message = await websocket.receive_json()
                    message_type = message.get("type")
                    if message_type == "input":
                        process.stdin.write(str(message.get("data") or ""))
                    elif message_type == "disconnect":
                        process.stdin.write("exit\n")
                        break

            output_task = asyncio.create_task(read_output())
            input_task = asyncio.create_task(read_input())
            done, pending = await asyncio.wait(
                {output_task, input_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
    except (asyncssh.Error, OSError) as exc:
        await websocket.send_json({"type": "error", "message": f"Falha SSH: {exc}"})
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "Tempo esgotado aguardando credenciais SSH"})
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": f"Sessão encerrada: {exc}"})
