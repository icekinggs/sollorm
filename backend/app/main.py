from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import agent_tokens, agents, auth, install, script_executions


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="SolloRMM API",
    description="API do sistema próprio de RMM",
    version="0.4.0",
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

# Router público - serve scripts de instalação
app.include_router(install.router)


@app.get("/")
async def root():
    return {"name": "SolloRMM API", "version": "0.4.0", "status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
