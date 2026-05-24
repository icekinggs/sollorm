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

    # ---------- Agentes ----------
    # Master token legado - sera removido em fases futuras
    agent_master_token: str = "MUDE_ESTE_TOKEN_GERE_UM_NOVO"
    allow_legacy_master_token: bool = True

    # URL pública do backend - usada nos scripts de instalação
    # IMPORTANTE: deve ser alcançável pelos endpoints!
    public_backend_url: str = "http://172.16.2.12:8000"

    # ---------- Releases (binários do agente) ----------
    # Owner/repo no GitHub onde estão os releases do agente
    github_repo: str = "icekinggs/sollorm"

    # Versão atual recomendada (atualize quando publicar nova release)
    agent_current_version: str = "v0.5.3"

    # ---------- Guacamole / RDP ----------
    guacd_host: str = "guacd"
    guacd_port: int = 4822

    # ---------- MeshCentral ----------
    # URL usada pelo botão "Conectar" e pelos endpoints para acessar o MeshCentral.
    meshcentral_public_url: str = "https://localhost:8443"

    # URLs opcionais dos agentes geradas dentro do MeshCentral em "Add Agent".
    # Quando vazias, os instaladores SolloRMM pulam a instalação do Mesh Agent.
    meshcentral_agent_linux_url: str = ""
    meshcentral_agent_windows_url: str = ""


settings = Settings()
