from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models import Agent, Group, UpdateApproval, User
from app.schemas import (
    StatusResponse,
    UpdateApprovalCreate,
    UpdateApprovalOut,
    UpdateStatusGroup,
    UpdateStatusOut,
)
from app.version import get_latest_version

router = APIRouter(tags=["updates"])


def _get_manager():
    from app.routers.script_executions import manager
    return manager


def _download_url(version: str, os_key: str) -> str:
    filename = "sollorm-agent-windows-amd64.exe" if os_key == "windows" else "sollorm-agent-linux-amd64"
    return f"https://github.com/{settings.github_repo}/releases/download/{version}/{filename}"


def _approval_out(a: UpdateApproval) -> UpdateApprovalOut:
    if a.is_global:
        group_name = "Todos os grupos"
    elif a.group_id is None:
        group_name = "Sem grupo"
    else:
        group_name = a.group.name if a.group else "—"

    return UpdateApprovalOut(
        id=a.id,
        version=a.version,
        group_id=a.group_id,
        group_name=group_name,
        is_global=a.is_global,
        approved_by=a.approved_by.username if a.approved_by else "—",
        approved_at=a.approved_at,
        active=a.active,
        notes=a.notes,
    )


def compute_approved_version(
    group_id: str | None,
    approvals: list[UpdateApproval],
) -> str | None:
    """Retorna a versão aprovada para um grupo (regra: específico > global)."""
    group_ap = None
    global_ap = None
    for ap in approvals:
        if not ap.active:
            continue
        if ap.is_global:
            global_ap = ap
        elif ap.group_id == group_id:
            group_ap = ap
        elif ap.group_id is None and group_id is None:
            group_ap = ap  # "Sem grupo" approval
    result = group_ap or global_ap
    return result.version if result else None


# ── Status overview ──────────────────────────────────────────────────────────

