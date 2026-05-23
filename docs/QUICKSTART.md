# Guia de início rápido — Fase 1

Vamos colocar o backend rodando na VM Debian e o agente rodando numa máquina de teste.

## Parte 1 — Subir o backend na VM Debian

### Pré-requisitos

Na sua VM Debian (172.16.2.12):

```bash
# Instalar Docker + Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Saia e entre de novo no SSH para o grupo valer

# Verificar
docker --version
docker compose version
```

### Subir o stack

```bash
# Clonar o projeto (você vai criar um repo Git e clonar)
cd ~
git clone <seu-repo> sollorm
cd sollorm/deploy

# Configurar segredos
cp .env.example .env

# Gerar tokens fortes
echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)" > .env
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
echo "AGENT_MASTER_TOKEN=$(openssl rand -hex 32)" >> .env

# IMPORTANTE: anote o AGENT_MASTER_TOKEN, você vai precisar dele pro agente
cat .env

# Subir tudo
docker compose up -d --build

# Acompanhar logs
docker compose logs -f backend
```

### Validar

```bash
# Health check
curl http://localhost:8000/health
# Esperado: {"status":"healthy"}

# Documentação interativa da API
# Abra no navegador: http://172.16.2.12:8000/docs
```

## Parte 2 — Compilar e rodar o agente

### Opção A — Compilar na própria VM (Linux)

```bash
# Instalar Go
sudo apt install -y golang-go

cd ~/sollorm/agent
go mod tidy
go build -o sollorm-agent

# Rodar (substitua o TOKEN pelo gerado acima)
./sollorm-agent \
  --server http://localhost:8000 \
  --token SEU_AGENT_MASTER_TOKEN
```

### Opção B — Cross-compilar para Windows

Na VM Debian:

```bash
cd ~/sollorm/agent
GOOS=windows GOARCH=amd64 go build -o sollorm-agent.exe
```

Copie `sollorm-agent.exe` para uma máquina Windows e execute (cmd como admin):

```cmd
sollorm-agent.exe --server http://172.16.2.12:8000 --token SEU_AGENT_MASTER_TOKEN
```

### O que esperar

O agente vai logar:

```
SolloRMM Agent v0.1.0 iniciando...
Agent ID: 550e8400-e29b-41d4-a716-446655440000
Servidor: http://172.16.2.12:8000
Enviando system info: NOTEBOOK-01 (Windows 11)
Heartbeat: CPU=12.3% RAM=45.7% DISK=62.1%
```

A cada 60 segundos um novo heartbeat será enviado.
A cada 30 minutos as info de sistema serão atualizadas.

## Parte 3 — Validar no backend

### Via API (curl)

```bash
# Listar agentes registrados
curl http://172.16.2.12:8000/api/v1/agents | jq

# Ver detalhes de um agente
curl http://172.16.2.12:8000/api/v1/agents/AGENT_ID_AQUI | jq

# Ver heartbeats recentes
curl http://172.16.2.12:8000/api/v1/agents/AGENT_ID_AQUI/heartbeats?limit=10 | jq
```

### Via interface Swagger

Abra http://172.16.2.12:8000/docs no navegador.

## Troubleshooting comum

### Backend não sobe
```bash
docker compose logs backend
# Verifica erros de conexão com banco
```

### Agente erro "connection refused"
- Verifica se a VM responde: `ping 172.16.2.12`
- Verifica se a porta 8000 está aberta: `telnet 172.16.2.12 8000`
- Firewall do Debian: `sudo ufw status` — pode precisar liberar a porta

### Agente erro 401
- Token errado. Confira que o token passado em `--token` é exatamente o `AGENT_MASTER_TOKEN` do `.env`

### "database does not exist"
- Container do banco subiu antes do init. Reset:
```bash
docker compose down -v
docker compose up -d --build
```

## Próximos passos

Quando essa Fase 1 estiver funcionando (agente reportando, backend recebendo, dados aparecendo na API):

- **Fase 2**: Frontend Vue pra visualizar
- **Fase 3**: Execução de scripts remotos
- **Fase 4**: Alertas e monitoramento
