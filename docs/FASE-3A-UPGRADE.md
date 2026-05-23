# Fase 3A — Tokens individuais + Instalação pelo Dashboard

Esta é a maior atualização até agora. Mexe em backend, agente e frontend.

## O que muda

### Backend
- Nova tabela `agent_tokens` (com hash, nunca o token em texto puro)
- Endpoints `/api/v1/agent-tokens` (CRUD + revoke)
- Endpoints públicos `/install/windows.ps1` e `/install/linux.sh`
- Auth aceita tokens individuais (`sollo_*`) E master token legado
- Versão da API: `0.3.0`

### Agente (reescrito em pacotes)
- Estrutura modular: `cmd/`, `internal/{config,reporter,service,system}`
- Suporte a Windows Service e systemd via `kardianos/service`
- Lê config de arquivo JSON ao invés de só flags
- Modo `--service` pra rodar como serviço gerenciado

### Frontend
- Nova rota `/tokens` com gestão completa
- Botão "Adicionar agente" abre wizard de 2 passos
- Mostra status do token: Em uso / Aguardando / Revogado / Expirado

### Infra
- `.github/workflows/build-agent.yml` builda binários automaticamente quando você faz push de tag

## Pré-requisitos antes de aplicar

1. **Configurar `public_backend_url` no .env do backend.**
   Os scripts de instalação vão usar essa URL. Como você está em dev,
   pode usar `http://172.16.2.12:8000` (IP da VM Debian acessível pela rede).

2. **GitHub Repo configurado com Actions habilitado** (`icekinggs/sollorm`).

3. **Backup do banco antes de fazer migração:**
   ```bash
   cd ~/projects/sollorm/deploy
   docker compose exec db pg_dump -U sollorm sollorm > ~/backup-pre-fase3a.sql
   ```

## Passo a passo

### 1. Substituir arquivos

A partir da raiz do projeto, copie os arquivos do pacote `sollorm-fase3a.tar.gz`:

```
backend/app/models.py                   (atualiza - adiciona AgentToken)
backend/app/config.py                   (atualiza - new settings)
backend/app/schemas.py                  (atualiza - novos schemas)
backend/app/auth.py                     (atualiza - lookup token individual)
backend/app/main.py                     (atualiza - novos routers)
backend/app/services/__init__.py        (NOVO)
backend/app/services/tokens.py          (NOVO)
backend/app/routers/agents.py           (atualiza - vincula token)
backend/app/routers/agent_tokens.py     (NOVO)
backend/app/routers/install.py          (NOVO)
backend/install_templates/windows.ps1   (NOVO)
backend/install_templates/linux.sh      (NOVO)
backend/Dockerfile                      (atualiza - copia install_templates)

agent/go.mod                            (atualiza - add kardianos/service)
agent/cmd/sollorm-agent/main.go         (REESTRUTURADO)
agent/internal/config/config.go         (NOVO)
agent/internal/system/system.go         (NOVO)
agent/internal/reporter/reporter.go     (NOVO)
agent/internal/service/service.go       (NOVO)
# Apague o antigo agent/main.go - agora vive em agent/cmd/sollorm-agent/main.go
rm agent/main.go

frontend/src/api/agentTokens.js         (NOVO)
frontend/src/views/TokensView.vue       (NOVO)
frontend/src/views/AppLayout.vue        (atualiza - link Tokens)
frontend/src/router/index.js            (atualiza - rota /tokens)
frontend/src/main.js                    (atualiza - Tooltip directive)
frontend/src/components/AddAgentDialog.vue (NOVO)

.github/workflows/build-agent.yml       (NOVO)
```

### 2. Atualizar `.env` do backend

```bash
cd ~/projects/sollorm/deploy
nano .env
```

Adicione/confirme:

```bash
POSTGRES_PASSWORD=...        # já existe
SECRET_KEY=...               # já existe
AGENT_MASTER_TOKEN=...       # já existe - será mantido como legado por enquanto

# NOVOS:
PUBLIC_BACKEND_URL=http://172.16.2.12:8000
GITHUB_REPO=icekinggs/sollorm
AGENT_CURRENT_VERSION=v0.3.0
ALLOW_LEGACY_MASTER_TOKEN=true
```

Atualize o `docker-compose.yml` pra passar essas variáveis:

```yaml
backend:
  environment:
    DATABASE_URL: ...
    REDIS_URL: ...
    SECRET_KEY: ...
    AGENT_MASTER_TOKEN: ...
    PUBLIC_BACKEND_URL: ${PUBLIC_BACKEND_URL:-http://172.16.2.12:8000}
    GITHUB_REPO: ${GITHUB_REPO:-icekinggs/sollorm}
    AGENT_CURRENT_VERSION: ${AGENT_CURRENT_VERSION:-v0.3.0}
    ALLOW_LEGACY_MASTER_TOKEN: ${ALLOW_LEGACY_MASTER_TOKEN:-true}
```

### 3. Rebuildar e subir

```bash
cd ~/projects/sollorm/deploy
docker compose down
docker compose up -d --build
docker compose logs -f backend
```

