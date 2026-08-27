#!/usr/bin/env bash
# Vendoriza o shared canonico (shared/shared) pra dentro do backend e da function.
# Rode antes de empacotar/deployar. As copias backend/shared e function/shared sao
# geradas e gitignored: a fonte unica e shared/shared. Nunca edite as copias.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$root/backend/shared" "$root/function/shared"
cp -R "$root/shared/shared" "$root/backend/shared"
cp -R "$root/shared/shared" "$root/function/shared"
echo "OK: shared vendorizado em backend/shared e function/shared"
