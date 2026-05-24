from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import agent_tokens, agents, auth, install, patches, rdp, remote_access, remote_screen, script_executions


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="SolloRMM API",
    description="API do sistema próprio de RMM",
    version="0.5.3",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers autenticados
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(agents.router, prefix=settings.api_v1_prefix)
app.include_router(agent_tokens.router, prefix=settings.api_v1_prefix)
app.include_router(script_executions.router, prefix=settings.api_v1_prefix)
app.include_router(patches.router, prefix=settings.api_v1_prefix)
app.add_api_websocket_route(
    f"{settings.api_v1_prefix}/agents/{{agent_id}}/ssh",
    remote_access.ssh_websocket,
)
app.add_api_websocket_route(
    f"{settings.api_v1_prefix}/agents/{{agent_id}}/rdp",
    rdp.rdp_websocket,
)
app.add_api_websocket_route(
    f"{settings.api_v1_prefix}/agents/{{agent_id}}/remote-screen",
    remote_screen.remote_screen_websocket,
)

# Router público - serve scripts de instalação
app.include_router(install.router)


@app.get("/")
async def root():
    return {"name": "SolloRMM API", "version": "0.5.3", "status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
