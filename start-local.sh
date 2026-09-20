#!/usr/bin/env bash
# ============================================================================
# start-local.sh  -  Sobe o ambiente local do CAT Document Reader (Linux/WSL)
#
# Equivalente ao start-local.ps1, que e a versao Windows/VM. As diferencas sao
# de plataforma: aqui o Postgres e servico do sistema (nao um pgdata proprio),
# nao ha proxy da CAT, e cada servico roda em background com log em arquivo em
# vez de abrir uma janela.
#
# Uso:  ./start-local.sh              normal, mantem os dados
#       ./start-local.sh --clean-blob limpa so o Azurite
#       ./start-local.sh --fresh      RESET TOTAL: Azurite + banco do zero
#       ./start-local.sh --status     so mostra o que esta de pe
#
# Derruba tudo com ./stop-local.sh
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$ROOT/.local"
LOGS="$RUN/logs"
AZURITE_DATA="${AZURITE_DATA:-$HOME/azurite-data}"
DB_URL="${DATABASE_URL:-postgresql+psycopg://invoice:invoice@localhost:5432/documentreader}"
FUNC_PORT=7071
API_PORT=8000
WEB_PORT=5173

CLEAN_BLOB=0; FRESH=0; STATUS_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --clean-blob) CLEAN_BLOB=1 ;;
        --fresh)      FRESH=1; CLEAN_BLOB=1 ;;
        --status)     STATUS_ONLY=1 ;;
        -h|--help)    sed -n '2,18p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "argumento desconhecido: $arg (use --help)"; exit 2 ;;
    esac
done

mkdir -p "$LOGS"

c_ok()   { printf '  \033[32m%s\033[0m %s\n' "ok" "$1"; }
c_warn() { printf '  \033[33m%s\033[0m %s\n' "!!" "$1"; }
c_err()  { printf '  \033[31m%s\033[0m %s\n' "XX" "$1"; }
head()   { printf '\n\033[36m%s\033[0m\n' "$1"; }

porta_aberta() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# Espera a porta subir. Sem isso o proximo servico sobe antes da dependencia e
# falha por um motivo que nao e o verdadeiro.
espera_porta() {
    local porta="$1" nome="$2" limite="${3:-60}"
    for _ in $(seq 1 "$limite"); do
        porta_aberta "$porta" && return 0
        sleep 1
    done
    c_err "$nome nao subiu na porta $porta -- veja $LOGS/${nome}.log"
    return 1
}

# Estado por PORTA, nao por pid: 'uv run' e 'npm run dev' sao wrappers que
# trocam de processo, entao o pid que o start guarda morre antes do servidor.
vivo() { porta_aberta "$1"; }

sobe() {
    local nome="$1" porta="$2" dir="$3"; shift 3
    if vivo "$porta"; then
        c_warn "$nome ja esta no ar na porta $porta"
        return 0
    fi
    ( cd "$dir" && setsid nohup "$@" </dev/null > "$LOGS/$nome.log" 2>&1 & echo $! > "$RUN/$nome.pid" )
    c_ok "$nome iniciado, log em .local/logs/$nome.log"
}

mostra_status() {
    head "=== estado ==="
    printf '  %-10s %-9s %s\n' "servico" "porta" "situacao"
    for par in "azurite 10000" "func $FUNC_PORT" "backend $API_PORT" "frontend $WEB_PORT"; do
        set -- $par
        if porta_aberta "$2"; then printf '  %-10s %-9s \033[32mno ar\033[0m\n' "$1" "$2"
        else printf '  %-10s %-9s \033[31mfora\033[0m\n' "$1" "$2"; fi
    done
    if pg_isready -h localhost -q 2>/dev/null; then printf '  %-10s %-9s \033[32mno ar\033[0m\n' "postgres" "5432"
    else printf '  %-10s %-9s \033[31mfora\033[0m\n' "postgres" "5432"; fi
}

[ "$STATUS_ONLY" = 1 ] && { mostra_status; exit 0; }

# --- 0. Pre-requisitos -------------------------------------------------------
head "=== CAT Document Reader - ambiente local ==="
echo "  raiz: $ROOT"

head "[0/5] pre-requisitos"
faltando=0
for cmd in uv npm node; do
    command -v "$cmd" >/dev/null || { c_err "$cmd nao encontrado"; faltando=1; }
done
command -v azurite >/dev/null || { c_err "azurite nao encontrado -- npm i -g azurite"; faltando=1; }
command -v func >/dev/null || { c_err "func nao encontrado -- npm i -g azure-functions-core-tools@4"; faltando=1; }
[ "$faltando" = 1 ] && exit 1
c_ok "uv, npm, node, azurite, func"

if ! pg_isready -h localhost -q 2>/dev/null; then
    c_err "Postgres nao responde em localhost:5432 -- sudo service postgresql start"
    exit 1
