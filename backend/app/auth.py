from fastapi import Header, HTTPException, status

from app.config import settings


async def verify_agent_token(authorization: str = Header(...)) -> str:
    """
    Valida o token Bearer enviado pelo agente.

    Na Fase 1 usamos um único master token para simplificar.
    Na Fase 2 cada agente terá seu próprio token único.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header inválido",
        )

    token = authorization.replace("Bearer ", "", 1).strip()

    if token != settings.agent_master_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )

    return token
