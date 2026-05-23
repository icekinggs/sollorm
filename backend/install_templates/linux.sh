#!/usr/bin/env bash
set -euo pipefail

# ============================================
# SolloRMM Agent Installer for Linux
# ============================================

SOLLORM_SERVER="${SOLLORM_SERVER:-{{SOLLORM_SERVER}}}"
SOLLORM_TOKEN="${SOLLORM_TOKEN:-}"
MESHCENTRAL_AGENT_URL="${MESHCENTRAL_AGENT_URL:-{{MESHCENTRAL_AGENT_LINUX_URL}}}"
GITHUB_REPO="{{GITHUB_REPO}}"
AGENT_VERSION="{{AGENT_VERSION}}"

INSTALL_DIR="/opt/sollorm"
BINARY_NAME="sollorm-agent"
SERVICE_NAME="sollorm-agent"
CONFIG_PATH="${INSTALL_DIR}/config.json"
LOG_PATH="${INSTALL_DIR}/agent.log"

# Cores (só se for terminal)
if [ -t 1 ]; then
    C_CYAN='\033[1;36m'
    C_GREEN='\033[1;32m'
    C_RED='\033[1;31m'
    C_YELLOW='\033[1;33m'
    C_RESET='\033[0m'
else
    C_CYAN=''; C_GREEN=''; C_RED=''; C_YELLOW=''; C_RESET=''
fi

step()  { echo ""; echo -e "${C_CYAN}==> $*${C_RESET}"; }
ok()    { echo -e "  ${C_GREEN}[OK]${C_RESET} $*"; }
err()   { echo -e "  ${C_RED}[ERRO]${C_RESET} $*" >&2; }
warn()  { echo -e "  ${C_YELLOW}[AVISO]${C_RESET} $*"; }

echo ""
echo "  SolloRMM Agent Installer for Linux"
echo "  Server: ${SOLLORM_SERVER}"
echo "  Version: ${AGENT_VERSION}"
echo ""

# Validar root
if [ "$(id -u)" -ne 0 ]; then
    err "Este script precisa rodar como root (use sudo)."
    exit 1
fi

# Validar token
if [ -z "${SOLLORM_TOKEN}" ]; then
    err "Variável SOLLORM_TOKEN não definida."
    echo ""
    echo "  Uso correto:"
    echo "    curl -fsSL URL | sudo SOLLORM_TOKEN='sollo_xxx' bash"
    exit 1
fi

case "${SOLLORM_TOKEN}" in
    sollo_*) ;;
    *) err "Token inválido - deve começar com 'sollo_'"; exit 1 ;;
esac

# Detectar arquitetura
ARCH="$(uname -m)"
case "${ARCH}" in
    x86_64|amd64) ARCH_TAG="amd64" ;;
    aarch64|arm64) ARCH_TAG="arm64" ;;
    armv7l) ARCH_TAG="arm" ;;
    *) err "Arquitetura não suportada: ${ARCH}"; exit 1 ;;
esac

# Detectar systemd
if ! command -v systemctl >/dev/null 2>&1; then
    err "systemctl não encontrado. Este script suporta apenas sistemas com systemd."
    exit 1
fi

# Validar curl
if ! command -v curl >/dev/null 2>&1; then
    err "curl não encontrado. Instale antes de prosseguir."
    exit 1
fi

step "Instalando MeshCentral Agent"
if [ -n "${MESHCENTRAL_AGENT_URL}" ]; then
    MESH_INSTALLER="/tmp/sollorm-meshinstall.sh"
    if curl -fsSL --connect-timeout 30 -o "${MESH_INSTALLER}" "${MESHCENTRAL_AGENT_URL}"; then
        chmod 700 "${MESH_INSTALLER}"
        if bash "${MESH_INSTALLER}"; then
            ok "MeshCentral Agent instalado"
        else
            warn "MeshCentral Agent falhou. O SolloRMM Agent continuará a instalação."
        fi
        rm -f "${MESH_INSTALLER}"
    else
        warn "Não foi possível baixar o MeshCentral Agent. Verifique MESHCENTRAL_AGENT_URL."
    fi
