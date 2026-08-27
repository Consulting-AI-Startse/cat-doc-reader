# ============================================================================
# stop-local.ps1  -  Derruba todo o ambiente local do CAT Document Reader
# Uso:  .\stop-local.ps1
# ============================================================================

$PG     = "$env:LOCALAPPDATA\pgsql\pgsql\bin"
$PGDATA = "$env:USERPROFILE\pgdata"

Write-Host "=== Derrubando ambiente local ===" -ForegroundColor Cyan

# --- Para Postgres (background) ---
Write-Host "Parando Postgres..." -ForegroundColor Yellow
& "$PG\pg_ctl.exe" -D $PGDATA stop 2>&1 | Out-Null

# --- Fecha as janelas dos servicos foreground pelo titulo ---
# (mata os processos node/func/python/uvicorn que sobem os servicos)
Write-Host "Parando Azurite, Function, Backend, Frontend..." -ForegroundColor Yellow

# Azurite e Frontend rodam sob node
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
# Function Core Tools
Get-Process func -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process "func.exe" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
# Backend (uvicorn roda sob python)
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "`n=== Ambiente derrubado. ===" -ForegroundColor Cyan
Write-Host "Nota: se voce tinha outros processos node/python abertos, eles tambem foram encerrados."