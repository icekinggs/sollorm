#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

# Garante saída UTF-8 no console (resolve "==> Verificando instala????o")
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$SOLLORM_SERVER = if ($env:SOLLORM_SERVER) { $env:SOLLORM_SERVER } else { "{{SOLLORM_SERVER}}" }
$SOLLORM_TOKEN = $env:SOLLORM_TOKEN
$MESHCENTRAL_AGENT_URL = if ($env:MESHCENTRAL_AGENT_URL) { $env:MESHCENTRAL_AGENT_URL } else { "{{MESHCENTRAL_AGENT_WINDOWS_URL}}" }
$GITHUB_REPO = "{{GITHUB_REPO}}"
$AGENT_VERSION = "{{AGENT_VERSION}}"

$INSTALL_DIR = "$env:ProgramFiles\SolloRMM"
$BINARY_NAME = "sollorm-agent.exe"
$SERVICE_NAME = "SolloRMMAgent"
$SERVICE_DISPLAY = "SolloRMM Agent"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-Err($msg) {
    Write-Host "  [ERRO] $msg" -ForegroundColor Red
}

Write-Host ""
Write-Host "  SolloRMM Agent Installer for Windows" -ForegroundColor White
Write-Host "  Server: $SOLLORM_SERVER" -ForegroundColor Gray
Write-Host "  Version: $AGENT_VERSION" -ForegroundColor Gray
Write-Host ""

# Validar token
if ([string]::IsNullOrEmpty($SOLLORM_TOKEN)) {
    Write-Err "Variável SOLLORM_TOKEN não definida."
    Write-Host ""
    Write-Host "  Uso correto:" -ForegroundColor Yellow
    Write-Host '    $env:SOLLORM_TOKEN="sollo_xxx"; iwr -useb URL | iex' -ForegroundColor Gray
    exit 1
}

if (-not $SOLLORM_TOKEN.StartsWith("sollo_")) {
    Write-Err "Token inválido - deve começar com 'sollo_'"
    exit 1
}

Write-Step "Instalando MeshCentral Agent"
if (-not [string]::IsNullOrWhiteSpace($MESHCENTRAL_AGENT_URL)) {
    $meshInstaller = Join-Path $env:TEMP "sollorm-meshagent.exe"
    try {
        Invoke-WebRequest -Uri $MESHCENTRAL_AGENT_URL -OutFile $meshInstaller -UseBasicParsing
        Start-Process -FilePath $meshInstaller -ArgumentList "-fullinstall" -Wait
        Write-Ok "MeshCentral Agent instalado"
    } catch {
        Write-Host "  [AVISO] MeshCentral Agent falhou: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "  O SolloRMM Agent continuará a instalação." -ForegroundColor Yellow
    }
} else {
    Write-Host "  [AVISO] MESHCENTRAL_AGENT_URL não configurado. Pulando MeshCentral Agent." -ForegroundColor Yellow
}

# Parar serviço se já existe (atualização)
Write-Step "Verificando instalação anterior"
$existing = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  Serviço existente encontrado, parando..."
    Stop-Service -Name $SERVICE_NAME -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Criar diretório
Write-Step "Criando diretório de instalação"
if (-not (Test-Path $INSTALL_DIR)) {
    New-Item -ItemType Directory -Path $INSTALL_DIR -Force | Out-Null
}
Write-Ok $INSTALL_DIR

# Detectar arquitetura
$arch = "amd64"
if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { $arch = "arm64" }

# Download do binário do GitHub Releases
Write-Step "Baixando binário do agente"
$downloadUrl = "https://github.com/$GITHUB_REPO/releases/download/$AGENT_VERSION/sollorm-agent-windows-$arch.exe"
$binaryPath = Join-Path $INSTALL_DIR $BINARY_NAME

