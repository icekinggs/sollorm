from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AgentAuthResult, get_current_user, verify_agent_token
from app.database import get_db
from app.models import SoftwareItem, User
from app.schemas import SoftwareItemOut, SoftwareSyncPayload, StatusResponse

router = APIRouter(tags=["software"])


@router.post(
    "/agents/{agent_id}/software/sync",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
)
async def sync_software(
    agent_id: str,
    payload: SoftwareSyncPayload,
    db: AsyncSession = Depends(get_db),
    _auth: AgentAuthResult = Depends(verify_agent_token),
):
    now = datetime.now(timezone.utc)
    await db.execute(delete(SoftwareItem).where(SoftwareItem.agent_id == agent_id))
    for item in payload.items:
        db.add(SoftwareItem(
            agent_id=agent_id,
            name=item.name,
            version=item.version,
            publisher=item.publisher,
            install_date=item.install_date,
            source=item.source,
            collected_at=now,
        ))
    await db.commit()
    return StatusResponse(message=f"{len(payload.items)} itens sincronizados")


@router.get("/agents/{agent_id}/software", response_model=list[SoftwareItemOut])
async def list_software(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SoftwareItem)
        .where(SoftwareItem.agent_id == agent_id)
        .order_by(SoftwareItem.name)
    )
    return list(result.scalars().all())
