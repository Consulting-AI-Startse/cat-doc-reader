#!/usr/bin/env bash
# PreToolUse (Bash) — recusa comando destrutivo antes de ele rodar.
#
# Duas famílias:
#
#   1. Destrutivo universal — apagar a raiz ou o home, formatar disco, escrever
#      cru num device, `drop database`, `chmod -R 777 /`.
#   2. Destrutivo DESTE repositório — commit e push direto na `main`, e force
#      push para a `main`. Desde 19/10 este repo também trabalha por PR
#      (CLAUDE.md, "O fluxo de trabalho"): a main só recebe merge.
#
# **Recusa é uma decisão, não um erro.** O hook sai com 0 e devolve
# `permissionDecision: "deny"` com o motivo — o modelo lê o motivo e corrige o
# rumo, em vez de ver um traceback e tentar de novo.
#
# Deliberadamente NÃO bloqueia `git reset --hard`: é como se desfaz trabalho
# local, e o /rewind existe. Nem o `check_dedupe.py` / `check_parts.py`, que
# apagam dados: o CLAUDE.md manda apontá-los para uma base de teste, e é a
# DATABASE_URL que decide, não o comando.
set -uo pipefail
raiz="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_INPUT="$(cat)"; export HOOK_INPUT
# shellcheck source=_hooklib.sh
. "$raiz/_hooklib.sh"

cmd="$(json_get tool_input.command)"
[ -n "$cmd" ] || exit 0

# --- 1. destrutivo universal -------------------------------------------------
# `rm -rf` seguido de / ou ~ (com ou sem aspas), e o clássico "$VAR/" vazio.
if grep -Eq 'rm[[:space:]]+(-[a-zA-Z]*[rR][a-zA-Z]*[fF]|-[a-zA-Z]*[fF][a-zA-Z]*[rR])[a-zA-Z]*[[:space:]]+("|'"'"')?(/|~|\$[A-Za-z_]+/)[[:space:]"'"'"'/]*$' <<< "$cmd"; then
  nega 'Recusado: apagar recursivamente a raiz ou o home. Se a intenção era limpar um diretório do projeto, nomeie o caminho completo.'
fi
grep -Eq 'mkfs(\.[a-z0-9]+)?[[:space:]]' <<< "$cmd" && nega 'Recusado: formatar sistema de arquivos.'
grep -Eq '>[[:space:]]*/dev/(sd|nvme|hd)' <<< "$cmd" && nega 'Recusado: escrita crua em device de bloco.'
grep -Eq 'chmod[[:space:]]+(-[a-zA-Z]+[[:space:]]+)*777[[:space:]]+/[[:space:]]*$' <<< "$cmd" && nega 'Recusado: chmod 777 recursivo na raiz.'
# Exige um CLIENTE de banco na mesma linha, não só o texto solto. A versão
# anterior casava a string em qualquer lugar do comando e recusou um
# `gh pr create` cujo CORPO citava o comando como exemplo — falso positivo
# encontrado ao abrir o PR destes próprios hooks, e o segundo comando que ele
# recusou foi o que vinha consertá-lo. Guardrail que bloqueia a documentação
# sobre o perigo é guardrail que alguém desliga.
#
# `dropdb` é regra PRÓPRIA, e não estava: ele não contém a frase de duas
# palavras, então a condição composta abaixo o deixava passar. Achado ao testar
# o estreitamento — um caso que a versão larga pegava por acidente.
grep -Eq '(^|[[:space:]|;&])dropdb([[:space:]]|$)' <<< "$cmd" \
  && nega 'Recusado: `dropdb`. Zerar banco é decisão de quem opera, não do agente: peça ao Luis.'

if grep -Eq '(psql|mysql|mariadb|sqlcmd)' <<< "$cmd" \
   && grep -Eiq 'drop[[:space:]]+database' <<< "$cmd"; then
  nega 'Recusado: `drop database` via cliente de banco. Zerar banco é decisão de quem opera, não do agente: peça ao Luis.'
fi

# --- 2. destrutivo deste repositório -----------------------------------------
grep -Eq 'git[[:space:]]+push[[:space:]].*(--force|[[:space:]]-f([[:space:]]|$)).*(main|origin[[:space:]]+main)' <<< "$cmd" \
  && nega 'Recusado: force push para a main. O histórico da main é compartilhado.'

if grep -Eq 'git[[:space:]]+(commit|push)([[:space:]]|$)' <<< "$cmd"; then
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
  if [ "$branch" = "main" ]; then
    nega "Recusado: 'git ${cmd#*git }' com a main em checkout. Desde 19/10 este repo trabalha por PR (CLAUDE.md): branch por trabalho (feat/, fix/, docs/, ci/), /code-review e, se tocar backend ou entrada, /security-review antes de abrir. Crie a branch a partir de origin/main primeiro."
  fi
fi

exit 0
