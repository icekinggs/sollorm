from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Agent, PatchItem, PatchScan, User
from app.schemas import (
    PatchInstallRequest,
    PatchItemOut,
    PatchScanDetailOut,
    PatchScanOut,
    StatusResponse,
)

router = APIRouter(prefix="/agents", tags=["patches"])


def _get_manager():
    from app.routers.script_executions import manager
    return manager


@router.post(
    "/{agent_id}/patches/scan",
    response_model=PatchScanOut,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_patch_scan(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente não encontrado")

    scan = PatchScan(
        agent_id=agent_id,
        requested_by_user_id=current_user.id,
        status="scanning",
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    sent = await _get_manager().send_command(agent_id, {
        "type": "scan_patches",
        "scan_id": scan.id,
    })
    if not sent:
        scan.status = "error"
        scan.error_message = "Agente não está conectado ao canal de comandos"
        scan.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(scan)

    return scan


@router.get("/{agent_id}/patches", response_model=PatchScanDetailOut | None)
async def get_latest_patch_scan(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scan_res = await db.execute(
        select(PatchScan)
        .where(PatchScan.agent_id == agent_id)
        .order_by(PatchScan.requested_at.desc())
        .limit(1)
    )
    scan = scan_res.scalar_one_or_none()
    if scan is None:
        return None

    items_res = await db.execute(
        select(PatchItem)
        .where(PatchItem.scan_id == scan.id)
        .order_by(PatchItem.severity.desc(), PatchItem.name)
    )
    items = list(items_res.scalars().all())
    return {"scan": scan, "items": items}


@router.post("/{agent_id}/patches/install", response_model=StatusResponse)
async def install_patches(
    agent_id: str,
    payload: PatchInstallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente não encontrado")

    sent = await _get_manager().send_command(agent_id, {
        "type": "install_patches",
        "packages": payload.package_names,
    })
    if not sent:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Agente não está conectado")

    return StatusResponse(message=f"{len(payload.package_names)} pacote(s) enviados para instalação")


@router.post("/{agent_id}/patches/install-all", response_model=StatusResponse)
async def install_all_patches(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente não encontrado")

    scan_res = await db.execute(
        select(PatchScan)
        .where(PatchScan.agent_id == agent_id)
        .where(PatchScan.status == "done")
        .order_by(PatchScan.requested_at.desc())
        .limit(1)
    )
    scan = scan_res.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhum scan disponível — execute um scan primeiro")

    items_res = await db.execute(
        select(PatchItem)
        .where(PatchItem.scan_id == scan.id)
        .where(PatchItem.installed == False)
    )
    items = list(items_res.scalars().all())
    if not items:
        return StatusResponse(message="Nenhum pacote pendente para instalar")

    packages = [item.name for item in items]
    sent = await _get_manager().send_command(agent_id, {
        "type": "install_patches",
        "scan_id": scan.id,
        "packages": packages,
    })
    if not sent:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Agente não está conectado")

    return StatusResponse(message=f"{len(packages)} pacotes enviados para instalação")