else
    warn "MESHCENTRAL_AGENT_URL não configurado. Pulando MeshCentral Agent."
fi

step "Verificando instalação anterior"
if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    echo "  Serviço existente encontrado, parando..."
    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
fi

step "Criando diretório de instalação"
mkdir -p "${INSTALL_DIR}"
ok "${INSTALL_DIR}"

step "Baixando binário do agente"
DOWNLOAD_URL="https://github.com/${GITHUB_REPO}/releases/download/${AGENT_VERSION}/sollorm-agent-linux-${ARCH_TAG}"
echo "  URL: ${DOWNLOAD_URL}"

BINARY_PATH="${INSTALL_DIR}/${BINARY_NAME}"
BINARY_TMP="${BINARY_PATH}.download"
rm -f "${BINARY_TMP}"

if ! curl -fsSL --connect-timeout 30 -o "${BINARY_TMP}" "${DOWNLOAD_URL}"; then
    err "Falha ao baixar binário."
    echo ""
    echo "  Verifique se a release ${AGENT_VERSION} existe no GitHub:"
    echo "  https://github.com/${GITHUB_REPO}/releases"
    rm -f "${BINARY_TMP}"
    exit 1
fi

mv -f "${BINARY_TMP}" "${BINARY_PATH}"
chmod 755 "${BINARY_PATH}"
ok "Binário salvo em ${BINARY_PATH}"

step "Salvando configuração"
cat > "${CONFIG_PATH}" <<EOF
{
  "server": "${SOLLORM_SERVER}",
  "token": "${SOLLORM_TOKEN}"
}
EOF
chmod 600 "${CONFIG_PATH}"
ok "Config protegido (somente root pode ler)"

# Criar usuário dedicado se não existir
step "Configurando usuário do serviço"
if ! id -u sollorm >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin sollorm
    ok "Usuário 'sollorm' criado"
else
    ok "Usuário 'sollorm' já existe"
fi

# Permissões: sollorm precisa ler o config e escrever no log
chown -R sollorm:sollorm "${INSTALL_DIR}"
chmod 700 "${INSTALL_DIR}"
chmod 600 "${CONFIG_PATH}"

step "Criando unidade systemd"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=SolloRMM monitoring agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=sollorm
Group=sollorm
ExecStart=${BINARY_PATH} --config ${CONFIG_PATH} --service
Restart=always
RestartSec=10
StandardOutput=append:${LOG_PATH}
StandardError=append:${LOG_PATH}

# Hardening básico
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${INSTALL_DIR}
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

ok "Unit criada em /etc/systemd/system/${SERVICE_NAME}.service"

step "Habilitando e iniciando o serviço"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}" >/dev/null 2>&1
systemctl start "${SERVICE_NAME}"
sleep 3

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    ok "Serviço ${SERVICE_NAME} rodando"
else
    err "Serviço não está rodando."
    echo ""
    echo "  Diagnóstico:"
    echo "    systemctl status ${SERVICE_NAME}"
    echo "    journalctl -u ${SERVICE_NAME} -n 50"
    echo "    cat ${LOG_PATH}"
    exit 1
fi

echo ""
echo -e "  ${C_GREEN}Instalação concluída!${C_RESET}"
echo ""
echo "  O agente está rodando como serviço systemd."
echo "  Em ~30 segundos ele aparecerá no dashboard."
echo ""
echo "  Comandos úteis:"
echo "    systemctl status ${SERVICE_NAME}     # ver status"
echo "    systemctl stop ${SERVICE_NAME}       # parar"
echo "    systemctl start ${SERVICE_NAME}      # iniciar"
echo "    journalctl -u ${SERVICE_NAME} -f     # acompanhar log"
echo "    tail -f ${LOG_PATH}                  # log do app"
echo ""
