from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import AgentAuthResult, get_current_user, verify_agent_token
from app.config import settings
from app.database import get_db
from app.models import Agent, AgentToken, Heartbeat, User
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
    threshold = now - timedelta(seconds=ONLINE_THRESHOLD_SECONDS)

    last_seen_aware = agent.last_seen
    if last_seen_aware is not None and last_seen_aware.tzinfo is None:
        last_seen_aware = last_seen_aware.replace(tzinfo=timezone.utc)

    is_online = last_seen_aware is not None and last_seen_aware > threshold

    token_name = None
    token_prefix = None
    if agent.token is not None:
        token_name = agent.token.name
        token_prefix = agent.token.token_prefix

    return AgentOut(
        id=agent.id,
        hostname=agent.hostname,
        os=agent.os,
        platform=agent.platform,
        cpu_model=agent.cpu_model,
        cpu_cores=agent.cpu_cores,
        ram_total_bytes=agent.ram_total_bytes,
        disk_total_bytes=agent.disk_total_bytes,
        agent_version=agent.agent_version,
        first_seen=agent.first_seen,
        last_seen=agent.last_seen,
        is_online=is_online,
        token_name=token_name,
        token_prefix=token_prefix,
        remote_access_url=settings.meshcentral_public_url.rstrip("/") or None,
    )


async def _link_token_to_agent(
    db: AsyncSession, auth: AgentAuthResult, agent: Agent
) -> None:
    if auth.is_legacy or auth.agent_token is None:
        return

    if auth.agent_token.agent_id is None:
        auth.agent_token.agent_id = agent.id


@router.post("/system-info", response_model=StatusResponse)
async def receive_system_info(
    payload: SystemInfoIn,
    db: AsyncSession = Depends(get_db),
    auth: AgentAuthResult = Depends(verify_agent_token),
):
    now = datetime.now(timezone.utc)

    result = await db.execute(select(Agent).where(Agent.id == payload.agent_id))
    agent = result.scalar_one_or_none()

    if agent is None:
        agent = Agent(
            id=payload.agent_id,
            hostname=payload.hostname,
            os=payload.os,
            platform=payload.platform,
            architecture=payload.architecture,
            kernel_arch=payload.kernel_arch,
            cpu_model=payload.cpu_model,
            cpu_cores=payload.cpu_cores,
            ram_total_bytes=payload.ram_total_bytes,
            disk_total_bytes=payload.disk_total_bytes,
            agent_version=payload.agent_version,
            last_system_info=now,
            last_seen=now,
        )
        db.add(agent)
        await db.flush()
    else:
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

    await _link_token_to_agent(db, auth, agent)
    await db.commit()
    return StatusResponse(message=f"Agente {agent.hostname} atualizado")


@router.post("/heartbeat", response_model=StatusResponse)
async def receive_heartbeat(
    payload: HeartbeatIn,
    db: AsyncSession = Depends(get_db),
    auth: AgentAuthResult = Depends(verify_agent_token),
):
    now = datetime.now(timezone.utc)

    result = await db.execute(select(Agent).where(Agent.id == payload.agent_id))
    agent = result.scalar_one_or_none()

    if agent is None:
        agent = Agent(id=payload.agent_id, hostname=payload.hostname)
        db.add(agent)
        await db.flush()

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

    await _link_token_to_agent(db, auth, agent)
    await db.commit()
    return StatusResponse(message="heartbeat recebido")


@router.get("", response_model=list[AgentOut])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Agent).options(selectinload(Agent.token)).order_by(Agent.hostname)
    )
    agents = result.scalars().all()
    now = datetime.now(timezone.utc)
    return [_build_agent_out(agent, now) for agent in agents]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Agent).options(selectinload(Agent.token)).where(Agent.id == agent_id)
    )
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
    result = await db.execute(
        select(Heartbeat)
        .where(Heartbeat.agent_id == agent_id)
        .order_by(Heartbeat.received_at.desc())
        .limit(min(limit, 1000))
    )
    return list(result.scalars().all())

@router.delete("/{agent_id}", response_model=StatusResponse)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    result = await db.execute(
        select(Agent).options(selectinload(Agent.token)).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente não encontrado",
        )

    hostname = agent.hostname
    token_to_delete = agent.token

    if token_to_delete is not None:
        await db.delete(token_to_delete)

    await db.delete(agent)

    await db.commit()
    return StatusResponse(message=f"Agente '{hostname}' apagado")