Aguarde "Application startup complete". As tabelas novas (`agent_tokens`) serão criadas automaticamente.

### 4. Validar backend

```bash
# Health check
curl http://localhost:8000/health

# Login pra pegar JWT (use seu admin)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"SUA_SENHA"}' | jq -r '.access_token')

# Listar tokens (deve estar vazio na primeira vez)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/agent-tokens | jq

# Criar token de teste
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"teste-linux","platform_hint":"linux"}' \
  http://localhost:8000/api/v1/agent-tokens | jq

# Testar script público (não precisa de auth)
curl http://localhost:8000/install/linux.sh | head -30
```

### 5. Testar via frontend

1. Acesse http://localhost:5173
2. Login com seu admin
3. Clique em **"Tokens"** no menu
4. Clique em **"Adicionar agente"**
5. Preencha nome, escolha plataforma, gere o token
6. Copie o token e o one-liner

### 6. Build do binário do agente

#### Opção A: GitHub Actions (recomendado pra produção)

```bash
cd ~/projects/sollorm
git add .
git commit -m "feat: fase 3A - tokens individuais + instalação pelo dashboard"
git push

# Cria tag pra disparar o build
git tag v0.3.0
git push origin v0.3.0
```

Vai pra **Actions** no GitHub e acompanha o build. Quando terminar, aparece na seção **Releases**.

#### Opção B: Build local (pra testar agora)

```bash
cd ~/projects/sollorm/agent
go mod tidy

# Linux
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o sollorm-agent-linux-amd64 ./cmd/sollorm-agent

# Windows
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -o sollorm-agent-windows-amd64.exe ./cmd/sollorm-agent

# Testar localmente (modo foreground)
./sollorm-agent-linux-amd64 --server http://localhost:8000 --token sollo_xxxxxxxx
```

⚠️ Se você buildar local, os scripts `install/*.sh` não vão funcionar (porque buscam o release no GitHub).
Pra testar end-to-end, use a Opção A.

### 7. Testar instalação real (após release no GitHub)

Numa máquina-alvo (pode ser uma VM, contêiner, ou outro PC da rede):

**Linux:**
```bash
# Pega o oneliner do dashboard (depois de criar token)
curl -fsSL http://172.16.2.12:8000/install/linux.sh | sudo SOLLORM_TOKEN='sollo_xxx' SOLLORM_SERVER='http://172.16.2.12:8000' bash
```

**Windows (PowerShell como admin):**
```powershell
$env:SOLLORM_TOKEN='sollo_xxx'; $env:SOLLORM_SERVER='http://172.16.2.12:8000'; iwr -useb http://172.16.2.12:8000/install/windows.ps1 | iex
```

Em ~30 segundos o agente aparece no dashboard.

## Troubleshooting

### Backend não sobe
- Verifique se `install_templates/` está no Dockerfile (deve estar)
- Logs: `docker compose logs backend --tail 50`

### "Token inválido" no agente
- Confirme que o token começa com `sollo_`
- Confira que não foi revogado: liste tokens no dashboard

### Script de install retorna 404
- Confira `PUBLIC_BACKEND_URL` no .env
- Confira que `install/` está acessível: `curl http://localhost:8000/install/linux.sh`

### Build do GitHub Actions falha
- Confira que o arquivo `go.mod` está em `agent/go.mod`
- Verifique secrets/permissões em Settings → Actions

### Agente Windows: serviço não inicia
- Verifique log: `Get-Content "C:\Program Files\SolloRMM\agent.log" -Tail 50`
- Tente rodar em foreground: `& "C:\Program Files\SolloRMM\sollorm-agent.exe" --config "C:\Program Files\SolloRMM\config.json"`

### Agente Linux: serviço não inicia
- Logs: `journalctl -u sollorm-agent -n 50`
- Permissões: `ls -la /opt/sollorm/`
- Teste em foreground: `sudo -u sollorm /opt/sollorm/sollorm-agent --config /opt/sollorm/config.json`

## Commit no Git

```bash
cd ~/projects/sollorm
git add .
git status  # confira que .env NÃO está sendo trackado
git commit -m "feat: Fase 3A - tokens individuais e instalação via dashboard

Backend:
- Tabela agent_tokens com hash SHA-256
- Endpoints CRUD para tokens (criar, listar, revogar, apagar)
- Endpoints públicos /install/windows.ps1 e /install/linux.sh
- Auth aceita token individual sollo_* e master token (legado)

Agent:
- Reestruturação em pacotes modulares (cmd/, internal/)
- Suporte a Windows Service e systemd
- Lê config de arquivo JSON
- Modo --service para serviço gerenciado

Frontend:
- Nova rota /tokens com listagem
- Wizard de criação com one-liner pronto
- Status do token: em uso, aguardando, revogado, expirado

CI:
- Workflow build-agent.yml para releases automáticos"
```

## Próximos passos (Fase 3B em diante)

- Vincular agentes existentes a tokens individuais (migração automática)
- Desabilitar master token legado quando todos migrarem
- Auto-update do agente quando nova release sair
- Execução remota de scripts (Fase 4)
- Acesso remoto via MeshCentral (Fase 5)
