# CLAUDE.md

Leia isto antes de mexer no repo. O resto do contexto está no `README.md`
(o que o sistema faz), `STRUCTURE.md` (por que está assim) e `BACKLOG.md`
(o que vem a seguir).

## A regra central: este repo espelha o da Caterpillar

Existem **dois repositórios**, com históricos independentes — não dá para dar
merge entre eles:

| | |
|---|---|
| `Consulting-AI-Startse/cat-doc-reader` | este. Onde o trabalho é feito e onde dá para rodar local. |
| `AICOE_AIagent_DocumentReader_POV` (org da CAT) | **de onde sai o deploy**. Roda na VM da Caterpillar. |

**Toda mudança de fluxo ou de regra de negócio feita aqui tem de ser espelhada
para lá.** Senão a produção fica para trás — já aconteceu: este repo passou cinco
semanas parado no scaffold enquanto todo o trabalho ia para o da CAT.

O espelhamento é por **patch escopado**, não por merge. O precedente é o
`cat-fixes.patch`: `git diff` restrito aos diretórios de aplicação, conferido com
`git apply --check` antes de aplicar.

### O que espelha e o que nunca espelha

| espelha para a CAT | nunca espelha |
|---|---|
| `backend/`, `frontend/` | `function/pipeline/extractor_local.py` |
| `shared/shared/` | `function/pipeline/structurer_local.py` |
| `function/pipeline/structurer.py`, `extractor.py` | `function/requirements-local.txt` |
| `function/doc_worker.py`, `function_app.py` | `start-local.sh`, `stop-local.sh` |
| `backend/alembic/versions/`, `db/db-setup-v2.sql` | `docs/modo-local.md`, `docs/cat-cd/` |
| `check_rules.py`, `check_structurer.py` | `.env.local`, `.local/` |
| | as linhas locais do `.funcignore` |

Duas armadilhas de espelhamento, ambas capazes de quebrar a produção:

- **A ausência de `.github/` aqui é deliberada** (os workflows foram para
  `docs/cat-cd/` como referência). Propagar isso **apaga o CD da CAT**. Lá eles
  precisam continuar em `.github/workflows/`.
- **`.github/variables/*.env` foi removido do histórico deste repo** — carregava
  subscription ID, object ID de grupo AAD e client IDs da Caterpillar. Não
  recriar aqui, e não propagar a remoção para lá.

## Rodar e testar

```bash
./start-local.sh          # azurite, function, backend, frontend
./start-local.sh --status
./stop-local.sh

python check_rules.py        # 25/25
python check_structurer.py   # 14/14
cd function && python -c "import function_app"
```

O `import function_app` **antes de qualquer publish**. Já subimos um módulo que
compilava mas não importava (cinco funções indentadas 4 espaços a mais viraram
métodos de uma classe; `py_compile` passa porque nome se resolve em tempo de
chamada) e a function respondeu 404 em produção até alguém rodar isso.

O modo local de IA — Docling no lugar do Document Intelligence, OpenRouter no
lugar do Azure OpenAI — está em `docs/modo-local.md`, com a matriz de settings.

## Convenções

- **Identificadores em inglês, prosa e comentários em português.** Vale para
  código, docstrings, mensagens de commit e chaves de JSON.
- **Comentário explica o porquê, não o quê.** O padrão do repo é registrar a
  evidência: qual documento quebrou, qual número apareceu. Um comentário que
  repete a linha de código abaixo dele é ruído.
- **Marcar, nunca descartar.** Linha com problema recebe nota em `validation` e
  o documento vai para `needs_review`. Um filtro que apagava linha sem sete
  dígitos destruía os itens de dois dos quatro documentos de teste, porque
  `674-8657` é part number legítimo.
- **Documento gravado sem explicação é bug.** Ou estoura, ou deixa nota. Já
  tivemos documento salvo vazio e tela em branco para o revisor, sem uma pista.

## Armadilhas que já custaram tempo

**Filtro de e-mail corrompe arquivo em trânsito.** O URL Defense da Caterpillar
reescreve URLs literais **e nomes terminados em `.py`** (`.py` é o TLD do
Paraguai). Já quebrou: o escopo do token do Azure OpenAI, o `start-local.ps1`
(`--blobHost http://127.0.0.1`, que não é host válido), o `sync-para-vm.txt`
inteiro, e docstrings de dois scripts de teste. Monte URLs e nomes de arquivo em
pedaços (`("azurewebsites","net") -join "."`), e rode
`grep -c urldefense` em qualquer coisa que veio por e-mail antes de aplicar.

**Nunca edite `backend/shared/` nem `function/shared/`.** São geradas por
`scripts/build.sh` a partir de `shared/shared/`. Editar a cópia funciona até o
próximo build sobrescrever em silêncio.

**`shared/pyproject.toml` pede Python >= 3.14, mas a Function App roda 3.11.**
Só não quebra porque o deploy vendoriza os arquivos em vez de instalar o pacote.
Num venv local de 3.11 o `uv pip install -e ../shared` falha — use
`scripts/build.sh`, que é o que o deploy faz.

**Confiança auto-reportada pelo modelo não vale nada.** Um documento voltou com
`confidence: 0.95` e quatro defeitos. Confiança útil vem do OCR (confiança por
palavra) ou da aritmética (soma das linhas contra o total impresso).

**`temperature=0` não é determinismo.** A mesma fatura, no mesmo modelo, deu
`total 22944.02` numa rodada e `22.94` na seguinte. Medir acurácia com uma
rodada só é medir ruído.

**Confira por `length(value)`, não a olho.** O `az ... -o table` reflui valores
longos, e isso nos fez diagnosticar um `FUNCTION_URL` truncado como ausente. O
mesmo vale para migração: confira `information_schema.columns`, não o
`alembic current` — uma migração pode estar carimbada sem estar aplicada.

**Um run de infraestrutura pode apagar as app settings.** O `functions.json`
monta `siteConfig.appSettings` como um `concat(...)` fechado, então reprovisionar
zera o que foi configurado por fora. Depois de qualquer run de infra, reconfira
as settings — `DATABASE_URL` sumiu assim uma vez.

## Onde ficam as coisas

```
shared/shared/       fonte unica: config, db, models, storage
backend/app/api/     rotas (documents, dashboard)
function/            function_app.py (3 gatilhos) + doc_worker.py + pipeline/
frontend/src/        paginas em pages/, rotas inline em main.tsx
backend/alembic/     migracoes; db/db-setup-v2.sql e gerado delas
docs/modo-local.md   modo local de IA
docs/cat-cd/         CD da CAT, so referencia -- nao roda daqui
```
