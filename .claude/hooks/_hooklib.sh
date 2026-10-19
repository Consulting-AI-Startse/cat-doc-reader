#!/usr/bin/env bash
# Funções comuns aos hooks. Não é um hook: é `source`ado pelos outros.
#
# Python e não `jq`: o `jq` não está instalado nas máquinas de desenvolvimento,
# e a primeira versão (no cat-freight-poc) saía 0 em silêncio quando ele
# faltava. Pelo mesmo motivo a ausência de python3 é falha ALTA (exit 2 bloqueia
# a ferramenta e mostra o stderr), e não "deixa passar".
set -uo pipefail

command -v python3 >/dev/null 2>&1 || { echo "hook: python3 ausente; recusando por seguranca" >&2; exit 2; }

# O payload fica numa variável de shell, nunca exportada: um Write de 300 KB
# exportado estoura o MAX_ARG_STRLEN de todo exec filho, o python3 nem sobe, e
# o hook saía 0 sem ver nada -- o guarda falhava justamente no arquivo grande.
HOOK_INPUT="$(cat)"

# json_get <caminho.pontilhado> [<alternativo> ...] -- lê de $HOOK_INPUT.
# Devolve vazio (e sai 0) se nada casar: payload inesperado não derruba o hook.
json_get() {
  python3 -c '
import json, sys
try:
    data = json.loads(sys.stdin.read() or "{}")
except Exception:
    sys.exit(0)
for path in sys.argv[1:]:
    cur = data
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            cur = None
            break
        cur = cur[part]
    if isinstance(cur, str) and cur:
        print(cur, end="")
        sys.exit(0)
' "$@" <<< "$HOOK_INPUT"
}

# deny <motivo> -- recusa a chamada (PreToolUse). Sai 0: recusa é decisão, não erro.
deny() {
  python3 -c '
import json, sys
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": sys.argv[1],
}}))
' "$1"
  exit 0
}

# secret_in <texto> -- sai 0 e imprime o motivo se o texto carrega segredo.
# Compartilhado entre o guarda de Write/Edit e o de Bash (heredoc, sed -i, tee
# escrevem arquivo sem passar por Write/Edit). Valor de desenvolvimento local
# não é segredo: a DATABASE_URL de localhost está em nove arquivos versionados
# e o Azurite usa UseDevelopmentStorage=true.
secret_in() {
  local text="$1"
  has() { grep -Eq -- "$1" <<< "$text"; }
  has '(sk-or-v1-|sk-proj-|sk-ant-)[A-Za-z0-9_-]{20,}' \
    && { echo 'chave de API (OpenAI/OpenRouter/Anthropic)'; return 0; }
  has '(ghp_|gho_|ghs_|github_pat_)[A-Za-z0-9_]{20,}' \
    && { echo 'token do GitHub'; return 0; }
  has 'AKIA[0-9A-Z]{16}' && { echo 'AWS Access Key ID'; return 0; }
  has '-----BEGIN [A-Z ]*PRIVATE KEY-----' && { echo 'bloco de chave privada'; return 0; }
  has '(AZURE_OPENAI_KEY|AZURE_DOCINTEL_KEY|OPENROUTER_API_KEY|FUNCTION_KEY)[[:space:]]*=[[:space:]]*["'"'"']?[A-Za-z0-9/+_=-]{12,}' \
    && { echo 'variavel de credencial com VALOR'; return 0; }
  if has '(AZURE_STORAGE_CONNECTION_STRING|AzureWebJobsStorage)[[:space:]]*=[[:space:]]*["'"'"']?[A-Za-z0-9/+_=;-]{12,}' \
     && ! has 'UseDevelopmentStorage=true'; then
    echo 'connection string de storage com VALOR'; return 0
  fi
  if has '(postgres(ql)?(\+[a-z]+)?)://[^:@/[:space:]]+:[^@/[:space:]]{6,}@' \
     && ! has '(postgres(ql)?(\+[a-z]+)?)://[^:@/[:space:]]+:[^@/[:space:]]{6,}@(localhost|127\.0\.0\.1|db|postgres)([:/]|$)'; then
    echo 'URL de banco com senha embutida'; return 0
  fi
  return 1
}
