from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, verify_agent_token
from app.database import get_db
from app.models import Agent, Heartbeat, User
from app.schemas import (
    AgentOut,
    HeartbeatIn,
    HeartbeatOut,
    StatusResponse,
    SystemInfoIn,
)

router = APIRouter(prefix="/agents", tags=["agents"])

ONLINE_THRESHOLD_SECONDS = 120


def _build_agent_out(agent: Agent, now: datetime) -> AgentOut:
    """Constrói AgentOut com is_online calculado, lidando com timezone."""
    threshold = now - timedelta(seconds=ONLINE_THRESHOLD_SECONDS)

    last_seen_aware = agent.last_seen
    if last_seen_aware is not None and last_seen_aware.tzinfo is None:
        last_seen_aware = last_seen_aware.replace(tzinfo=timezone.utc)

    agent_dict = AgentOut.model_validate(agent).model_dump()
    agent_dict["is_online"] = (
        last_seen_aware is not None and last_seen_aware > threshold
    )
    return AgentOut(**agent_dict)


@router.post("/system-info", response_model=StatusResponse)
async def receive_system_info(
    payload: SystemInfoIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_agent_token),
):
    """Recebe info completa de hardware/SO do agente."""
    now = datetime.now(timezone.utc)

    result = await db.execute(select(Agent).where(Agent.id == payload.agent_id))
    agent = result.scalar_one_or_none()

    if agent is None:
        agent = Agent(id=payload.agent_id)
        db.add(agent)

    agent.hostname = payload.hostname
    agent.os = payload.os
    agent.platform = payload.platform
    agent.architecture = payload.architecture
    agent.kernel_arch = payload.kernel_arch
    agent.cpu_model = payload.cpu_model
    agent.cpu_cores = payload.cpu_cores
    agent.ram_total_bytes = payload.ram_total_bytes
    agent.disk_total_bytes = payload.disk_total_bytes
    agent.agent_version = payload.agent_version
    agent.last_system_info = now
    agent.last_seen = now

    await db.commit()
    return StatusResponse(message=f"Agente {agent.hostname} atualizado")


@router.post("/heartbeat", response_model=StatusResponse)
async def receive_heartbeat(
    payload: HeartbeatIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_agent_token),
):
    """Recebe heartbeat com métricas atuais do agente."""
    now = datetime.now(timezone.utc)

    result = await db.execute(select(Agent).where(Agent.id == payload.agent_id))
    agent = result.scalar_one_or_none()

    if agent is None:
        agent = Agent(id=payload.agent_id, hostname=payload.hostname)
        db.add(agent)

    agent.last_seen = now
    if not agent.hostname:
        agent.hostname = payload.hostname

    heartbeat = Heartbeat(
        agent_id=payload.agent_id,
        cpu_usage_percent=payload.cpu_usage_percent,
        ram_usage_percent=payload.ram_usage_percent,
        disk_usage_percent=payload.disk_usage_percent,
        uptime_seconds=payload.uptime_seconds,
        reported_at=payload.timestamp,
    )
    db.add(heartbeat)

    await db.commit()
    return StatusResponse(message="heartbeat recebido")


@router.get("", response_model=list[AgentOut])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista todos os agentes registrados. Requer login."""
    result = await db.execute(select(Agent).order_by(Agent.hostname))
    agents = result.scalars().all()
    now = datetime.now(timezone.utc)

    return [_build_agent_out(agent, now) for agent in agents]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna detalhes de um agente específico. Requer login."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado"
        )

    return _build_agent_out(agent, datetime.now(timezone.utc))


@router.get("/{agent_id}/heartbeats", response_model=list[HeartbeatOut])
async def get_agent_heartbeats(
    agent_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna os últimos heartbeats de um agente. Requer login."""
    result = await db.execute(
        select(Heartbeat)
        .where(Heartbeat.agent_id == agent_id)
        .order_by(Heartbeat.received_at.desc())
        .limit(min(limit, 1000))
    )
    return list(result.scalars().all())
