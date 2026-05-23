from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Agent(Base):
    """Representa um endpoint gerenciado (Windows/Linux/macOS)."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )

    # Informações de identificação
    hostname: Mapped[str] = mapped_column(String(255), index=True)
    os: Mapped[str | None] = mapped_column(String(50))
    platform: Mapped[str | None] = mapped_column(String(255))
    architecture: Mapped[str | None] = mapped_column(String(20))
    kernel_arch: Mapped[str | None] = mapped_column(String(20))

    # Hardware
    cpu_model: Mapped[str | None] = mapped_column(String(255))
    cpu_cores: Mapped[int | None] = mapped_column(Integer)
    ram_total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    disk_total_bytes: Mapped[int | None] = mapped_column(BigInteger)

    # Versão do agente
    agent_version: Mapped[str | None] = mapped_column(String(20))

    # Timestamps
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_system_info: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relação com heartbeats
    heartbeats: Mapped[list["Heartbeat"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Agent {self.hostname} ({self.id[:8]})>"


class Heartbeat(Base):
    """Métricas pontuais enviadas pelo agente."""

    __tablename__ = "heartbeats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )

    cpu_usage_percent: Mapped[float] = mapped_column(Float)
    ram_usage_percent: Mapped[float] = mapped_column(Float)
    disk_usage_percent: Mapped[float] = mapped_column(Float)
    uptime_seconds: Mapped[int] = mapped_column(BigInteger)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    agent: Mapped["Agent"] = relationship(back_populates="heartbeats")
