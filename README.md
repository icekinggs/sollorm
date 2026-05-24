# SolloRMM

> Sistema de Remote Monitoring & Management (RMM) self-hosted, construído do zero para gerenciar endpoints Windows e Linux sem depender de licenças de terceiros.

[![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)]()
[![Release](https://img.shields.io/badge/release-v0.5.4-brightgreen)](https://github.com/icekinggs/sollorm/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Go](https://img.shields.io/badge/Go-1.22-00ADD8?logo=go&logoColor=white)]()
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)]()
[![Vue](https://img.shields.io/badge/Vue-3-42b883?logo=vuedotjs&logoColor=white)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)]()

---

## Sobre

SolloRMM é uma solução completa de RMM, inspirada em Tactical RMM, NinjaOne e Atera — mas 100% self-hosted, sem custos de licença e sem dados saindo do seu ambiente. Construída para escalar para milhares de endpoints em ambientes corporativos.

**O que você pode fazer hoje:**

- Monitorar hardware (CPU, RAM, disco, uptime) em tempo real
- Executar scripts remotamente (PowerShell, Bash, Python)
- Abrir terminal SSH nativo diretamente no navegador
- Acessar a tela do endpoint remotamente (captura nativa, sem senha, sem Guacamole)
- Gerenciar tokens de agente por endpoint
- Gerenciar atualizações de sistema (patch management)

---

## Stack

| Camada | Tecnologia |
|---|---|
| Agente | Go 1.22 — binário único, sem dependências |
| Backend API | Python 3.12 · FastAPI · SQLAlchemy 2.0 async |
| Banco de dados | PostgreSQL 16 |
| Cache | Redis 7 |
| Frontend | Vue 3 · PrimeVue · Vite |
| Acesso remoto | SSH nativo (asyncssh) · Captura de tela nativa (GDI/Session 0) |
| Deploy | Docker Compose |

---

## Arquitetura

```
Navegador (Vue 3)
      │  HTTPS / WSS
      ▼
Backend FastAPI  ──── PostgreSQL 16
      │          ──── Redis 7
      │  WebSocket persistente
      ▼
Agente Go (endpoint)
  ├─ Heartbeat / System Info  →  POST /api/v1/agents/heartbeat
  ├─ Execução de scripts      ←  WS  /api/v1/agents/{id}/executions
  ├─ Terminal SSH              ←  WS  /api/v1/agents/{id}/ssh
  └─ Captura de tela          ←  WS  /api/v1/agents/{id}/remote-screen
```

O agente mantém uma conexão WebSocket persistente com o backend. Comandos chegam do backend para o agente pelo mesmo canal, sem necessidade de abrir portas no endpoint.

---

## Estrutura do projeto

```
sollorm/
├── agent/                    # Agente Go (binário para os endpoints)
│   ├── cmd/sollorm-agent/    # Entrypoint
│   └── internal/
│       ├── commands/         # Dispatcher de comandos WebSocket
│       ├── config/           # Leitura/escrita de config.json
│       ├── remote/           # Captura de tela nativa (GDI + Session 0)
│       ├── reporter/         # Envio de heartbeat e system info
│       ├── service/          # Loop principal (systemd / Windows Service)
│       └── system/           # Coleta de métricas (gopsutil)
├── backend/
│   └── app/
│       ├── routers/          # Endpoints FastAPI
│       ├── models.py         # Modelos SQLAlchemy
│       ├── schemas.py        # Schemas Pydantic
│       └── config.py         # Configuração via .env
├── frontend/
│   └── src/
│       ├── views/            # Páginas (Dashboard, AgentDetail, Login)
│       └── components/       # RemoteScreenPanel, SshTerminal, etc.
└── deploy/
    ├── docker-compose.yml
    └── .env.example
```

---

## Deploy (servidor)

### Pré-requisitos

- Docker + Docker Compose v2
- Porta 8000 acessível pelos endpoints (ou reverse proxy)

### 1. Clonar e configurar

```bash
git clone https://github.com/icekinggs/sollorm.git
cd sollorm/deploy

cp .env.example .env
```

Edite `.env` com seus valores:

```dotenv
POSTGRES_PASSWORD=<senha forte>
SECRET_KEY=<openssl rand -hex 32>
AGENT_MASTER_TOKEN=<openssl rand -hex 32>
PUBLIC_BACKEND_URL=http://SEU_IP:8000
AGENT_CURRENT_VERSION=v0.5.4
```

> **Importante:** `PUBLIC_BACKEND_URL` deve ser o endereço que os **endpoints conseguem alcançar**. Não use `localhost` se os agentes estiverem em outras máquinas.

### 2. Subir os containers

```bash
docker compose up -d --build
```

A API estará disponível em `http://localhost:8000`. Swagger UI em `/docs`.

### 3. Criar o primeiro usuário admin

```bash
docker compose exec backend python -m scripts.create_user
```

### 4. Acessar o frontend

```bash
cd ../frontend
npm install
npm run dev
```

Acesse `http://localhost:5173`.

---

## Agente

### Instalar

O script de instalação baixa o binário do GitHub Releases, configura o serviço e registra o agente no backend automaticamente.

**Linux (como root):**

```bash
curl -fsSL http://SEU_BACKEND:8000/install/linux | sudo SOLLORM_TOKEN='sollo_xxx' bash
```

**Windows (PowerShell como Administrador):**

```powershell
$env:SOLLORM_TOKEN="sollo_xxx"
iwr -useb http://SEU_BACKEND:8000/install/windows | iex
```

> O token `sollo_xxx` é gerado no painel: **Agentes → Tokens → Novo Token**.

Após ~30 segundos o endpoint aparece no dashboard.

---

### Atualizar

Re-executar o script de instalação é suficiente. Ele para o serviço existente, substitui o binário e reinicia — sem perder o `agent_id` ou o token.

**Linux:**

```bash
curl -fsSL http://SEU_BACKEND:8000/install/linux | sudo SOLLORM_TOKEN='sollo_xxx' bash
```

**Windows (PowerShell como Administrador):**

```powershell
$env:SOLLORM_TOKEN="sollo_xxx"
iwr -useb http://SEU_BACKEND:8000/install/windows | iex
```

---

### Desinstalar

#### Linux

```bash
# Parar e desabilitar o serviço
sudo systemctl stop sollorm-agent
sudo systemctl disable sollorm-agent

# Remover a unit do systemd
sudo rm /etc/systemd/system/sollorm-agent.service
sudo systemctl daemon-reload

# Remover arquivos do agente
sudo rm -rf /opt/sollorm

# Remover usuário de serviço (opcional)
sudo userdel sollorm
```

Tudo em um só comando:

```bash
sudo systemctl stop sollorm-agent && \
sudo systemctl disable sollorm-agent && \
sudo rm /etc/systemd/system/sollorm-agent.service && \
sudo systemctl daemon-reload && \
sudo rm -rf /opt/sollorm && \
sudo userdel sollorm 2>/dev/null; echo "Desinstalado."
```

#### Windows (PowerShell como Administrador)

```powershell
# Parar e remover o serviço
Stop-Service -Name SolloRMMAgent -Force -ErrorAction SilentlyContinue
sc.exe delete SolloRMMAgent

# Remover arquivos
Remove-Item -Recurse -Force "$env:ProgramFiles\SolloRMM"

Write-Host "Agente desinstalado."
```

Após desinstalar, o endpoint continuará aparecendo no dashboard como **offline**. Para removê-lo definitivamente, exclua-o pela interface ou via API:

```bash
curl -X DELETE http://SEU_BACKEND:8000/api/v1/agents/<agent_id> \
  -H "Authorization: Bearer <seu_jwt>"
```

---

### Diagnóstico

**Linux:**

```bash
systemctl status sollorm-agent          # status do serviço
journalctl -u sollorm-agent -f          # logs em tempo real
tail -f /opt/sollorm/agent.log          # log do aplicativo
```

**Windows:**

```powershell
Get-Service SolloRMMAgent               # status
Get-Content "$env:ProgramFiles\SolloRMM\agent.log" -Tail 50  # log
```

---

## Compilar o agente manualmente

Caso prefira compilar a partir do código:

```bash
cd agent
go mod tidy

# Linux amd64
GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o sollorm-agent-linux-amd64 ./cmd/sollorm-agent/

# Linux arm64 (Raspberry Pi, servidores ARM)
GOOS=linux GOARCH=arm64 go build -ldflags="-s -w" -o sollorm-agent-linux-arm64 ./cmd/sollorm-agent/

# Windows amd64
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o sollorm-agent-windows-amd64.exe ./cmd/sollorm-agent/
```

---

## API — Endpoints principais

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | — | Login, retorna JWT |
| `GET` | `/api/v1/auth/me` | JWT | Dados do usuário atual |
| `GET` | `/api/v1/agents` | JWT | Lista agentes |
| `GET` | `/api/v1/agents/{id}` | JWT | Detalhes de um agente |
| `DELETE` | `/api/v1/agents/{id}` | JWT | Remove agente |
| `GET` | `/api/v1/agents/{id}/executions` | JWT | Histórico de execuções |
| `POST` | `/api/v1/agents/{id}/executions` | JWT | Executa script remotamente |
| `GET` | `/api/v1/agent-tokens` | JWT | Lista tokens de agente |
| `POST` | `/api/v1/agent-tokens` | JWT | Cria novo token |
| `DELETE` | `/api/v1/agent-tokens/{id}` | JWT | Revoga token |
| `WS` | `/api/v1/agents/{id}/ssh` | JWT (query) | Terminal SSH nativo |
| `WS` | `/api/v1/agents/{id}/remote-screen` | JWT (query) | Acesso remoto à tela |
| `POST` | `/api/v1/agents/system-info` | Agent Token | Agente envia info de hardware |
| `POST` | `/api/v1/agents/heartbeat` | Agent Token | Agente envia métricas |
| `GET` | `/install/linux` | — | Script de instalação Linux |
| `GET` | `/install/windows` | — | Script de instalação Windows |

Documentação interativa completa em `/docs` (Swagger UI).

---

## Roadmap

- [x] **Fase 1** — Agente envia heartbeat + info de hardware
- [x] **Fase 2A** — Autenticação JWT, modelo de usuários
- [x] **Fase 2B** — Frontend Vue 3 com login + dashboard (PrimeVue)
- [x] **Fase 3** — Execução remota de scripts (PowerShell / Bash / Python)
- [x] **Fase 3B** — Terminal SSH nativo via WebSocket (xterm.js)
- [x] **Fase 5** — Acesso remoto à tela (captura nativa GDI, sem Guacamole, sem senha)
- [x] **Fase 6** — Patch management Windows/Linux (scan + instalação)
- [ ] **Fase 4** — Monitoramento ativo (checks configuráveis + alertas)
- [ ] **Fase 7** — Inventário de software instalado
- [ ] **Fase 8** — Execução agendada (scripts em cron)
- [ ] **Fase 9** — Multi-tenant / multi-organização

---

## Segurança

- Senhas hasheadas com **Argon2**
- Autenticação via **JWT** com expiração configurável
- Tokens de agente separados dos tokens de usuário (prefixo `sollo_`)
- Configuração do agente restrita a root/SYSTEM no endpoint
- 100% self-hosted — nenhum dado sai do seu ambiente
- HTTPS recomendado em produção (reverse proxy com certificado próprio)

---

## Licença

[MIT](LICENSE) — uso livre, sem garantias.

---

> 🚧 **Em desenvolvimento ativo.** A API pode mudar entre versões. Não recomendado para ambientes de produção críticos sem testes prévios.
