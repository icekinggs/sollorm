from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class AgentToken(Base):
    """
    Token único por agente. Armazenamos apenas o hash SHA-256.
    O token em texto puro só é mostrado ao admin no momento da criação.
    """

    __tablename__ = "agent_tokens"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )

    # Hash do token (SHA-256) - único, indexado para lookup rápido
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Prefixo público (primeiros 8 chars do token) - pra mostrar no dashboard
    # como "sollo_xxxxxxxx..." sem expor o token completo
    token_prefix: Mapped[str] = mapped_column(String(16))

    # Nome amigável (ex: "DESKTOP-RH-Joao", "FILESERVER-01")
    name: Mapped[str] = mapped_column(String(255))

    # Plataforma esperada (windows, linux, darwin) - usado pelo wizard
    platform_hint: Mapped[str] = mapped_column(String(20))

    # Quem criou o token
    created_by_user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Agent que usa este token (preenchido no primeiro registro)
    agent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agents.id", ondelete="SET NULL"), unique=True
    )

    # Relações
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])
    agent: Mapped["Agent"] = relationship(back_populates="token", foreign_keys=[agent_id])

    def __repr__(self) -> str:
        return f"<AgentToken {self.name} ({self.token_prefix}...)>"

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        from datetime import timezone
        return datetime.now(timezone.utc) > self.expires_at


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )

    hostname: Mapped[str] = mapped_column(String(255), index=True)
    os: Mapped[str | None] = mapped_column(String(50))
    platform: Mapped[str | None] = mapped_column(String(255))
    architecture: Mapped[str | None] = mapped_column(String(20))
    kernel_arch: Mapped[str | None] = mapped_column(String(20))

    cpu_model: Mapped[str | None] = mapped_column(String(255))
    cpu_cores: Mapped[int | None] = mapped_column(Integer)
    ram_total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    disk_total_bytes: Mapped[int | None] = mapped_column(BigInteger)

    agent_version: Mapped[str | None] = mapped_column(String(20))

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_system_info: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relação reversa com o token (1-to-1)
    token: Mapped["AgentToken | None"] = relationship(
        back_populates="agent",
        foreign_keys=[AgentToken.agent_id],
        uselist=False,
    )

    heartbeats: Mapped[list["Heartbeat"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Agent {self.hostname} ({self.id[:8]})>"


class Heartbeat(Base):
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
