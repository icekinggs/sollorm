# Fase 2B — Frontend Vue 3 + PrimeVue

## O que muda

- Pasta `frontend/` com aplicação Vue 3 completa
- `docker-compose.yml` agora sobe 4 serviços (db, redis, backend, **frontend**)
- Frontend acessível em http://localhost:5173

## Stack do frontend

- **Vue 3** com Composition API
- **Vue Router 4** para navegação
- **Pinia** para estado global (auth)
- **PrimeVue 4** + tema Aura (componentes UI)
- **Axios** com interceptors para JWT
- **Vite** como bundler
- **date-fns** para formatação de datas em pt-BR

## Passo a passo de upgrade

### 1. Copiar arquivos novos

Extraia o pacote `sollorm-fase2b.tar.gz` na raiz do projeto. Vai criar/atualizar:

```
frontend/                           (toda a pasta - NOVA)
├── package.json
├── vite.config.js
├── index.html
├── Dockerfile.dev
├── .dockerignore
├── public/
│   └── favicon.svg
└── src/
    ├── main.js
    ├── App.vue
    ├── api/
    ├── stores/
    ├── views/
    ├── router/
    ├── composables/
    └── assets/

deploy/
└── docker-compose.yml              (atualizado - inclui frontend)
```

### 2. Subir o stack atualizado

```bash
cd ~/projects/sollorm/deploy

# Para todos os containers
docker compose down

# Sobe tudo (vai buildar a imagem do frontend na primeira vez)
docker compose up -d --build

# Acompanha os logs do frontend
docker compose logs -f frontend
```

A primeira build do frontend leva 1-3 minutos (npm install). Aguarde a mensagem:

```
VITE v6.0.5  ready in XXX ms

➜  Local:   http://localhost:5173/
➜  Network: http://172.x.x.x:5173/
```

### 3. Acessar o frontend

Abra no navegador: **http://localhost:5173**

Você deve ver a tela de login do SolloRMM.

### 4. Fazer login

Use as credenciais do admin que você criou com `scripts/create_user`.

Após login, você é redirecionado pro Dashboard com lista de agentes.

### 5. Funcionalidades disponíveis

**Dashboard:**
- 3 cards de métricas (Total, Online, Offline)
- Tabela com todos os agentes
- Refresh automático a cada 30s
- Botão de refresh manual
- Click em uma linha abre o detalhe do agente

**Detalhe do agente:**
- Métricas atuais (CPU, RAM, Disco, Uptime) com barras coloridas
- Informações completas de hardware
- Histórico dos últimos 20 heartbeats
- Botão voltar pro dashboard

**Header:**
- Logo + link pro Dashboard
- Toggle de tema claro/escuro (sol/lua)
- Menu de usuário com logout

**Login:**
- Validação de campos
- Toggle de tema na tela de login também
- Tratamento de erros (credenciais inválidas, sem conexão, etc)

## Troubleshooting

### "Cannot connect to backend"
Verifique que o backend está rodando:
```bash
docker compose ps
curl http://localhost:8000/health
```

### Frontend mostra tela branca
Abra o DevTools (F12) e veja o Console. Geralmente é erro de import. Cole o erro aqui.

### Build do frontend muito lento
Normal na primeira vez (instala ~200MB de node_modules). Builds seguintes usam cache e são instantâneas.

### "EADDRINUSE: address already in use 0.0.0.0:5173"
Algo já está usando a porta. Identifica e mata:
```bash
sudo lsof -i :5173
```

### Login retorna "Network Error"
O proxy do Vite está apontando pra `http://backend:8000` (nome do serviço Docker). Confirme que ambos estão na mesma network:
```bash
docker compose ps
docker network inspect deploy_default
```

### Tema não persiste após reload
LocalStorage do navegador pode estar bloqueado (modo anônimo). Use janela normal.

## Estrutura de pastas explicada

```
src/
├── main.js                 # Entry point - inicializa Vue/Pinia/Router/PrimeVue
├── App.vue                 # Raiz - só router-view + Toast
├── api/                    # Cliente HTTP e funções por recurso
│   ├── client.js           # Axios com interceptors JWT
│   ├── auth.js             # login, /me
│   └── agents.js           # list, get, heartbeats
├── stores/
│   └── auth.js             # Pinia store de autenticação
├── router/
│   └── index.js            # Rotas + guards de autenticação
├── views/                  # Páginas (associadas a rotas)
│   ├── AppLayout.vue       # Layout autenticado (header + slot)
│   ├── LoginView.vue       # Tela de login
│   ├── DashboardView.vue   # Lista de agentes
│   └── AgentDetailView.vue # Detalhe de um agente
├── composables/
│   ├── useTheme.js         # Toggle dark/light
│   └── useFormatters.js    # Formatadores reutilizáveis
└── assets/
    └── main.css            # CSS global
```

## Próximos passos (Fase 2C)

- Gráfico de linha com histórico de heartbeats (Chart.js ou ApexCharts)
- Tela de gerenciamento de usuários (admin only)
- Filtros e busca na tabela
- Tela de configurações do sistema
