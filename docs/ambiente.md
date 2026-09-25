# Ambiente de desenvolvimento

O que precisa estar instalado para o `./start-local.sh` subir, e em que versão
isso foi verificado. **Mantenha atualizado**: quando trocar uma versão ou
acrescentar uma dependência de ambiente, atualize aqui na mesma leva.

Última verificação: **2026-09-21**.

## Ferramentas

| ferramenta | versão | para quê |
|---|---|---|
| Node | 22.22.2 | frontend (Vite) |
| npm | 10.9.7 | |
| uv | 0.10.7 | ambientes Python de backend e function |
| Azure Functions Core Tools | 4.14.0 | roda a function local (`func start`) |
| Azurite | 3.37.0 | Blob (10000) e Queue (10001) |
| PostgreSQL | 15.17 | serviço do sistema, não container |

`func` e `azurite` vêm do npm global:

```bash
npm i -g azurite azure-functions-core-tools@4
```

## Python: duas versões, e o shared no menor delas

| onde | versão | por quê |
|---|---|---|
| `function/.venv` | **3.11.14** | runtime do Function App na Azure; a 3.14 ainda não chegou lá |
| `backend/.venv` | 3.14.2 | runtime do App Service do backend, onde a 3.14 roda normalmente |

`shared/pyproject.toml` declara `>=3.11`, não `>=3.14`, **de propósito**: o
pacote é implantado nas duas aplicações, e sintaxe que só exista em 3.14 passa
no backend e quebra no import da function. O piso do `shared` é sempre o menor
dos dois runtimes.

```bash
cd function && uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt

cd backend && uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

O `shared` não é instalado como pacote em nenhum dos dois: é vendorizado por
`scripts/build.sh`, que é o que o deploy faz.

## Pacotes que importam

| pacote | versão | onde |
|---|---|---|
| `azure-functions` | 1.25.0 | function |
| `azure-ai-documentintelligence` | 1.0.2 | function (OCR de produção) |
| `openai` | 3.16.2 | function (Azure OpenAI e OpenRouter) |
| `sqlalchemy` | 2.0.54 | backend e function |
| `docling` | 2.129.0 | **só modo local** (`requirements-local.txt`) |
| `torch` | 2.14.0+cpu | dependência do docling; instalar pelo índice de CPU |
| `pypdfium2` | 5.13.0 | vem com o docling; renderiza página no fallback por imagem |

O `torch` pelo índice de CPU, senão a resolução puxa a stack CUDA inteira:

```bash
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Custo do modo local: ~1,5 GB de venv e ~500 MB de modelos em
`~/.cache/huggingface` (uma vez só).

## Banco

Postgres é serviço do sistema e **não é derrubado** pelo `stop-local.sh` — a
mesma instância hospeda outros bancos.

```sql
CREATE ROLE invoice LOGIN PASSWORD 'invoice';
CREATE DATABASE documentreader OWNER invoice;
```

Depois, `alembic upgrade head` (o `start-local.sh` já faz).

O `check_dedupe.py` **apaga todos os documentos** do banco para o qual apontar,
porque a duplicata só é testável contra dados controlados. Crie uma base
separada para ele e nunca rode contra a de desenvolvimento:

```sql
CREATE DATABASE dedupe_test OWNER invoice;   -- precisa de superusuário
```

```bash
cd backend && DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/dedupe_test \
    ./.venv/bin/alembic upgrade head
cd .. && DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/dedupe_test \
    ./backend/.venv/bin/python check_dedupe.py
```

No CI é o Postgres efêmero do job `backend`, que morre com o run.

## Portas

| porta | serviço |
|---|---|
| 5173 | frontend (Vite) |
| 8000 | backend (FastAPI) |
| 7071 | function (Core Tools) |
| 10000 / 10001 | Azurite blob / queue |
| 5432 | Postgres |

## Conferir o que está instalado

```bash
./start-local.sh --status     # o que esta no ar

node --version; npm --version; uv --version
func --version; azurite --version; psql --version
function/.venv/bin/python --version
function/.venv/bin/python -c "import importlib.metadata as m; \
print({p: m.version(p) for p in ('docling','torch','openai','azure-functions')})"
```

## O `shared` vendorizado, e por que o `import function_app` mente sem ele

`function/shared/` e `backend/shared/` são **geradas** por `scripts/build`
(`.ps1` no Windows) a partir de `shared/shared/`, e são gitignored: não vêm no
clone, não vêm em leva de espelhamento. Numa máquina onde o build nunca rodou,
ou onde a cópia foi apagada, `from shared.config import settings` estoura com
`ModuleNotFoundError: No module named 'shared.config'`.

**O `import function_app` só é um teste honesto depois do build.** Antes dele,
falha por ambiente e se lê como "a mudança quebrou a function" — foi exatamente
o susto na VM da CAT ao aplicar a leva 2, com a leva correta e conferida.

**Não confie em `Test-Path`/`ls` no diretório.** Na VM ele existia e estava
vazio: sobrara só um `__pycache__` órfão de uma remoção parcial. Um diretório
sem `__init__` vira namespace package, então `import shared` funciona e
`shared.config` não existe — o erro aponta para o submódulo e esconde a causa.
Confira o conteúdo:

```powershell
Get-ChildItem ./function/shared | Select-Object Name, Length
# 5 modulos: __init__, config, db, models, storage
```

O `scripts/build` apaga antes de copiar, então resolve cópia parcial também.

**Barra invertida antes de ponto some em alguns terminais.**
`..\function\.venv\Scripts\python.exe` chegou como `..\function.venv\...` e o
PowerShell não achou o executável. O PowerShell aceita barra normal, então use
`../function/.venv/Scripts/python.exe` em instrução que vai ser colada.

## Memória

O modo local com Docling é pesado. Numa máquina de 7 GB, o fallback por imagem
já levou a OOM em documento longo — e com outras ferramentas abertas o limite
chega antes. Se o worker morrer sem deixar mensagem, é o primeiro suspeito:
confira `free -m` e feche o que não estiver em uso.
