from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://sollorm:sollorm@db:5432/sollorm"
    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "MUDE_ESTA_CHAVE_EM_PRODUCAO_USE_OPENSSL_RAND_HEX_32"
    access_token_expire_minutes: int = 60 * 24

    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://172.16.2.12:5173",
        "https://rmm.sollobrasil.com.br",
    ]

    agent_master_token: str = "MUDE_ESTE_TOKEN_GERE_UM_NOVO"


settings = Settings()
