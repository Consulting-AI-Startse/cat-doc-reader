# ============================================================================
# start-local.ps1  -  Sobe todo o ambiente local do CAT Document Reader
# Uso:  .\start-local.ps1            (normal - mantem dados)
#       .\start-local.ps1 -CleanBlob (limpa so o Azurite, ex: crash de GC)
#       .\start-local.ps1 -Fresh     (RESET TOTAL: limpa Azurite + zera o banco)
# Cada servico abre em sua propria janela. Para derrubar tudo: .\stop-local.ps1
# ============================================================================

param(
    [switch]$CleanBlob,
    [switch]$Fresh
)

$ErrorActionPreference = "Stop"

# -Fresh implica limpar o blob tambem
if ($Fresh) { $CleanBlob = $true }

# --- Configuracao (ajuste PG se sua pasta do Postgres for outra) ---
$ROOT     = $PSScriptRoot
$PG       = "$env:LOCALAPPDATA\pgsql\pgsql\bin"
$PGDATA   = "$env:USERPROFILE\pgdata"
$AZURITE  = "$env:USERPROFILE\azurite-data"
$NOPROXY  = "localhost,127.0.0.1,::1"

Write-Host "=== CAT Document Reader - subindo ambiente local ===" -ForegroundColor Cyan
Write-Host "Raiz do projeto: $ROOT`n"

# --- Funcao auxiliar: abre um servico em nova janela do PowerShell ---
# Limpa VIRTUAL_ENV pra a janela nao herdar um venv errado do terminal pai.
function Start-Service-Window($title, $workdir, $command) {
    $full = "`$host.UI.RawUI.WindowTitle='$title'; " +
            "Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue; " +
            "`$env:NO_PROXY='$NOPROXY'; " +
            "`$env:HTTP_PROXY='http://proxy.cat.com:80'; " +
            "`$env:HTTPS_PROXY='http://proxy.cat.com:80'; " +
            "cd '$workdir'; " +
            "Write-Host '=== $title ===' -ForegroundColor Green; " +
            "$command"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $full
}

# --- 1. Postgres (background, nao ocupa janela) ---
Write-Host "[1/5] Postgres..." -ForegroundColor Yellow
$pgStatus = & "$PG\pg_ctl.exe" -D $PGDATA status 2>&1
if ($pgStatus -match "no server running") {
    & "$PG\pg_ctl.exe" -D $PGDATA -o "-p 5432" -l "$PGDATA\server.log" start
    Start-Sleep -Seconds 2
    Write-Host "      Postgres iniciado." -ForegroundColor Green
} else {
    Write-Host "      Postgres ja estava rodando." -ForegroundColor Green
}

# --- Reset do banco (so com -Fresh) ---
# TRUNCATE ... CASCADE zera documents e, por cascata, invoices/linhas/eventos.
if ($Fresh) {
    Write-Host "      Zerando o banco (-Fresh)..." -ForegroundColor Yellow
    $env:PGPASSWORD = "invoice"
    & "$PG\psql.exe" "host=localhost port=5432 dbname=documentreader user=invoice" `
        -c "TRUNCATE documents CASCADE;" 2>&1 | Out-Null
    Write-Host "      Banco zerado." -ForegroundColor Green
}

# --- 2. Azurite (Blob + Queue) ---
# 'azurite' (nao 'azurite-blob'): o function_app.py usa queue_output/queue_trigger,
# que precisam do endpoint de Queue (10001) alem do de Blob (10000). Com azurite-blob
# sozinho os bindings de fila nao conectam. Se -CleanBlob for passado, limpa o
# diretorio de dados (resolve o crash de GC por dados corrompidos).
Write-Host "[2/5] Azurite (Blob + Queue)..." -ForegroundColor Yellow
if ($CleanBlob) {
    Write-Host "      Limpando dados do Azurite (--CleanBlob)..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $AZURITE -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $AZURITE | Out-Null
}
Start-Service-Window "Azurite" $ROOT `
    "azurite --blobHost 127.0.0.1 --blobPort 10000 --queueHost 127.0.0.1 --queuePort 10001 --location '$AZURITE' --skipApiVersionCheck"
Start-Sleep -Seconds 3

# --- 3. Function (worker de IA) ---
Write-Host "[3/5] Function (worker)..." -ForegroundColor Yellow
Start-Service-Window "Function" "$ROOT\function" `
    ".\.venv\Scripts\Activate.ps1; func start --python"
Start-Sleep -Seconds 8

# --- 4. Backend (FastAPI) ---
# A janela ja limpa VIRTUAL_ENV (ver Start-Service-Window), entao o 'uv run'
# a partir de backend/ usa o venv correto do backend, nao o da function.
Write-Host "[4/5] Backend (FastAPI)..." -ForegroundColor Yellow
Start-Service-Window "Backend" "$ROOT\backend" `
    "uv run uvicorn app.main:app --reload --port 8000"
Start-Sleep -Seconds 5

# --- 5. Frontend (Vite) ---
Write-Host "[5/5] Frontend (Vite)..." -ForegroundColor Yellow
Start-Service-Window "Frontend" "$ROOT\frontend" `
    "npm run dev"
Start-Sleep -Seconds 3

Write-Host "`n=== Tudo no ar! ===" -ForegroundColor Cyan
Write-Host "Frontend:  http://localhost:5173"
Write-Host "Backend:   http://localhost:8000/health"
Write-Host "Function:  http://localhost:7071"
Write-Host "`nCada servico esta em sua propria janela (Azurite, Function, Backend, Frontend)."
Write-Host "Se o Azurite crashar (erro de GC):     .\start-local.ps1 -CleanBlob"
Write-Host "Para resetar tudo (blob + banco):      .\start-local.ps1 -Fresh"
Write-Host "Para derrubar tudo:                    .\stop-local.ps1`n"
