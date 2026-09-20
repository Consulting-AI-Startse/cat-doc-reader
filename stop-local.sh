#!/usr/bin/env bash
# ============================================================================
# stop-local.sh  -  Derruba o ambiente local do CAT Document Reader (Linux/WSL)
#
# Uso:  ./stop-local.sh
#
# Diferente do stop-local.ps1, que mata todo processo node/python da maquina,
# aqui so morre o que ocupa as quatro portas do projeto. Postgres nao e
# derrubado -- e servico do sistema e provavelmente tem outros bancos em uso.
#
# Por que por porta e nao por pid: 'uv run uvicorn' e 'npm run dev' sao
# wrappers que trocam de processo, entao o pid guardado no start morre antes do
# servidor de verdade. A porta e o unico identificador estavel.
# ============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$ROOT/.local"

printf '\n\033[36m=== derrubando ambiente local ===\033[0m\n'

porta_aberta() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

derruba() {
    local nome="$1" porta="$2"
    if ! porta_aberta "$porta"; then
        printf '  \033[33m--\033[0m %-9s (porta %s) ja estava parado\n' "$nome" "$porta"
        rm -f "$RUN/$nome.pid"
        return 0
    fi
    # fuser -k manda SIGTERM em quem escuta a porta; so nessa porta.
    fuser -k -TERM "$porta/tcp" >/dev/null 2>&1
    for _ in $(seq 1 10); do
        porta_aberta "$porta" || break
        sleep 1
    done
    if porta_aberta "$porta"; then
        fuser -k -KILL "$porta/tcp" >/dev/null 2>&1
        sleep 1
    fi
    if porta_aberta "$porta"; then
        printf '  \033[31mXX\033[0m %-9s (porta %s) NAO morreu -- veja: lsof -i :%s\n' "$nome" "$porta" "$porta"
    else
        printf '  \033[32mok\033[0m %-9s (porta %s) parado\n' "$nome" "$porta"
    fi
    rm -f "$RUN/$nome.pid"
}

# Ordem importa: frontend e backend primeiro, para nao ficarem gritando com
# dependencia que sumiu no log.
derruba frontend 5173
derruba backend  8000
derruba func     7071
derruba azurite  10000

printf '\n\033[36m=== estado ===\033[0m\n'
for par in "azurite 10000" "func 7071" "backend 8000" "frontend 5173"; do
    set -- $par
    if porta_aberta "$2"; then
        printf '  \033[31m%-10s porta %s ainda aberta\033[0m\n' "$1" "$2"
    else
        printf '  \033[32m%-10s porta %s livre\033[0m\n' "$1" "$2"
    fi
done

echo
echo "  Postgres continua no ar de proposito (servico do sistema)."
echo "  Logs preservados em .local/logs/"
