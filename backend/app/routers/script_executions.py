from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models import Agent, PatchItem, PatchScan, ScriptExecution, User
from app.auth import get_current_user
from app.schemas import ScriptExecutionCreate, ScriptExecutionOut
from app.services.tokens import find_valid_token, mark_token_used

router = APIRouter(tags=["script-executions"])


class AgentConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, agent_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        old_socket = self._connections.get(agent_id)
        if old_socket is not None:
            await old_socket.close(code=4000, reason="Nova conexão do agente")
        self._connections[agent_id] = websocket

    def disconnect(self, agent_id: str, websocket: WebSocket) -> None:
        if self._connections.get(agent_id) is websocket:
            self._connections.pop(agent_id, None)

    def is_connected(self, agent_id: str) -> bool:
        return agent_id in self._connections

    async def send_command(self, agent_id: str, command: dict) -> bool:
        websocket = self._connections.get(agent_id)
        if websocket is None:
            return False
        try:
            await websocket.send_json(command)
            return True
        except RuntimeError:
            self._connections.pop(agent_id, None)
            return False

    async def send_execution(self, agent_id: str, execution: ScriptExecution) -> bool:
        websocket = self._connections.get(agent_id)
        if websocket is None:
            return False

        try:
            await websocket.send_json(
                {
                    "type": "run_script",
                    "execution_id": execution.id,
                    "language": execution.language,
                    "script": execution.script,
                    "timeout_seconds": execution.timeout_seconds,
                }
            )
            return True
        except RuntimeError:
            self._connections.pop(agent_id, None)
            return False


manager = AgentConnectionManager()


async def _authenticate_agent_ws(
    websocket: WebSocket,
    agent_id: str,
    token: str,
    db: AsyncSession,
) -> bool:
    if token.startswith("sollo_"):
        agent_token = await find_valid_token(db, token)
        if agent_token is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False

        if agent_token.agent_id is not None and agent_token.agent_id != agent_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False

        if agent_token.agent_id is None:
            agent_token.agent_id = agent_id
        await mark_token_used(db, agent_token)
        await db.commit()
        return True

    if settings.allow_legacy_master_token and token == settings.agent_master_token:
        return True

    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return False


async def _mark_execution_running(db: AsyncSession, execution_id: str) -> None:
    result = await db.execute(
        select(ScriptExecution).where(ScriptExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        return
    execution.status = "running"
    execution.started_at = datetime.now(timezone.utc)
    await db.commit()


async def _finish_execution(db: AsyncSession, payload: dict) -> None:
    execution_id = payload.get("execution_id")
    if not execution_id:
        return

    result = await db.execute(
        select(ScriptExecution).where(ScriptExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        return

    status_value = payload.get("status") or "failed"
    if status_value not in {"succeeded", "failed", "timed_out"}:
        status_value = "failed"

    execution.status = status_value
    execution.stdout = payload.get("stdout")
    execution.stderr = payload.get("stderr")
    execution.exit_code = payload.get("exit_code")
    execution.error_message = payload.get("error_message")
    execution.finished_at = datetime.now(timezone.utc)
    await db.commit()


async def _send_queued_executions(agent_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScriptExecution)
            .where(ScriptExecution.agent_id == agent_id)
            .where(ScriptExecution.status.in_(["pending", "queued"]))
            .order_by(ScriptExecution.created_at)
            .limit(20)
        )
        executions = result.scalars().all()
        for execution in executions:
            sent = await manager.send_execution(agent_id, execution)
            if sent:
                execution.status = "pending"
                execution.error_message = None
        await db.commit()


@router.websocket("/agent-ws/{agent_id}")
async def agent_websocket(
    websocket: WebSocket,
    agent_id: str,
    token: str = Query(...),
):
    async with AsyncSessionLocal() as db:
        authenticated = await _authenticate_agent_ws(websocket, agent_id, token, db)
        if not authenticated:
            return

    await manager.connect(agent_id, websocket)
    await _send_queued_executions(agent_id)
    try:
        while True:
            payload = await websocket.receive_json()
            message_type = payload.get("type")
            async with AsyncSessionLocal() as db:
                if message_type == "script_started":
                    await _mark_execution_running(db, payload.get("execution_id", ""))
                elif message_type == "script_result":
                    await _finish_execution(db, payload)
                elif message_type == "patch_scan_result":
                    await _handle_patch_scan_result(db, payload)
                elif message_type == "patch_install_result":
                    await _handle_patch_install_result(db, payload)
    except WebSocketDisconnect:
        manager.disconnect(agent_id, websocket)


@router.post(
    "/agents/{agent_id}/executions",
    response_model=ScriptExecutionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_script_execution(
    agent_id: str,
    payload: ScriptExecutionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente não encontrado",
        )

    execution = ScriptExecution(
        agent_id=agent_id,
        created_by_user_id=current_user.id,
        language=payload.language,
        script=payload.script,
        timeout_seconds=payload.timeout_seconds,
        status="pending",
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    sent = await manager.send_execution(agent_id, execution)
    if not sent:
        execution.status = "queued"
        execution.error_message = "Agente não está conectado ao canal de comandos"
        await db.commit()
        await db.refresh(execution)

    return execution


@router.get("/agents/{agent_id}/executions", response_model=list[ScriptExecutionOut])
async def list_script_executions(
    agent_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ScriptExecution)
        .where(ScriptExecution.agent_id == agent_id)
        .order_by(ScriptExecution.created_at.desc())
        .limit(min(limit, 200))
    )
    return list(result.scalars().all())


# ─── Patch WebSocket handlers ─────────────────────────────────────────────────

async def _handle_patch_scan_result(db: AsyncSession, payload: dict) -> None:
    scan_id = payload.get("scan_id")
    if not scan_id:
        return

    result = await db.execute(select(PatchScan).where(PatchScan.id == scan_id))
    scan = result.scalar_one_or_none()
    if scan is None:
        return

    error = payload.get("error")
    if error:
        scan.status = "error"
        scan.error_message = str(error)
        scan.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return

    raw_patches = payload.get("patches") or []

    # Remove itens anteriores do mesmo scan (re-scan)
    await db.execute(delete(PatchItem).where(PatchItem.scan_id == scan_id))

    for p in raw_patches:
        db.add(PatchItem(
            scan_id=scan_id,
            agent_id=scan.agent_id,
            name=str(p.get("name") or ""),
            current_version=p.get("current_version") or None,
            available_version=p.get("available_version") or None,
            severity=p.get("severity") or "unknown",
            source=p.get("source") or None,
        ))

    scan.status = "done"
    scan.patch_count = len(raw_patches)
    scan.completed_at = datetime.now(timezone.utc)
    await db.commit()


async def _handle_patch_install_result(db: AsyncSession, payload: dict) -> None:
    installed = payload.get("installed") or []
    scan_id = payload.get("scan_id")
    if not installed or not scan_id:
        return

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PatchItem)
        .where(PatchItem.scan_id == scan_id)
        .where(PatchItem.name.in_(installed))
    )
    for item in result.scalars().all():
        item.installed = True
        item.installed_at = now

    await db.commit()