@router.get("/update-approvals/status", response_model=UpdateStatusOut)
async def get_update_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    agents_res = await db.execute(select(Agent))
    agents = list(agents_res.scalars().all())

    groups_res = await db.execute(select(Group).order_by(Group.name))
    groups = list(groups_res.scalars().all())

    approvals_res = await db.execute(
        select(UpdateApproval)
        .options(selectinload(UpdateApproval.group))
        .where(UpdateApproval.active == True)
    )
    approvals = list(approvals_res.scalars().all())

    def version_counts(group_agents: list[Agent]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for a in group_agents:
            v = a.agent_version or "desconhecido"
            counts[v] = counts.get(v, 0) + 1
        return counts

    result: list[UpdateStatusGroup] = []

    for g in groups:
        grp_agents = [a for a in agents if a.group_id == g.id]
        result.append(UpdateStatusGroup(
            group_id=g.id,
            group_name=g.name,
            group_color=g.color,
            approved_version=compute_approved_version(g.id, approvals),
            agent_count=len(grp_agents),
            versions=version_counts(grp_agents),
        ))

    ungrouped = [a for a in agents if a.group_id is None]
    result.append(UpdateStatusGroup(
        group_id=None,
        group_name="Sem grupo",
        group_color=None,
        approved_version=compute_approved_version(None, approvals),
        agent_count=len(ungrouped),
        versions=version_counts(ungrouped),
    ))

    return UpdateStatusOut(latest_version=get_latest_version(), groups=result)


# ── CRUD aprovações ───────────────────────────────────────────────────────────

@router.get("/update-approvals", response_model=list[UpdateApprovalOut])
async def list_approvals(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    res = await db.execute(
        select(UpdateApproval)
        .options(selectinload(UpdateApproval.group), selectinload(UpdateApproval.approved_by))
        .order_by(UpdateApproval.approved_at.desc())
        .limit(100)
    )
    return [_approval_out(a) for a in res.scalars().all()]


@router.post("/update-approvals", response_model=UpdateApprovalOut, status_code=status.HTTP_201_CREATED)
async def create_approval(
    payload: UpdateApprovalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Desativa aprovação anterior para o mesmo escopo
    if payload.is_global:
        old_q = select(UpdateApproval).where(
            UpdateApproval.active == True, UpdateApproval.is_global == True
        )
    elif payload.group_id is None:
        old_q = select(UpdateApproval).where(
            UpdateApproval.active == True,
            UpdateApproval.is_global == False,
            UpdateApproval.group_id.is_(None),
        )
    else:
        old_q = select(UpdateApproval).where(
            UpdateApproval.active == True,
            UpdateApproval.is_global == False,
            UpdateApproval.group_id == payload.group_id,
        )
    for old in (await db.execute(old_q)).scalars().all():
        old.active = False

    approval = UpdateApproval(
        version=payload.version,
        group_id=payload.group_id,
        is_global=payload.is_global,
        approved_by_user_id=current_user.id,
        approved_at=datetime.now(timezone.utc),
        active=True,
        notes=payload.notes,
    )
    db.add(approval)
    await db.commit()

    # Recarrega com relacionamentos
    res = await db.execute(
        select(UpdateApproval)
        .options(selectinload(UpdateApproval.group), selectinload(UpdateApproval.approved_by))
        .where(UpdateApproval.id == approval.id)
    )
    approval = res.scalar_one()

    # Empurra update para agentes online do grupo
    await _push_to_group(payload.group_id, payload.is_global, payload.version)

    return _approval_out(approval)


@router.delete("/update-approvals/{approval_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    res = await db.execute(select(UpdateApproval).where(UpdateApproval.id == approval_id))
    approval = res.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="Aprovação não encontrada")
    approval.active = False
    await db.commit()


# ── Push helpers ──────────────────────────────────────────────────────────────

async def _push_to_group(group_id: str | None, is_global: bool, version: str) -> None:
    """Envia update_agent para todos os agentes online do grupo aprovado."""
    manager = _get_manager()
    async with AsyncSessionLocal() as db:
        if is_global:
            agents_res = await db.execute(select(Agent))
        elif group_id is None:
            agents_res = await db.execute(select(Agent).where(Agent.group_id.is_(None)))
        else:
            agents_res = await db.execute(select(Agent).where(Agent.group_id == group_id))
        agents = list(agents_res.scalars().all())

    for agent in agents:
        if agent.agent_version == version:
            continue
        await manager.send_command(agent.id, {
            "type": "update_agent",
            "version": version,
            "download_url": _download_url(version, agent.os or "linux"),
        })


async def check_and_push_on_heartbeat(agent_id: str, agent_version: str, group_id: str | None) -> None:
    """
    Chamado a cada heartbeat: se o agente tem update aprovado pendente, envia o comando.
    Garante que agentes que estavam offline ao aprovar sejam atualizados assim que voltam.
    """
    async with AsyncSessionLocal() as db:
        conditions = [
            and_(UpdateApproval.active == True, UpdateApproval.is_global == True)
        ]
        if group_id is not None:
            conditions.append(
                and_(UpdateApproval.active == True,
                     UpdateApproval.is_global == False,
                     UpdateApproval.group_id == group_id)
            )
        else:
            conditions.append(
                and_(UpdateApproval.active == True,
                     UpdateApproval.is_global == False,
                     UpdateApproval.group_id.is_(None))
            )

        res = await db.execute(
            select(UpdateApproval)
            .where(or_(*conditions))
            .order_by(UpdateApproval.approved_at.desc())
            .limit(1)
        )
        approval = res.scalar_one_or_none()

    if approval and approval.version != agent_version:
        manager = _get_manager()
        # Busca OS do agente
        async with AsyncSessionLocal() as db:
            agent_res = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = agent_res.scalar_one_or_none()
        os_key = agent.os if agent else "linux"
        await manager.send_command(agent_id, {
            "type": "update_agent",
            "version": approval.version,
            "download_url": _download_url(approval.version, os_key or "linux"),
        })