fi
c_ok "postgres respondendo"

# --- 1. shared vendorizado ---------------------------------------------------
# A function importa 'from shared...' de uma copia dentro dela, nao do pacote:
# shared/pyproject.toml pede Python >=3.14 e o runtime da function e 3.11, entao
# instalar como pacote nao resolve. O deploy faz o mesmo (scripts/build.sh).
head "[1/5] shared vendorizado"
bash "$ROOT/scripts/build.sh" >/dev/null && c_ok "copiado para backend/shared e function/shared"

# --- 2. Azurite --------------------------------------------------------------
head "[2/5] azurite (blob + queue)"
if [ "$CLEAN_BLOB" = 1 ]; then
    vivo 10000 && { fuser -k -TERM 10000/tcp >/dev/null 2>&1; sleep 2; rm -f "$RUN/azurite.pid"; }
    rm -rf "$AZURITE_DATA"; c_warn "dados do azurite apagados"
fi
mkdir -p "$AZURITE_DATA"
# 'azurite' e nao 'azurite-blob': o function_app usa queue_trigger, que precisa
# do endpoint de fila (10001) alem do de blob (10000).
sobe azurite 10000 "$AZURITE_DATA" azurite \
    --blobHost 127.0.0.1 --blobPort 10000 \
    --queueHost 127.0.0.1 --queuePort 10001 \
    --location "$AZURITE_DATA" --skipApiVersionCheck
espera_porta 10000 azurite

# --- 3. Banco ----------------------------------------------------------------
head "[3/5] banco"
if [ "$FRESH" = 1 ]; then
    c_warn "RESET: derrubando e recriando o schema"
    ( cd "$ROOT/backend" && DATABASE_URL="$DB_URL" uv run alembic downgrade base >/dev/null 2>&1 || true )
fi
( cd "$ROOT/backend" && DATABASE_URL="$DB_URL" uv run alembic upgrade head > "$LOGS/alembic.log" 2>&1 ) \
    && c_ok "migracoes em dia" \
    || { c_err "alembic falhou -- veja .local/logs/alembic.log"; exit 1; }

# --- 4. Function -------------------------------------------------------------
head "[4/5] function (worker)"
if [ ! -x "$ROOT/function/.venv/bin/python" ]; then
    c_err "function/.venv nao existe. Crie com:"
    echo "      cd function && uv venv --python 3.11 .venv"
    echo "      uv pip install --python .venv/bin/python -r requirements.txt"
    echo "      # modo local (opcional): -r requirements-local.txt, ver docs/modo-local.md"
    exit 1
fi
[ -f "$ROOT/function/local.settings.json" ] || c_warn "function/local.settings.json ausente -- o worker vai subir sem DATABASE_URL"
# func acha o worker de python pelo PATH, entao o venv tem de vir na frente.
if vivo "$FUNC_PORT"; then
    c_warn "func ja esta no ar na porta $FUNC_PORT"
else
    ( cd "$ROOT/function" && PATH="$ROOT/function/.venv/bin:$PATH" VIRTUAL_ENV="$ROOT/function/.venv" \
        setsid nohup func start --port "$FUNC_PORT" </dev/null > "$LOGS/func.log" 2>&1 & echo $! > "$RUN/func.pid" )
    c_ok "func iniciado (pid $(cat "$RUN/func.pid")), log em .local/logs/func.log"
fi
espera_porta "$FUNC_PORT" func 90

# --- 5. Backend e frontend ---------------------------------------------------
head "[5/5] backend e frontend"
if vivo "$API_PORT"; then c_warn "backend ja esta no ar na porta $API_PORT"; else
    ( cd "$ROOT/backend" && DATABASE_URL="$DB_URL" \
        FUNCTION_URL="http://localhost:$FUNC_PORT/api/process_document" \
        setsid nohup uv run uvicorn app.main:app --port "$API_PORT" --host 127.0.0.1 \
        </dev/null > "$LOGS/backend.log" 2>&1 & echo $! > "$RUN/backend.pid" )
    c_ok "backend iniciado (pid $(cat "$RUN/backend.pid"))"
fi
espera_porta "$API_PORT" backend

[ -d "$ROOT/frontend/node_modules" ] || ( cd "$ROOT/frontend" && npm install >/dev/null 2>&1 )
sobe frontend "$WEB_PORT" "$ROOT/frontend" npm run dev -- --host 127.0.0.1 --port "$WEB_PORT"
espera_porta "$WEB_PORT" frontend

mostra_status
head "=== pronto ==="
echo "  frontend   http://localhost:$WEB_PORT"
echo "  backend    http://localhost:$API_PORT/health"
echo "  function   http://localhost:$FUNC_PORT/api/process_document"
echo
echo "  logs       .local/logs/*.log"
echo "  derrubar   ./stop-local.sh"
