"""
Serviço de gestão de tokens de agente.

Tokens são gerados como strings aleatórias seguras no formato:
    sollo_<32 chars base62>

Apenas o hash SHA-256 é armazenado no banco. O token em texto puro
só é mostrado ao admin uma vez, no momento da criação.
"""
import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentToken

TOKEN_PREFIX = "sollo_"
TOKEN_RANDOM_LENGTH = 32  # caracteres aleatórios após o prefixo


def generate_token() -> tuple[str, str, str]:
    """
    Gera um novo token e retorna (token_completo, token_hash, token_prefix_publico).

    - token_completo: o token que vai ser mostrado UMA vez ao admin
    - token_hash: SHA-256 hex digest, vai pro banco
    - token_prefix_publico: primeiros chars pra mostrar no dashboard
    """
    random_part = secrets.token_urlsafe(TOKEN_RANDOM_LENGTH)[:TOKEN_RANDOM_LENGTH]
    full_token = f"{TOKEN_PREFIX}{random_part}"
    token_hash = hashlib.sha256(full_token.encode("utf-8")).hexdigest()
    public_prefix = full_token[: len(TOKEN_PREFIX) + 8]  # "sollo_xxxxxxxx"
    return full_token, token_hash, public_prefix


def hash_token(token: str) -> str:
    """Gera hash SHA-256 de um token para lookup no banco."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def find_valid_token(db: AsyncSession, token: str) -> AgentToken | None:
    """
    Procura um token válido no banco.
    Retorna None se: não existe, foi revogado, ou expirou.
    """
    token_hash = hash_token(token)
    result = await db.execute(
        select(AgentToken).where(AgentToken.token_hash == token_hash)
    )
    agent_token = result.scalar_one_or_none()

    if agent_token is None:
        return None

    if agent_token.is_revoked:
        return None

    if agent_token.is_expired:
        return None

    return agent_token


async def mark_token_used(db: AsyncSession, agent_token: AgentToken) -> None:
    """Atualiza last_used_at do token (sem commit - chamador faz)."""
    agent_token.last_used_at = datetime.now(timezone.utc)
