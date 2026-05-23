from datetime import datetime

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
    """Requisição de login - usaremos JSON ao invés do form OAuth2 padrão."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Resposta do login - JWT + tipo + info básica do usuário."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"


class UserOut(BaseModel):
    """Representação de um usuário (sem senha) retornada pela API."""

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
    """Payload para criar novo usuário (admin only)."""

    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    full_name: str | None = None
    password: str = Field(min_length=8, max_length=128)
    is_superuser: bool = False


TokenResponse.model_rebuild()
