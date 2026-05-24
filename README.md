# SolloRMM

> Sistema próprio de Remote Monitoring & Management (RMM), construído do zero para uso interno.

[![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()
[![Release](https://img.shields.io/badge/release-v0.5.0-brightgreen)]()
[![Go](https://img.shields.io/badge/Go-1.22-00ADD8?logo=go)]()
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql)]()
[![Vue](https://img.shields.io/badge/Vue-3-42b883?logo=vuedotjs)]()

## Sobre

SolloRMM é uma solução de gerenciamento remoto de endpoints (Windows, Linux, macOS) inspirada em ferramentas como Tactical RMM, NinjaOne e Atera — mas construída do zero, sem amarras de licença, focada em escalar para milhares de endpoints num ambiente corporativo próprio.

## Stack

| Camada | Tecnologia |
|---|---|
| Agente | Go 1.22 + gopsutil |
| Backend API | Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) |
| Banco de dados | PostgreSQL 16 |
| Cache / Filas | Redis 7 |
| Frontend | Vue 3 + PrimeVue + Vite |
| Acesso remoto | SSH nativo (asyncssh) + MeshCentral (RDP/VNC) |
| Mensageria (planejado) | NATS |
| Deploy | Docker Compose |

## Estrutura do projeto

```
sollorm/
├── agent/        # Agente em Go que roda nos endpoints
├── backend/      # API em Python/FastAPI
├── frontend/     # Interface web Vue 3 (Fase 2B)
├── deploy/       # docker-compose, configs
└── docs/         # Documentação técnica e guias
```

## Roadmap

- [x] **Fase 1** — Agente envia heartbeat + info de hardware pro backend
- [x] **Fase 2A** — Autenticação JWT no backend, modelo de Users
- [x] **Fase 2B** — Frontend Vue 3 com login + dashboard (PrimeVue)
- [x] **Fase 3** — Execução remota de scripts (PowerShell/Bash/Python)
- [x] **Fase 3B** — Terminal SSH nativo via WebSocket (xterm.js + asyncssh)
- [x] **Fase 5** — Acesso remoto: SSH integrado + MeshCentral (RDP/VNC) via iframe
- [ ] **Fase 4** — Monitoramento ativo (checks configuráveis) + alertas
- [ ] **Fase 6** — Patch management Windows/Linux
- [ ] **Fase 7** — Inventário de software instalado
- [ ] **Fase 8** — Execução agendada (scripts em cron)

## Como rodar

### Pré-requisitos

- Docker + Docker Compose
- Go 1.22+ (para compilar o agente)
- Git

### Subir o backend

```bash
git clone https://github.com/icekinggs/sollorm.git
cd sollorm/deploy

# Gerar segredos
cat > .env << EOF
POSTGRES_PASSWORD=$(openssl rand -hex 24)
SECRET_KEY=$(openssl rand -hex 32)
AGENT_MASTER_TOKEN=$(openssl rand -hex 32)
EOF

# Anote o AGENT_MASTER_TOKEN — você vai precisar dele
cat .env

# Subir
docker compose up -d --build
```

API disponível em `http://localhost:8000` (docs em `/docs`).

### Criar o primeiro usuário admin

```bash
docker compose exec backend python -m scripts.create_user
```

### Compilar e rodar o agente

```bash
cd ../agent
go mod tidy
go build -o sollorm-agent

# Linux/macOS
./sollorm-agent --server http://localhost:8000 --token <AGENT_MASTER_TOKEN>

# Cross-compile pra Windows
GOOS=windows GOARCH=amd64 go build -o sollorm-agent.exe
```

## Endpoints principais

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/api/v1/auth/login` | — | Login retorna JWT |
| GET | `/api/v1/auth/me` | JWT | Dados do usuário atual |
| GET | `/api/v1/agents` | JWT | Lista agentes registrados |
| GET | `/api/v1/agents/{id}` | JWT | Detalhes de um agente |
| GET | `/api/v1/agents/{id}/heartbeats` | JWT | Histórico de heartbeats |
| DELETE | `/api/v1/agents/{id}` | JWT | Remove agente e histórico |
| WS | `/api/v1/agents/{id}/ssh` | JWT (query) | Terminal SSH nativo via WebSocket |
| POST | `/api/v1/agents/system-info` | Agent Token | Agente envia info de SO/hardware |
| POST | `/api/v1/agents/heartbeat` | Agent Token | Agente envia métricas |
| GET | `/api/v1/agents/{id}/executions` | JWT | Histórico de execuções |
| POST | `/api/v1/agents/{id}/executions` | JWT | Dispara execução remota de script |

Documentação interativa completa em `/docs` (Swagger UI).

## Documentação

- [Quickstart - Fase 1](docs/QUICKSTART.md)
- [Upgrade - Fase 2A](docs/FASE-2A-UPGRADE.md)

## Segurança

- Senhas hasheadas com Argon2
- JWT com expiração configurável
- Token separado para agentes (Bearer master) e usuários humanos (JWT)
- HTTPS recomendado em produção (use seu próprio certificado wildcard)
- Sem dados saindo do seu ambiente (100% self-hosted)

## Licença

[MIT](LICENSE) — uso livre, sem garantias.

## Status

🚧 **Em desenvolvimento ativo.** Use por sua conta e risco. Não recomendado para produção crítica ainda.
