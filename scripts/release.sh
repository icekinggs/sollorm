#!/usr/bin/env bash
# Cria uma release do SolloRMM no GitHub.
# Uso: ./scripts/release.sh v0.7.0 "Descrição da release"
# Requer: gh CLI autenticado, git, go
set -euo pipefail

VERSION="${1:?Uso: $0 <versao> [descricao]}"
NOTES="${2:-Release $VERSION}"
AGENT_DIR="agent"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo 'icekinggs/sollorm')"

echo "==> Buildando binários do agente $VERSION..."

cd "$AGENT_DIR"
GOOS=linux   GOARCH=amd64 go build -ldflags="-s -w" -o sollorm-agent-linux-amd64   ./cmd/sollorm-agent/
GOOS=linux   GOARCH=arm64 go build -ldflags="-s -w" -o sollorm-agent-linux-arm64   ./cmd/sollorm-agent/
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o sollorm-agent-windows-amd64.exe ./cmd/sollorm-agent/
cd ..

echo "==> Criando release $VERSION no GitHub..."
gh release create "$VERSION" \
  --title "$VERSION" \
  --notes "$NOTES" \
  agent/sollorm-agent-linux-amd64 \
  agent/sollorm-agent-linux-arm64 \
  agent/sollorm-agent-windows-amd64.exe

echo ""
echo "✅ Release $VERSION publicada!"
echo ""
echo "Agora atualize deploy/.env:"
echo "  AGENT_CURRENT_VERSION=$VERSION"
echo ""
echo "E reinicie o backend (SEM rebuild):"
echo "  docker compose -f deploy/docker-compose.yml up -d backend"
