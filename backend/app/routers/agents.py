from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_agent_token
from app.database import get_db
from app.models import Agent, Heartbeat
from app.schemas import (
    AgentOut,
    HeartbeatIn,
    HeartbeatOut,
    StatusResponse,
    SystemInfoIn,
)

router = APIRouter(prefix="/agents", tags=["agents"])

# Janela em segundos para considerar um agente "online"
ONLINE_THRESHOLD_SECONDS = 120


@router.post("/system-info", response_model=StatusResponse)
async def receive_system_info(
    payload: SystemInfoIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_agent_token),
):
    """Recebe info completa de hardware/SO do agente."""
    now = datetime.now(timezone.utc)

    # Procura agente existente ou cria novo
    result = await db.execute(select(Agent).where(Agent.id == payload.agent_id))
    agent = result.scalar_one_or_none()

    if agent is None:
        agent = Agent(id=payload.agent_id)
        db.add(agent)

    # Atualiza todos os campos
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

    # Verifica se o agente existe (deveria, mas vamos ser tolerantes)
    result = await db.execute(select(Agent).where(Agent.id == payload.agent_id))
    agent = result.scalar_one_or_none()

    if agent is None:
        # Cria agente "stub" com hostname só - próximo system-info preenche o resto
        agent = Agent(id=payload.agent_id, hostname=payload.hostname)
        db.add(agent)

    # Atualiza last_seen do agente
    agent.last_seen = now
    if not agent.hostname:
        agent.hostname = payload.hostname

    # Cria registro de heartbeat
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
async def list_agents(db: AsyncSession = Depends(get_db)):
    """Lista todos os agentes registrados."""
    result = await db.execute(select(Agent).order_by(Agent.hostname))
    agents = result.scalars().all()

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(seconds=ONLINE_THRESHOLD_SECONDS)

    output = []
    for agent in agents:
        agent_dict = AgentOut.model_validate(agent).model_dump()
        agent_dict["is_online"] = (
            agent.last_seen is not None and agent.last_seen > threshold
        )
        output.append(AgentOut(**agent_dict))

    return output


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Retorna detalhes de um agente específico."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado"
        )

    now = datetime.now(timezone.utc)
    threshold = now - timedelta(seconds=ONLINE_THRESHOLD_SECONDS)

    agent_dict = AgentOut.model_validate(agent).model_dump()
    agent_dict["is_online"] = (
        agent.last_seen is not None and agent.last_seen > threshold
    )

    return AgentOut(**agent_dict)


@router.get("/{agent_id}/heartbeats", response_model=list[HeartbeatOut])
async def get_agent_heartbeats(
    agent_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Retorna os últimos heartbeats de um agente (mais recentes primeiro)."""
    result = await db.execute(
        select(Heartbeat)
        .where(Heartbeat.agent_id == agent_id)
        .order_by(Heartbeat.received_at.desc())
        .limit(min(limit, 1000))
    )
    return list(result.scalars().all())
