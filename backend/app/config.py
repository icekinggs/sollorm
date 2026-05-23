from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+asyncpg://sollorm:sollorm@db:5432/sollorm"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Segurança
    secret_key: str = "MUDE_ESTA_CHAVE_EM_PRODUCAO_USE_OPENSSL_RAND_HEX_32"
    access_token_expire_minutes: int = 60 * 24  # 24h

    # API
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "https://rmm.sollobrasil.com.br"]

    # Agentes
    # Token mestre temporário para registro de agentes na Fase 1.
    # Na Fase 2 isso será substituído por tokens individuais por organização.
    agent_master_token: str = "MUDE_ESTE_TOKEN_GERE_UM_NOVO"


settings = Settings()