Write-Host "  URL: $downloadUrl"

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $downloadUrl -OutFile $binaryPath -UseBasicParsing
    Write-Ok "Binário salvo em $binaryPath"
} catch {
    Write-Err "Falha ao baixar binário: $($_.Exception.Message)"
    Write-Host ""
    Write-Host "  Verifique se a release $AGENT_VERSION existe no GitHub:" -ForegroundColor Yellow
    Write-Host "  https://github.com/$GITHUB_REPO/releases" -ForegroundColor Yellow
    exit 1
}

# Salvar config (token + server URL)
Write-Step "Salvando configuração"
$configPath = Join-Path $INSTALL_DIR "config.json"
$config = @{
    server = $SOLLORM_SERVER
    token = $SOLLORM_TOKEN
} | ConvertTo-Json

# IMPORTANTE: usar UTF-8 SEM BOM. O Set-Content -Encoding UTF8 do PS5 adiciona BOM,
# que quebra o parser JSON do Go. Por isso usamos WriteAllText do .NET diretamente.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($configPath, $config, $utf8NoBom)

# Permissões: só Administradores e SYSTEM podem ler/escrever o config
# Usando SID ao invés de nome para funcionar em Windows de qualquer idioma
try {
    $adminSid = New-Object System.Security.Principal.SecurityIdentifier("S-1-5-32-544")
    $systemSid = New-Object System.Security.Principal.SecurityIdentifier("S-1-5-18")

    $acl = Get-Acl $configPath
    $acl.SetAccessRuleProtection($true, $false)

    $ruleAdmin = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $adminSid, "FullControl", "Allow"
    )
    $acl.AddAccessRule($ruleAdmin)

    $ruleSystem = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $systemSid, "FullControl", "Allow"
    )
    $acl.AddAccessRule($ruleSystem)

    Set-Acl -Path $configPath -AclObject $acl
    Write-Ok "Config protegido (apenas Admin e SYSTEM)"
} catch {
    Write-Host "  [AVISO] Não foi possível restringir permissões do config: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Criar/atualizar serviço Windows
Write-Step "Configurando Windows Service"

if ($existing) {
    # Remove serviço antigo pra recriar limpo
    sc.exe delete $SERVICE_NAME | Out-Null
    Start-Sleep -Seconds 2
}

$binaryArgs = "--config `"$configPath`" --service"
$binPathWithArgs = "`"$binaryPath`" $binaryArgs"

New-Service `
    -Name $SERVICE_NAME `
    -DisplayName $SERVICE_DISPLAY `
    -Description "SolloRMM monitoring agent" `
    -BinaryPathName $binPathWithArgs `
    -StartupType Automatic | Out-Null

# Configura restart automático em caso de falha
sc.exe failure $SERVICE_NAME reset= 86400 actions= restart/5000/restart/10000/restart/30000 | Out-Null

Write-Ok "Serviço $SERVICE_NAME criado"

# Iniciar
Write-Step "Iniciando o serviço"
Start-Service -Name $SERVICE_NAME
Start-Sleep -Seconds 3

$svc = Get-Service -Name $SERVICE_NAME
if ($svc.Status -eq "Running") {
    Write-Ok "Serviço rodando"
} else {
    Write-Err "Serviço não está rodando. Status: $($svc.Status)"
    Write-Host "  Veja o log em: $INSTALL_DIR\agent.log" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "  Instalacao concluida!" -ForegroundColor Green
Write-Host ""
Write-Host "  O agente esta rodando como servico do Windows." -ForegroundColor White
Write-Host "  Em ~30 segundos ele aparecera no dashboard." -ForegroundColor White
Write-Host ""
Write-Host "  Comandos uteis:" -ForegroundColor Gray
Write-Host "    Get-Service $SERVICE_NAME       # ver status" -ForegroundColor Gray
Write-Host "    Stop-Service $SERVICE_NAME      # parar" -ForegroundColor Gray
Write-Host "    Start-Service $SERVICE_NAME     # iniciar" -ForegroundColor Gray
Write-Host "    Get-Content '$INSTALL_DIR\agent.log' -Tail 50  # log" -ForegroundColor Gray
Write-Host ""
