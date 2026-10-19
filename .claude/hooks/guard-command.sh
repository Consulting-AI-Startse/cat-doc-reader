#!/usr/bin/env bash
# PreToolUse (Bash) -- recusa antes de rodar:
#
#   1. destrutivo universal: apagar raiz ou home, formatar disco, escrever cru
#      em device, drop database, chmod 777 na raiz;
#   2. destrutivo deste repositório: commit ou push com a `main` em checkout, e
#      force push para a `main`. Desde 19/10 o repo trabalha por PR (CLAUDE.md,
#      "O fluxo de trabalho"): a main só recebe merge;
#   3. segredo no texto do comando: heredoc, `sed -i` e `tee` escrevem arquivo
#      sem passar por Write/Edit, e o guarda de lá não os vê.
#
# Toda regra casa o COMANDO, não a palavra: o padrão exige início de comando
# antes do verbo (`(^|[[:space:];&|(])`). Sem isso o hook recusava o próprio
# comando de teste do README e um `gh pr create` cujo corpo citava o perigo.
#
# Recusa é decisão, não erro: sai 0 com `permissionDecision: "deny"` e o motivo.
# Deliberadamente NÃO bloqueia `git reset --hard` (é como se desfaz trabalho
# local, e o /rewind existe) nem `check_dedupe.py` / `check_parts.py`, que
# apagam dados: quem decide é a DATABASE_URL, não o comando.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_hooklib.sh
. "$here/_hooklib.sh"

cmd="$(json_get tool_input.command)"
[ -n "$cmd" ] || exit 0

START='(^|[[:space:];&|(])'
has() { grep -Eq -- "$1" <<< "$cmd"; }

# --- 1. destrutivo universal -------------------------------------------------
# rm recursivo (flag com r/R, junta ou separada) em /, /*, ~, $HOME ou "$VAR/".
# `$VAR/` com a variável vazia é a raiz; `"$VAR"` vazio só faz o rm falhar, e é
# o idioma normal de limpar um temporário -- não entra.
if has "${START}rm[[:space:]]+(-[A-Za-z]+[[:space:]]+)*-[A-Za-z]*[rR][A-Za-z]*([[:space:]]+-[A-Za-z]+)*[[:space:]]+(\"|')?(/\*?|~/?|\\\$\{?HOME\}?/?|\\\$\{?[A-Za-z_]+\}?/)(\"|')?([[:space:]]|$)"; then
  deny 'Recusado: apagar recursivamente a raiz, o home ou uma variável vazia. Se a intenção era limpar um diretório do projeto, nomeie o caminho completo.'
fi
has "${START}mkfs(\.[a-z0-9]+)?[[:space:]]" && deny 'Recusado: formatar sistema de arquivos.'
has '>[[:space:]]*/dev/(sd|nvme|hd)' && deny 'Recusado: escrita crua em device de bloco.'
has "${START}chmod[[:space:]]+(-[A-Za-z]+[[:space:]]+)*777[[:space:]]+/[[:space:]]*$" && deny 'Recusado: chmod 777 recursivo na raiz.'
has "${START}dropdb([[:space:]]|$)" && deny 'Recusado: `dropdb`. Zerar banco é decisão de quem opera, não do agente: peça ao Luis.'
if has "${START}(psql|mysql|mariadb|sqlcmd)([[:space:]]|$)" && grep -Eiq 'drop[[:space:]]+database' <<< "$cmd"; then
  deny 'Recusado: `drop database` via cliente de banco. Zerar banco é decisão de quem opera, não do agente: peça ao Luis.'
fi

# --- 2. destrutivo deste repositório -----------------------------------------
# `main` como refspec inteiro: `feat/main-page` não é a main; `+main` é force push.
if has "${START}git[[:space:]]+push([[:space:]]|$)"; then
  if has "${START}git[[:space:]]+push[[:space:]]+(.*[[:space:]])?(--force(-with-lease)?|-f)[[:space:]]+(.*[[:space:]:])?main([[:space:]]|$)" \
     || has "${START}git[[:space:]]+push[[:space:]]+(.*[[:space:]:])?\+main([[:space:]]|$)"; then
    deny 'Recusado: force push para a main. O histórico da main é compartilhado.'
  fi
fi

if has "${START}git[[:space:]]+(commit|push)([[:space:]]|$)"; then
  # O comando que cria a branch e commita na sequência é o remédio que a
  # própria mensagem prescreve; julgar pela branch de ANTES o recusaria.
  if ! has "${START}git[[:space:]]+(checkout[[:space:]]+-b|switch[[:space:]]+-c)[[:space:]]"; then
    branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
    if [ "$branch" = "main" ]; then
      deny "Recusado: git commit/push com a main em checkout. Desde 19/10 este repo trabalha por PR (CLAUDE.md): branch por trabalho (feat/, fix/, docs/, ci/) a partir de origin/main, /code-review e, se tocar backend ou entrada, /security-review antes de abrir. Crie a branch primeiro (pode ser no mesmo comando: git checkout -b ... && git commit ...)."
    fi
  fi
fi

# --- 3. segredo no comando ---------------------------------------------------
if reason="$(secret_in "$cmd")"; then
  deny "Recusado: $reason no texto do comando. Segredo vive no .env.local (gitignored), escrito por quem o tem; nunca pelo agente."
fi

exit 0
