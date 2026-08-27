# cat-doc-reader-azure

Versao do CAT Document Reader preparada para deploy no ambiente Azure da Caterpillar.
Tres deployaveis independentes, um por servico:

- `frontend/` -> App Service (build estatico do Vite)
- `backend/`  -> App Service (FastAPI, dono da persistencia). Chama a function por HTTP.
- `function/` -> Function App (worker de IA, trigger HTTP `process_document`)

Autenticacao no Postgres e no Blob por Managed Identity (sem senha, sem connection
string). IA mockada por enquanto (`USE_REAL_SERVICES=false`); virar para real e config.

## Estrutura

```
shared/              fonte unica do dominio (config, db, models, storage) + pyproject
  shared/            o pacote em si (import `from shared...`)
backend/             FastAPI  -> App Service
  app/               rotas /documents e /dashboard; processing.py chama a function
  alembic/           migracoes (0001 inicial, 0002 packaging -> texto) do schema v2
  pyproject.toml     uv (shared por path dep) + indice do Artifactory
  requirements.txt   gerado do uv, third-party (o Oryx da Azure instala daqui)
  shared/            VENDORIZADO por scripts/build (gitignored)
function/            Function App (worker de IA)
  function_app.py    trigger HTTP process_document
  worker.py, pipeline/
  pyproject.toml     uv + indice do Artifactory
  requirements.txt   gerado do uv (a Function exige requirements.txt no remote build)
  shared/            VENDORIZADO por scripts/build (gitignored)
frontend/            React + Vite + Tailwind -> App Service
db/                  db-setup-v2.sql (schema v2; aplicar antes, ver DEPLOY.md Fase 0)
scripts/             build.sh / build.ps1 (vendoriza o shared antes do deploy)
```

## shared unico + vendoring (por que assim)

O `shared` e a fonte da verdade em UM lugar so: `shared/shared/`. Backend e function
importam `from shared...`. Em dev, cada um usa o shared como dependencia de path do uv
(`shared = { path = "../shared", editable = true }`). No deploy, cada servico vira um zip
self-contained na Azure (nao existe `../shared` la dentro), entao `scripts/build` copia
`shared/shared/` pra dentro de `backend/shared/` e `function/shared/` antes de empacotar.
Essas copias sao gitignored: **edite sempre em `shared/shared/`, nunca nas copias.**

O racional completo das decisoes de estrutura esta em `STRUCTURE.md`.

## Rodar / deployar

- Deploy passo a passo (CLI az, da VM da CAT): `DEPLOY.md`. Rode `scripts/build` antes de
  empacotar backend e function.
- Schema do banco (aplicar antes, Fase 0): `db/db-setup-v2.sql`.
