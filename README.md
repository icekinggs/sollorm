# SolloRMM

Sistema próprio de gerenciamento remoto (RMM) para ambiente interno.

## Visão geral

Stack:
- **Agente**: Go 1.22 (Windows/Linux/macOS)
- **Backend**: Python 3.12 + FastAPI
- **Banco**: PostgreSQL 16
- **Cache**: Redis 7
- **Frontend** (futuro): Vue 3 + Vuetify
- **Acesso remoto** (futuro): MeshCentral integrado
- **Deploy**: Docker Compose

## Estrutura do projeto

```
sollorm/
├── agent/        # Agente em Go que roda nos endpoints
├── backend/      # API em Python/FastAPI
├── frontend/     # Interface web (Fase 2)
├── deploy/       # docker-compose, configs de Nginx, etc
└── docs/         # Documentação técnica
```

## Roadmap

- [x] **Fase 0** — Setup do projeto e arquitetura
- [ ] **Fase 1** — Agente envia heartbeat + info de hardware pro backend
- [ ] **Fase 2** — Frontend lista agentes e mostra status
- [ ] **Fase 3** — Execução remota de scripts/comandos
- [ ] **Fase 4** — Monitoramento (checks) + alertas
- [ ] **Fase 5** — Integração com MeshCentral pra acesso remoto
- [ ] **Fase 6** — Patch management Windows

## Como começar

### Pré-requisitos
- Docker + Docker Compose na VM Debian
- Go 1.22+ (apenas para compilar o agente)
- Git

### Subir o backend
```bash
cd deploy
docker compose up -d
```

A API ficará em `http://localhost:8000` (docs em `/docs`).

### Compilar e rodar o agente
```bash
cd agent
go build -o sollorm-agent
./sollorm-agent --server http://192.168.x.x:8000 --token TOKEN_AQUI
```

## Segurança

- Toda comunicação agente↔backend usa HTTPS + token Bearer
- Agentes recebem token único na instalação
- Backend valida token em todo request
- Senhas hasheadas com Argon2
- 2FA obrigatório para usuários admin

## Licença

Proprietary — uso interno apenas.
