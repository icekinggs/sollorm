from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import AgentToken, User
from app.security import decode_access_token
from app.services.tokens import find_valid_token, mark_token_used

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False
)


class AgentAuthResult:
    """Resultado da autenticação de agente - inclui o token usado (se for individual)."""

    def __init__(self, raw_token: str, agent_token: AgentToken | None, is_legacy: bool):
        self.raw_token = raw_token
        self.agent_token = agent_token  # None se for master token legado
        self.is_legacy = is_legacy


async def verify_agent_token(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> AgentAuthResult:
    """
    Valida o token Bearer enviado pelo agente.

    Aceita 2 formas (durante transição):
    1. Token individual no formato sollo_xxx... (recomendado)
    2. AGENT_MASTER_TOKEN do .env (legado, será removido em fases futuras)
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header inválido",
        )

    token = authorization.replace("Bearer ", "", 1).strip()

    # 1. Tenta como token individual (prefixo sollo_)
    if token.startswith("sollo_"):
        agent_token = await find_valid_token(db, token)
        if agent_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido, revogado ou expirado",
            )

        await mark_token_used(db, agent_token)
        # NOTA: commit é feito pelo handler do endpoint
        return AgentAuthResult(raw_token=token, agent_token=agent_token, is_legacy=False)

    # 2. Fallback - master token legado
    if settings.allow_legacy_master_token and token == settings.agent_master_token:
        return AgentAuthResult(raw_token=token, agent_token=None, is_legacy=True)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido",
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token mal-formado",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou inativo",
        )

    return user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operação requer privilégios de administrador",
        )
    return current_user
