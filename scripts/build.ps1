# Vendoriza o shared canonico (shared\shared) pra dentro do backend e da function.
# Rode antes de empacotar/deployar (secoes 2 e 3 do DEPLOY.md). As copias
# backend\shared e function\shared sao geradas e gitignored: a fonte unica e
# shared\shared. Nunca edite as copias.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Remove-Item -Recurse -Force "$root\backend\shared","$root\function\shared" -ErrorAction SilentlyContinue
Copy-Item -Recurse "$root\shared\shared" "$root\backend\shared"
Copy-Item -Recurse "$root\shared\shared" "$root\function\shared"
Write-Host "OK: shared vendorizado em backend/shared e function/shared"
