# STRUCTURE.md — por que o repo esta assim

Racional das decisoes de estrutura do `cat-doc-reader-azure`. Leia junto do `README.md`.

## Tres deployaveis (backend, frontend, function)

A plataforma da CAT provisionou tres servicos no resource group: dois App Services
(FastAPI e frontend) e um Function App. Os tres diretorios mapeiam 1:1 nesses servicos, e
cada um vira um zip proprio no deploy. Backend e function sao separados de proposito: o
backend (dono da persistencia) chama a function (worker de IA) por HTTP
(`FUNCTION_URL` + `FUNCTION_KEY`).

## shared: fonte unica + vendoring no build

O codigo compartilhado (config, db, models, storage) vive em UM lugar: `shared/shared/`.
Backend e function importam `from shared...`.

O problema: cada deploy da Azure e um zip self-contained (a raiz do zip vira o `wwwroot`),
e la dentro nao existe `../shared`. Uma dependencia de path nao sobrevive ao deploy.

A solucao (sem cair na duplicacao que gera drift):
- Dev: backend e function usam o shared como dependencia de path do uv
  (`shared = { path = "../shared", editable = true }`). Uma fonte so.
- Deploy: `scripts/build` copia `shared/shared/` pra dentro de `backend/shared/` e
  `function/shared/` antes do zip. Essas copias sao gitignored: nao entram no git, entao
  nao ha duas versoes versionadas divergindo.

Regra de ouro: **edite so `shared/shared/`.** As copias sao geradas.

Alternativa futura (produto final): publicar o `shared` como wheel no Artifactory e
backend/function dependerem de `shared==x.y` como qualquer lib. Mais limpo, mais pesado
(precisa de repo de publish no JFrog e processo de release). Overkill pra POV.

## uv como fonte, requirements.txt como artefato de deploy

O COE da CAT padroniza `uv` (+ indice no Artifactory/JFrog, nao PyPI). Mas o build da
Azure (Oryx) instala com pip a partir de `requirements.txt`, e a Function App EXIGE
`requirements.txt` no remote build (uv nao e suportado nesse caminho). O backend (App
Service) ja aceita `pyproject.toml` + `uv.lock` desde mai/2026, mas apontar o uv nativo
pro Artifactory ali ainda nao e documentado.

Entao:
- `pyproject.toml` (+ `uv.lock`, gerado na VM) e a fonte da verdade das deps, com o indice
  do Artifactory configurado (bloco `[[tool.uv.index]]` ou a env `UV_INDEX_URL`).
- `requirements.txt` e um artefato gerado do uv, so third-party (o `shared` nao entra,
  porque e vendorizado como pasta). Regenerar:
  `uv export --no-hashes --format requirements-txt --no-emit-project > requirements.txt`
  (e conferir que nenhuma linha de path do `shared` sobrou).
- Na Azure, o indice do Artifactory entra por App Setting `PIP_EXTRA_INDEX_URL`
  (mais seguro) ou `PIP_INDEX_URL`.

## Banco: alembic no repo + db-setup-v2.sql

`backend/alembic/` tem as migracoes (0001 inicial, 0002 packaging -> texto), fonte da
verdade do schema. `db/db-setup-v2.sql` e o schema achatado (head 0002) pra aplicar direto
no ambiente da CAT (Fase 0 do DEPLOY.md), gerado a partir das migracoes.

## Fluxo de deploy (resumo)

1. Aplicar o schema: `db/db-setup-v2.sql` (uma vez).
2. `scripts/build` (vendoriza o shared).
3. Empacotar e subir cada servico (ver `DEPLOY.md`).
