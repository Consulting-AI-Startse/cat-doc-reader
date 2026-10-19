#!/usr/bin/env bash
# PreToolUse (Write|Edit) -- recusa escrever segredo em arquivo versionado.
#
# A checagem é do par (conteúdo, destino). Uma chave no `.env.local` é o uso
# certo: ele é gitignored e é onde ela deve estar. A mesma chave em
# `shared/shared/config.py` é o vazamento. Por isso o hook pergunta primeiro ao
# git se o destino é versionado (ou está fora do repo: scratchpad, /tmp) e só
# então varre. Os padrões estão em `secret_in`, na _hooklib, porque o guarda de
# Bash usa os mesmos.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_hooklib.sh
. "$here/_hooklib.sh"

file="$(json_get tool_input.file_path)"
[ -n "$file" ] || exit 0

# Fora da árvore do repo (scratchpad, /tmp) não é versionado: fixture com chave
# falsa ali é legítima. `check-ignore` devolve 128 nesse caso, não 0.
top="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
case "$file" in
  "$top"/*) ;;
  *) exit 0 ;;
esac
git check-ignore -q "$file" 2>/dev/null && exit 0

# `content` no Write, `new_string` no Edit.
content="$(json_get tool_input.content tool_input.new_string)"
[ -n "$content" ] || exit 0

if reason="$(secret_in "$content")"; then
  deny "Recusado: $reason em arquivo versionado ($file). Segredo vive no .env.local (gitignored); exemplo e documentação levam placeholder vazio."
fi

exit 0
