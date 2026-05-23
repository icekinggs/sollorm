# Fase 2A — Backend com autenticação

## O que muda

- Tabela `users` para usuários humanos
- Endpoints `/api/v1/auth/login` e `/api/v1/auth/me`
- Rotas `GET /agents` agora exigem JWT (não acesso anônimo)
- Rotas do agente (`/heartbeat`, `/system-info`) continuam com token Bearer master
- CORS configurado pro Vite dev server (porta 5173)
- Bug do `is_online` corrigido (timezone aware)
- Bug do `cpu_cores` corrigido no agente

## Passo a passo de upgrade

### 1. Substituir os arquivos

A partir da raiz do seu projeto `~/projects/sollorm`, substitua os seguintes arquivos pelos novos:

```
backend/app/models.py        (adiciona User)
backend/app/security.py      (NOVO - hash + JWT)
backend/app/auth.py          (atualiza - agora exporta get_current_user)
backend/app/schemas.py       (adiciona LoginRequest, TokenResponse, UserOut, UserCreate)
backend/app/config.py        (atualiza CORS)
backend/app/main.py          (inclui novo router de auth)
backend/app/routers/auth.py  (NOVO - login + me)
backend/app/routers/agents.py (atualiza - JWT em rotas de listagem)
backend/scripts/__init__.py  (NOVO)
backend/scripts/create_user.py (NOVO - bootstrap admin)
backend/Dockerfile           (atualiza - copia scripts/)

agent/main.go                (corrige cpu_cores)
```

### 2. Rebuildar o backend

```bash
cd ~/projects/sollorm/deploy
docker compose down
docker compose up -d --build
docker compose logs -f backend
```

Aguarde a mensagem de "Application startup complete".

### 3. Criar o primeiro usuário admin

```bash
docker compose exec backend python -m scripts.create_user
```

Vai pedir interativamente: username, email, nome, senha (mínimo 8 chars) e se é admin (responda "s").

### 4. Testar o login

```bash
# Substitua admin/sua_senha pelos valores que você criou
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"sua_senha_aqui"}'
```

Resposta esperada:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": "uuid-aqui",
    "username": "admin",
    "email": "...",
    "is_superuser": true,
    ...
  }
}
```

### 5. Testar endpoint protegido

```bash
# Cola o access_token do passo anterior aqui
TOKEN="eyJhbGciOiJIUzI1NiIs..."

# Sem token - deve dar 401
curl http://localhost:8000/api/v1/agents

# Com token - deve listar os agentes
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/agents | jq

# Ver o próprio user
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me | jq
```

### 6. Recompilar o agente (correção do cpu_cores)

```bash
cd ~/projects/sollorm/agent

# Mata o agente antigo (Ctrl+C no terminal dele se estiver rodando)
go build -o sollorm-agent

# Roda de novo
./sollorm-agent --server http://localhost:8000 --token SEU_AGENT_MASTER_TOKEN
```

Deve aparecer no log: `Enviando system info: ICEKING (...) - 16 cores`

### 7. Validar tudo via Swagger

Abra http://localhost:8000/docs

1. Clique no botão verde "Authorize" no canto superior direito
2. Em **OAuth2PasswordBearer**, use seu username/senha
3. Agora os endpoints protegidos têm o cadeado liberado
4. Teste `GET /api/v1/agents` — deve retornar os agentes com `cpu_cores: 16` e `is_online: true`

## Troubleshooting

### "Application startup failed" após rebuild
Verifique se a pasta `backend/scripts/` existe e tem `__init__.py` (mesmo vazio).

### Erro de import "no module named 'jose'"
O pip já está em requirements.txt. Force o rebuild:
```bash
docker compose build --no-cache backend
docker compose up -d
```

### Login retornando 401 mesmo com senha certa
Confira se você não digitou senha errada no create_user (use --no-cache se duvidar do cache). Pra resetar:
```bash
docker compose exec backend python -m scripts.create_user
# usa outro username, ou apague o user via SQL
```

### "is_online" ainda falso
Confirme que o agente está rodando e mandando heartbeats nos últimos 2 minutos. Olhe o log do backend:
```bash
docker compose logs -f backend
# Deve aparecer "POST /api/v1/agents/heartbeat HTTP/1.1" 200 OK
```

## Commit no Git

```bash
cd ~/projects/sollorm
git add .
git commit -m "feat(backend): adiciona autenticação JWT

- Modelo User + hash Argon2
- Endpoints /auth/login e /auth/me
- Proteção JWT nas rotas de listagem
- Script CLI para criar admin inicial
- Token de agente separado do JWT humano
- CORS configurado pro Vite

fix(backend): corrige is_online com timezone aware
fix(agent): corrige cpu_cores usando runtime.NumCPU"
```

## Próximos passos

Quando tudo isso estiver funcionando, na próxima sessão entregaremos a **Fase 2B**:
- Frontend Vue 3 + Vite + PrimeVue
- Tela de login
- Dashboard listando agentes
- Toggle de tema claro/escuro
- Detalhe de agente com gráficos de heartbeats
