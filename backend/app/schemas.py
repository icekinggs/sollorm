from datetime import datetime

from pydantic import BaseModel, Field


class SystemInfoIn(BaseModel):
    """Payload enviado pelo agente com info completa do sistema."""

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
    """Payload de heartbeat enviado pelo agente."""

    agent_id: str
    hostname: str
    cpu_usage_percent: float = Field(ge=0, le=100)
    ram_usage_percent: float = Field(ge=0, le=100)
    disk_usage_percent: float = Field(ge=0, le=100)
    uptime_seconds: int
    timestamp: datetime


class AgentOut(BaseModel):
    """Representação de um agente retornada pela API."""

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
    is_online: bool = False  # calculado: last_seen < 2 min atrás

    class Config:
        from_attributes = True


class HeartbeatOut(BaseModel):
    """Heartbeat retornado pela API."""

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
    """Resposta padrão de sucesso."""

    status: str = "ok"
    message: str | None = None
