// ============================================================================
// main.bicep — AI Agent Document Reader (First Provision)
// Uses governed ARM JSON templates from JFrog as modules.
// Creates all resources. No outputs. No cross-resource references.
// ============================================================================

// --------------- Project Identity ---------------
param projectName string
param environment string

// --------------- Identity ---------------
param developerGroupObjectId string = ''
param developerGroupName string = ''

// ======================== Naming Convention ========================

var prefix = '${projectName}-${environment}'

// Log Analytics & App Insights
var logAnalyticsName              = '${prefix}-log-analytics'
var logAnalyticsResourceId        = resourceId('Microsoft.OperationalInsights/workspaces', logAnalyticsName)
var appInsightsName               = '${prefix}-appinsights'

// Storage (max 24 chars, lowercase, no hyphens, must be globally unique)
var storageAccountName            = toLower(take('${replace(projectName, '-', '')}${environment}${uniqueString(resourceGroup().id)}', 24))

// App Service Plans
var appServicePlanFrontendName    = '${prefix}-frontend-appserviceplan'
var appServicePlanBackendName     = '${prefix}-backend-appserviceplan'

// App Services & Functions
var appServiceFrontendName        = '${prefix}-frontend-appservice'
var appServiceFastApiName         = '${prefix}-fastapi-appservice'
var functionAppBackendName        = '${prefix}-backend-function'

// Security (max 24 chars, must be globally unique)
var keyVaultName                  = take('${prefix}-kv-${uniqueString(resourceGroup().id)}', 24)

// AI / Cognitive
var openAiName                    = '${prefix}-openai'
var contentFilterName             = '${prefix}-content-filter'
var aiDocIntelligenceName         = '${prefix}-ai-docintelligence'
var aiLanguageName                = '${prefix}-ai-language'

// Database
var postgresServerName            = '${prefix}-postgresql-server'

// SKUs
var appServicePlanSku             = 'P1V3'
var openAiSku                     = 'S0'
var aiDocIntelligenceSku          = 'S0'
var aiLanguageSku                 = 'S'
var postgresSku                   = 'Standard_D2s_v3'
var postgresStorageGB             = 32
var postgresVersion               = '15'


// ======================== Resources ========================

// --------------- Log Analytics Workspace ---------------
module logAnalytics 'log-analytics.json' = {
  name: 'log-analytics'
  params: {
    workspaceName: logAnalyticsName
  }
}

// --------------- App Insights ---------------
module appInsights 'app-insights.json' = {
  name: 'app-insights'
  dependsOn: [logAnalytics]
  params: {
    appInsightsName: appInsightsName
    workspaceResourceId: logAnalyticsResourceId
  }
}

// --------------- Storage Account ---------------
module storageAccount 'storage-account.json' = {
  name: 'storage-account'
  params: {
    storageAccountName: storageAccountName
  }
}

// --------------- App Service Plans ---------------
module appServicePlanFrontend 'app-service-plan.json' = {
  name: 'app-service-plan-frontend'
  params: {
    appServicePlanName: appServicePlanFrontendName
    skuName: appServicePlanSku
    appServiceKind: 'linux'
  }
}

module appServicePlanBackend 'app-service-plan.json' = {
  name: 'app-service-plan-backend'
  params: {
    appServicePlanName: appServicePlanBackendName
    skuName: appServicePlanSku
    appServiceKind: 'linux'
  }
}

// --------------- Frontend App Service ---------------
module appServiceFrontend 'app-service.json' = {
  name: 'app-service-frontend'
  dependsOn: [appServicePlanFrontend]
  params: {
    appServiceName: appServiceFrontendName
    appServicePlanName: appServicePlanFrontendName
  }
}

// --------------- FastAPI Server App Service ---------------
module appServiceFastApi 'app-service.json' = {
  name: 'app-service-fastapi'
  dependsOn: [appServicePlanBackend]
  params: {
    appServiceName: appServiceFastApiName
    appServicePlanName: appServicePlanBackendName
  }
}

// --------------- Backend Function App ---------------
module functionAppBackend 'functions.json' = {
  name: 'function-app-backend'
  dependsOn: [storageAccount, appServicePlanBackend, appInsights]
  params: {
    functionsName: functionAppBackendName
    functionsRuntimeVersion: '~4'
    runtimeLanguage: 'python'
    appServicePlanType: 'App Service'
    appServicePlanName: appServicePlanBackendName
    storageAccountName: storageAccountName
    appInsightsName: appInsightsName
    linuxFxVersion: 'Python|3.11'
  }
}

// --------------- Key Vault ---------------
module keyVault 'key-vault.json' = {
  name: 'key-vault'
  params: {
    vaultName: keyVaultName
  }
}

// --------------- OpenAI ---------------
module openAi 'cognitive-service.json' = {
  name: 'openai'
  params: {
    name: openAiName
    sku: openAiSku
    kind: 'OpenAI'
  }
}

// --------------- Content Filter ---------------
module contentFilter 'cognitive-service-customfilter.json' = {
  name: 'content-filter'
  dependsOn: [openAi]
  params: {
    name: contentFilterName
    connectedAiInstance: openAiName
  }
}

// --------------- Document Intelligence ---------------
module aiDocIntelligence 'cognitive-service.json' = {
  name: 'ai-document-intelligence'
  params: {
    name: aiDocIntelligenceName
    sku: aiDocIntelligenceSku
    kind: 'FormRecognizer'
  }
}

// --------------- Language ---------------
module aiLanguage 'cognitive-service.json' = {
  name: 'ai-language'
  params: {
    name: aiLanguageName
    sku: aiLanguageSku
    kind: 'TextAnalytics'
  }
}

// --------------- PostgreSQL Flexible Server ---------------
module postgresServer 'postgresql-server.json' = {
  name: 'postgresql-server'
  params: {
    serverName: postgresServerName
    serverEdition: 'GeneralPurpose'
    skuName: postgresSku
    storageSizeGB: postgresStorageGB
    version: postgresVersion
    aadData: !empty(developerGroupObjectId) ? [
      {
        principalName: developerGroupName
        principalType: 'Group'
        objectID: developerGroupObjectId
      }
    ] : []
  }
}
