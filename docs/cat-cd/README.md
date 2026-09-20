# docs/cat-cd — o CD da Caterpillar, como referência

Cópia dos workflows que fazem o deploy do POV. **Eles não rodam a partir deste
repositório**, e estão aqui de propósito, fora de `.github/workflows/`, para
que isso fique explícito.

Três motivos pelos quais não rodam daqui:

1. Leem `.github/variables/*.env`, que carregam identificadores da Caterpillar
   e foram removidos de todo o histórico deste repo. Ver `variables.md` para as
   chaves esperadas.
2. Dependem de secrets da org da CAT: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` e
   `ARTIFACTORY_ACCESS_TOKEN`.
3. Baixam os templates ARM governados do JFrog interno, inalcançável de fora da
   rede da Caterpillar.

O deploy de verdade acontece pelo repo `AICOE_AIagent_DocumentReader_POV`, na
org da Caterpillar. Alterar qualquer coisa aqui não muda nada lá.

## Para que servem então

São a referência de como o ambiente é provisionado, e a base do documento de
change-request que pedimos ao Cloud COE. Ler junto de
`aiagent-documentreader-infrastructure-azure/bicep/`, que continua no lugar
original porque não é executável por si só.

| arquivo | o que faz |
|---|---|
| `aiagent-documentreader-infra-provision.yml` | baixa os templates governados do JFrog, monta os artefatos e chama o deploy |
| `aiagent-documentreader-infra-deploy.yml` | aplica `main.bicep` e `rbac.bicep` no resource group |
| `deploy-model.yml` | publica deployments de modelo no Azure OpenAI (`modelVersionPairs`) |
| `variables.md` | chaves esperadas dos três `.env`, sem valores |

## Ao sincronizar com o repo da CAT

Nunca propague esta movimentação para lá. Lá os arquivos têm de continuar em
`.github/workflows/`, senão o CD para de existir. A sincronização deve ficar
restrita a `backend/`, `frontend/`, `function/` e `shared/`.
