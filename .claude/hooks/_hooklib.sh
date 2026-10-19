#!/usr/bin/env bash
# Funções comuns aos hooks. Não é um hook: é `source`ado pelos outros.
#
# ## Por que Python e não `jq`
#
# A primeira versão destes hooks usava `jq`, e **na máquina de desenvolvimento o
# `jq` não está instalado**. O modo de falhar foi o pior possível: cada hook saía
# 0 sem fazer nada, em silêncio, porque o erro do `jq` estava mandado para
# /dev/null e o `|| exit 0` engolia o resto. Um guardrail que não guarda nada e
# não avisa é pior que guardrail nenhum.
#
# `python3` é a escolha óbvia aqui e não foi a primeira: é a LINGUAGEM do
# projeto, então está presente por definição em qualquer máquina que rode este
# repositório — ao contrário do `jq`, que é utilitário de sistema e ninguém
# declarou em lugar nenhum.
set -uo pipefail

# json_get <caminho.pontilhado> [<caminho alternativo> ...] — lê do stdin já
# capturado em $HOOK_INPUT. Devolve vazio (e sai 0) se nada casar: hook não pode
# morrer por causa de payload inesperado.
json_get() {
  local chaves=("$@")
  python3 -c '
import json, sys
try:
    dados = json.loads(sys.stdin.read() or "{}")
except Exception:
    sys.exit(0)
for caminho in sys.argv[1:]:
    atual = dados
    for parte in caminho.split("."):
        if not isinstance(atual, dict) or parte not in atual:
            atual = None
            break
        atual = atual[parte]
    if isinstance(atual, str) and atual:
        print(atual, end="")
        sys.exit(0)
' "${chaves[@]}" <<< "$HOOK_INPUT" 2>/dev/null
}

# json_out <json-python-literal-de-dict> — imprime JSON válido.
# Construir JSON com printf é como ele quebra: aspas, quebra de linha e acento no
# meio de uma mensagem em português já bastam.
json_emit() {
  python3 -c '
import json, sys
print(json.dumps(json.loads(sys.stdin.read())))
' 2>/dev/null
}

# nega <motivo> — recusa a chamada de ferramenta (PreToolUse), com o motivo que o
# modelo vai ler. Sai 0: recusa é decisão, não erro.
nega() {
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

# bloqueia <motivo> — impede o encerramento do turno (Stop).
bloqueia() {
  python3 -c '
import json, sys
print(json.dumps({"decision": "block", "reason": sys.argv[1]}))
' "$1"
  exit 0
}

# avisa <mensagem> — mostra ao usuário sem bloquear nada.
avisa() {
  python3 -c '
import json, sys
print(json.dumps({"systemMessage": sys.argv[1]}))
' "$1"
}
