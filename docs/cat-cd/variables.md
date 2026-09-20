# .github/variables — ausente de proposito

Os arquivos `global.env`, `build.env` e `pov.env` **nao** ficam neste
repositorio. Eles carregam identificadores da Caterpillar (subscription ID,
object ID do grupo AAD, client IDs das app registrations, host do Artifactory
interno) e foram removidos de todo o historico.

A fonte deles e o repo da Caterpillar, `AICOE_AIagent_DocumentReader_POV`.
Os workflows em `.github/workflows/` leem esses arquivos e, sem eles, nao
rodam a partir daqui — o que e esperado: o deploy acontece pelo repo da CAT,
que tambem tem as secrets de OIDC e do JFrog.

## Chaves esperadas, para referencia

`global.env` — igual em todos os ambientes:

    PROJECTNAME
    JF_URL

`build.env` — assinatura do job de build e versoes dos templates governados:

    AZURESUBSCRIPTIONID
    KEYVAULTARTIFACTVERSION
    APPSERVICEARTIFACTVERSION
    APPSERVICEPLANARTIFACTVERSION
    APPINSIGHTSARTIFACTVERSION
    LOGANALYTICSARTIFACTVERSION
    POSTGRESQLSERVERARTIFACTVERSION
    STORAGEACCOUNTARTIFACTVERSION
    COGNITIVESERVICEARTIFACTVERSION
    FUNCTIONSARTIFACTVERSION
    APPSERVICEAUTHSETTINGSARTIFACTVERSION
    COGNITIVESERVICECUSTOMFILTERARTIFACTVERSION

`pov.env` — alvo do ambiente POV:

    AZURESUBSCRIPTIONID
    RESOURCEGROUPLOCATION
    RESOURCEGROUPNAME
    DEVELOPERGROUPOBJECTID
    DEVELOPERGROUPNAME
    CLIENT_ID_FRONTEND
    CLIENT_ID_FLASK

## Ao sincronizar com o repo da CAT

Nunca propague a ausencia destes arquivos para la. Sincronize por diretorio de
aplicacao (`backend/`, `frontend/`, `function/`, `shared/`) e deixe `.github/`
e `aiagent-documentreader-infrastructure-azure/` fora do escopo.
