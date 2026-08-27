# shared

Dominio compartilhado do CAT Document Reader: `config`, `db`, `models`, `storage`.
E a **fonte unica** da verdade. O backend e a function importam `from shared...`.

## Fonte unica + vendoring

O codigo compartilhado vive versionado em UM lugar so: `shared/shared/`. Em dev, backend
e function usam este pacote como dependencia de path do uv
(`shared = { path = "../shared", editable = true }`). No deploy, `scripts/build` copia
`shared/shared/` pra dentro de `backend/shared/` e `function/shared/`, porque cada deploy
da Azure e um zip self-contained (sem acesso a `../shared`).

**Nunca edite `backend/shared/` nem `function/shared/`** (sao geradas e gitignored).
Edite sempre aqui, em `shared/shared/`.
