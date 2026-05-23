from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class SystemInfoIn(BaseModel):
    agent_id: str
    hostname: str
    os: str
    platform: str
    architecture: str
    kernel_arch: str
    uptime_seconds: int
    cpu_model: str
    cpu_cores: int
    ram_total_bytes: int
    disk_total_bytes: int
    agent_version: str
    timestamp: datetime


class HeartbeatIn(BaseModel):
    agent_id: str
    hostname: str
    cpu_usage_percent: float = Field(ge=0, le=100)
    ram_usage_percent: float = Field(ge=0, le=100)
    disk_usage_percent: float = Field(ge=0, le=100)
    uptime_seconds: int
    timestamp: datetime


class AgentOut(BaseModel):
    id: str
    hostname: str
    os: str | None
    platform: str | None
    cpu_model: str | None
    cpu_cores: int | None
    ram_total_bytes: int | None
    disk_total_bytes: int | None
    agent_version: str | None
    first_seen: datetime
    last_seen: datetime | None
    is_online: bool = False
    token_name: str | None = None
    token_prefix: str | None = None

    class Config:
        from_attributes = True


class HeartbeatOut(BaseModel):
    id: int
    agent_id: str
    cpu_usage_percent: float
    ram_usage_percent: float
    disk_usage_percent: float
    uptime_seconds: int
    received_at: datetime
    reported_at: datetime

    class Config:
        from_attributes = True


class StatusResponse(BaseModel):
    status: str = "ok"
    message: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    full_name: str | None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    last_login: datetime | None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    full_name: str | None = None
    password: str = Field(min_length=8, max_length=128)
    is_superuser: bool = False


# ---------- Agent Tokens ----------

PlatformLiteral = Literal["windows", "linux", "darwin"]


class AgentTokenCreate(BaseModel):
    """Payload para criar um novo token de agente."""

    name: str = Field(min_length=1, max_length=255)
    platform_hint: PlatformLiteral = "linux"
    expires_in_days: int | None = Field(None, ge=1, le=3650)


class AgentTokenOut(BaseModel):
    """Token retornado em listagens (SEM o token em texto puro)."""

    id: str
    name: str
    platform_hint: str
    token_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_by_user_id: str
    agent_id: str | None
    is_active: bool

    class Config:
        from_attributes = True


class AgentTokenCreatedResponse(BaseModel):
    """
    Resposta da CRIAÇÃO de token - inclui o token em texto puro.
    Este é o ÚNICO momento em que o token aparece - quem perder, gera outro.
    """

    token_id: str
    name: str
    platform_hint: str
    raw_token: str = Field(description="Token em texto puro - guarde, não aparecerá novamente")
    install_command_oneliner: str = Field(description="Comando one-liner para colar na máquina-alvo")
    install_script_url: str
    expires_at: datetime | None


TokenResponse.model_rebuild()
