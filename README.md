# cat-doc-reader

Leitor de faturas de fornecedor da Caterpillar: sobe o PDF, o pipeline extrai os
invoices e as linhas de part number, e um humano revisa antes de aprovar.

Este repo é o **espelho da StartSe**; o deploy acontece pelo repo da Caterpillar.
A relação entre os dois, e o que pode ou não ser espelhado, está no `CLAUDE.md`.

Três deployáveis independentes, um por serviço:

- `frontend/` → App Service (build estático do Vite)
- `backend/` → App Service (FastAPI, dono da persistência). Não processa nada:
  enfileira chamando a function por HTTP.
- `function/` → Function App (worker de IA)

Autenticação no Postgres e no Blob por Managed Identity na Azure (sem senha, sem
connection string). **A IA real está em produção** — Document Intelligence
(`prebuilt-layout`) para OCR e Azure OpenAI (`gpt-4.1`) para estruturar.
`USE_REAL_SERVICES=false` cai em mock.

## Como um documento é processado

```
upload  ->  backend grava o blob e chama a function (HTTP)
        ->  process_document enfileira em 'document-processing'
        ->  process_document_worker (queue trigger) faz o trabalho pesado
        ->  extractor (OCR) -> structurer (LLM) -> validações -> banco
        ->  status extracted | needs_review | error
```

São **três funções**, não uma (`function/function_app.py`):

| função | gatilho | papel |
|---|---|---|
| `process_document` | HTTP POST | só enfileira e responde na hora |
| `process_document_worker` | fila `document-processing` | o processamento de verdade |
| `process_document_poison` | fila `...-poison` | mensagem que falhou 2 vezes |

A fila existe porque documento grande estourava o timeout do gatilho HTTP: 35
páginas não cabem em uma requisição síncrona.

## Estrutura

```
shared/              fonte unica do dominio
  shared/            o pacote em si (import `from shared...`): config, db, models,
                     storage, dedupe (chave de duplicata), parts (lista de PN),
                     confidence e metrics (agregados puros, testados sem banco)
backend/             FastAPI -> App Service
  app/api/           rotas /documents, /dashboard, /parts e /suppliers
  app/processing.py  chama a function (nao processa)
  alembic/versions/  migracoes 0001..0008
function/            Function App (worker de IA)
  function_app.py    os tres gatilhos acima
  doc_worker.py      orquestra: storage -> extractor -> structurer -> banco
  pipeline/          extractor.py (OCR), pages.py (invoice x packing list, antes
                     do LLM), structurer.py (LLM), confidence.py (nota por campo)
frontend/            React + Vite + Tailwind -> App Service
  src/pages/         Dashboard (lista e upload), DocumentDetail (revisao),
                     PartNumbers, Suppliers, Performance (metricas do agente)
db/db-setup-v2.sql   schema achatado na head 0008 (GERADO, ver STRUCTURE.md)
aiagent-documentreader-infrastructure-azure/
  workflows/         app-ci.yml e app-deploy.yml: o CI/CD de aplicacao da CAT
                     (la eles rodam de .github/workflows/, ver CLAUDE.md)
docs/modo-local.md   modo local de desenvolvimento (Docling + OpenRouter)
docs/cat-cd/         workflows de infraestrutura da CAT, so como referencia
scripts/build.sh     vendoriza o shared antes do deploy
```

## shared único + vendoring (por que assim)

O `shared` é a fonte da verdade em UM lugar: `shared/shared/`. Backend e function
importam `from shared...`. No deploy, cada serviço vira um zip self-contained na
Azure (não existe `../shared` lá dentro), então `scripts/build.sh` copia
`shared/shared/` para `backend/shared/` e `function/shared/`.

Essas cópias são gitignored: **edite sempre em `shared/shared/`, nunca nas
cópias.** O racional completo está em `STRUCTURE.md`.

## Rodar local

```bash
./start-local.sh          # azurite, function, backend e frontend
./start-local.sh --status
./stop-local.sh
```

Ferramentas e versões necessárias: `docs/ambiente.md`. O modo local de IA
(Docling no lugar do Document Intelligence, OpenRouter no lugar do Azure OpenAI)
está em `docs/modo-local.md`. No Windows/VM o equivalente é o `start-local.ps1`.

## Testes

```bash
python check_rules.py        # regras puras: _num, PART_NUMBER_RE, duplicata,
                             # confianca, paginas, metricas -- roda no CI
python check_structurer.py   # structurer contra o gabarito e o CIV (manual)
cd function && python -c "import function_app"

# precisam de banco migrado e APAGAM dados dele -- aponte para uma base de teste:
DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/dedupe_test \
    python check_parts.py      # lista de PN e regra de serial
DATABASE_URL=postgresql+psycopg://invoice:invoice@localhost:5432/dedupe_test \
    python check_dedupe.py     # duplicata por (invoice, fornecedor)
```

O `import function_app` **antes de qualquer publish**: já subimos uma vez um
módulo que compilava mas não importava, e a function respondeu 404 em produção
até alguém rodar isso.

## Backlog e deploy

- Próximas features, ponderadas: `BACKLOG.md`
- O que já foi espelhado para o repo da CAT: `docs/sync-cat.md`
- Deploy de codigo e o workflow `app-deploy.yml` (push na `main` da CAT ou
  dispatch manual). `DEPLOY.md` e o roteiro do que o workflow nao faz:
  migracao de schema pelo webssh, privilegios das Managed Identities, rede.
- Schema do banco (Fase 0): `db/db-setup-v2.sql`.
