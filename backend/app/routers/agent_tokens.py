from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import AgentToken, User
from app.schemas import (
    AgentTokenCreate,
    AgentTokenCreatedResponse,
    AgentTokenOut,
    StatusResponse,
)
from app.services.tokens import generate_token

router = APIRouter(prefix="/agent-tokens", tags=["agent-tokens"])


def _build_token_out(token: AgentToken) -> AgentTokenOut:
    """Constrói AgentTokenOut com is_active calculado."""
    is_active = token.revoked_at is None
    if token.expires_at is not None and is_active:
        if token.expires_at.tzinfo is None:
            exp = token.expires_at.replace(tzinfo=timezone.utc)
        else:
            exp = token.expires_at
        if datetime.now(timezone.utc) > exp:
            is_active = False

    # Constrói manualmente o dict ao invés de usar model_validate + model_dump
    # (model_validate falha porque is_active não existe no model SQLAlchemy)
    return AgentTokenOut(
        id=token.id,
        name=token.name,
        platform_hint=token.platform_hint,
        token_prefix=token.token_prefix,
        created_at=token.created_at,
        last_used_at=token.last_used_at,
        expires_at=token.expires_at,
        revoked_at=token.revoked_at,
        created_by_user_id=token.created_by_user_id,
        agent_id=token.agent_id,
        is_active=is_active,
    )


def _build_install_command(platform: str, raw_token: str) -> tuple[str, str]:
    """Retorna (oneliner, script_url) para a plataforma."""
    base = settings.public_backend_url.rstrip("/")

    if platform == "windows":
        script_url = f"{base}/install/windows.ps1"
        # IMPORTANTE: o one-liner é para ser COLADO em um PowerShell já aberto
        # (não usa `powershell -Command "..."` aninhado, que quebra as variáveis $env:)
        oneliner = (
            f"$env:SOLLORM_TOKEN='{raw_token}'; "
            f"$env:SOLLORM_SERVER='{base}'; "
            f"iwr -useb {script_url} | iex"
        )
    else:  # linux/darwin
        script_url = f"{base}/install/linux.sh"
        oneliner = (
            f"curl -fsSL {script_url} | "
            f"sudo SOLLORM_TOKEN='{raw_token}' SOLLORM_SERVER='{base}' bash"
        )

    return oneliner, script_url


@router.post("", response_model=AgentTokenCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_token(
    payload: AgentTokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cria um novo token de agente.

    O token em texto puro é retornado UMA vez. Anote, ele não aparecerá novamente.
    """
    raw_token, token_hash, token_prefix = generate_token()

    expires_at = None
    if payload.expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)

    agent_token = AgentToken(
        token_hash=token_hash,
        token_prefix=token_prefix,
        name=payload.name,
        platform_hint=payload.platform_hint,
        created_by_user_id=current_user.id,
        expires_at=expires_at,
    )
    db.add(agent_token)
    await db.commit()
    await db.refresh(agent_token)

    oneliner, script_url = _build_install_command(payload.platform_hint, raw_token)

    return AgentTokenCreatedResponse(
        token_id=agent_token.id,
        name=agent_token.name,
        platform_hint=agent_token.platform_hint,
        raw_token=raw_token,
        install_command_oneliner=oneliner,
        install_script_url=script_url,
        expires_at=expires_at,
    )


@router.get("", response_model=list[AgentTokenOut])
async def list_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista todos os tokens criados (sem expor o token em texto puro)."""
    result = await db.execute(
        select(AgentToken).order_by(AgentToken.created_at.desc())
    )
    tokens = result.scalars().all()
    return [_build_token_out(t) for t in tokens]


@router.get("/{token_id}", response_model=AgentTokenOut)
async def get_token(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna detalhes de um token específico."""
    result = await db.execute(select(AgentToken).where(AgentToken.id == token_id))
    token = result.scalar_one_or_none()

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token não encontrado",
        )

    return _build_token_out(token)


@router.post("/{token_id}/revoke", response_model=StatusResponse)
async def revoke_token(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoga um token. Não pode ser desfeito."""
    result = await db.execute(select(AgentToken).where(AgentToken.id == token_id))
    token = result.scalar_one_or_none()

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token não encontrado",
        )

    if token.revoked_at is not None:
        return StatusResponse(message="Token já estava revogado")

    token.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    return StatusResponse(message=f"Token '{token.name}' revogado com sucesso")


@router.delete("/{token_id}", response_model=StatusResponse)
async def delete_token(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Apaga permanentemente um token.
    Use isso só para tokens nunca usados (sem agente vinculado).
    Para tokens em uso, revogue ao invés de apagar.
    """
    result = await db.execute(select(AgentToken).where(AgentToken.id == token_id))
    token = result.scalar_one_or_none()

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token não encontrado",
        )

    if token.agent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Token está vinculado a um agente. Revogue ao invés de apagar.",
        )

    await db.delete(token)
    await db.commit()

    return StatusResponse(message=f"Token '{token.name}' apagado")
