#!/usr/bin/env bash
# PreToolUse (Write|Edit) — recusa escrever segredo em arquivo versionado.
#
# **A checagem é do par (conteúdo, destino), não só do conteúdo.** Uma chave no
# `.env` é o uso CERTO — o `.env` é gitignored e é onde ela deve estar. A mesma
# chave em `api/config.py` é o vazamento. Por isso o hook pergunta primeiro ao
# `git check-ignore` se o destino é versionado, e só então varre.
#
# Sem isso o hook viraria ou inútil (só bloqueia o óbvio) ou insuportável
# (bloqueia o `.env`, que é justamente o que o CLAUDE.md manda usar).
set -uo pipefail
raiz="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_INPUT="$(cat)"; export HOOK_INPUT
# shellcheck source=_hooklib.sh
. "$raiz/_hooklib.sh"

file="$(json_get tool_input.file_path)"
[ -n "$file" ] || exit 0

# Destino gitignored (.env, .venv, fixtures) não é vazamento — é o lugar certo.
git check-ignore -q "$file" 2>/dev/null && exit 0

# `content` no Write, `new_string` no Edit.
conteudo="$(json_get tool_input.content tool_input.new_string)"
[ -n "$conteudo" ] || exit 0

achar() { grep -Eq -- "$1" <<< "$conteudo"; }

achar '(sk-or-v1-|sk-proj-|sk-ant-)[A-Za-z0-9_-]{20,}' \
  && nega 'Recusado: chave de API (OpenAI/OpenRouter/Anthropic) em arquivo versionado. Segredo vai para o .env, que é gitignored; o .env.example leva só o placeholder.'
achar '(ghp_|gho_|ghs_|github_pat_)[A-Za-z0-9_]{20,}' \
  && nega 'Recusado: token do GitHub em arquivo versionado. Use o gh CLI ou uma variável de ambiente.'
achar 'AKIA[0-9A-Z]{16}' \
  && nega 'Recusado: AWS Access Key ID em arquivo versionado.'
achar '-----BEGIN [A-Z ]*PRIVATE KEY-----' \
  && nega 'Recusado: bloco de chave privada em arquivo versionado.'
achar '(AZURE_OPENAI_KEY|AZURE_DOCINTEL_KEY|OPENROUTER_API_KEY|FUNCTION_KEY|AZURE_STORAGE_CONNECTION_STRING|AzureWebJobsStorage)[[:space:]]*=[[:space:]]*["'"'"']?[A-Za-z0-9/+_=-]{12,}' \
  && nega 'Recusado: variável de credencial com VALOR em arquivo versionado. Segredo vive no .env.local (gitignored); exemplo e documentação levam placeholder vazio.'
achar '(postgres(ql)?(\+[a-z]+)?)://[^:@/[:space:]]+:[^@/[:space:]]{6,}@' \
  && nega 'Recusado: URL de banco com senha embutida em arquivo versionado. A DATABASE_URL vem do ambiente.'

exit 0
