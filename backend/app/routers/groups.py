from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Agent, Group, User
from app.schemas import AgentGroupAssign, AgentOut, GroupCreate, GroupOut, GroupUpdate

router = APIRouter(tags=["groups"])


def _build_agent_out(agent: Agent) -> AgentOut:
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
        last_ip=agent.last_ip,
        group_id=agent.group_id,
        group_name=agent.group.name if agent.group else None,
    )


@router.get("/groups", response_model=list[GroupOut])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Group).order_by(Group.name))
    groups = result.scalars().all()

    # Count agents per group in one query
    counts_result = await db.execute(
        select(Agent.group_id, func.count(Agent.id))
        .where(Agent.group_id.isnot(None))
        .group_by(Agent.group_id)
    )
    counts = {row[0]: row[1] for row in counts_result}

    out = []
    for g in groups:
        out.append(GroupOut(
            id=g.id,
            name=g.name,
            color=g.color,
            created_at=g.created_at,
            agent_count=counts.get(g.id, 0),
        ))
    return out


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = Group(
        name=payload.name,
        color=payload.color,
        created_by_user_id=current_user.id,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return GroupOut(id=group.id, name=group.name, color=group.color, created_at=group.created_at, agent_count=0)


@router.put("/groups/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: str,
    payload: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")

    if payload.name is not None:
        group.name = payload.name
    if payload.color is not None:
        group.color = payload.color

    await db.commit()
    await db.refresh(group)

    count_result = await db.execute(
        select(func.count(Agent.id)).where(Agent.group_id == group_id)
    )
    count = count_result.scalar() or 0
    return GroupOut(id=group.id, name=group.name, color=group.color, created_at=group.created_at, agent_count=count)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    await db.delete(group)
    await db.commit()


@router.put("/agents/{agent_id}/group", response_model=AgentOut)
async def assign_agent_group(
    agent_id: str,
    payload: AgentGroupAssign,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado")

    if payload.group_id is not None:
        grp_result = await db.execute(select(Group).where(Group.id == payload.group_id))
        grp = grp_result.scalar_one_or_none()
        if grp is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
        agent.group_id = payload.group_id
        agent.group = grp
    else:
        agent.group_id = None
        agent.group = None

    await db.commit()
    await db.refresh(agent)
    return _build_agent_out(agent)
