// ============================================================================
// rbac.bicep — AI Agent Document Reader RBAC & Network Tags (Second Provision)
// Cross-service role assignments and egress/ingress network tags
// Computes resource names from projectName + environment (same as main.bicep)
// ============================================================================

// =============================================================================
// PARAMETERS
// =============================================================================

param projectName string
param environment string
param developerGroupObjectId string = ''

// =============================================================================
// NAMING CONVENTION (mirrors main.bicep)
// =============================================================================

var prefix = '${projectName}-${environment}'

// Compute
var frontendAppServiceName        = '${prefix}-frontend-appservice'
var fastApiAppServiceName         = '${prefix}-fastapi-appservice'
var backendFunctionAppName        = '${prefix}-backend-function'

// AI / Cognitive
var openAiName                    = '${prefix}-openai'
var aiDocIntelligenceName         = '${prefix}-ai-docintelligence'
var aiLanguageName                = '${prefix}-ai-language'

// Storage & Security (same uniqueString logic as main.bicep)
var storageAccountName            = toLower(take('${replace(projectName, '-', '')}${environment}${uniqueString(resourceGroup().id)}', 24))
var keyVaultName                  = take('${prefix}-kv-${uniqueString(resourceGroup().id)}', 24)

// Monitoring
var appInsightsName               = '${prefix}-appinsights'

// Database
var postgresServerName            = '${prefix}-postgresql-server'

// =============================================================================
// EXISTING RESOURCE REFERENCES
// =============================================================================

// --- Compute ---
resource existingFrontendApp 'Microsoft.Web/sites@2022-09-01' existing = {
  name: frontendAppServiceName
}

resource existingFastApiApp 'Microsoft.Web/sites@2022-09-01' existing = {
  name: fastApiAppServiceName
}

resource existingBackendFunction 'Microsoft.Web/sites@2022-09-01' existing = {
  name: backendFunctionAppName
}

// Principal IDs derived from existing resources
var frontendPrincipalId       = existingFrontendApp.identity.principalId
var fastApiPrincipalId        = existingFastApiApp.identity.principalId
var backendFuncPrincipalId    = existingBackendFunction.identity.principalId

// --- Storage & Security ---
resource existingStorageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

// --- Monitoring ---
resource existingAppInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

// --- Database ---
resource existingPostgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2022-12-01' existing = {
  name: postgresServerName
}

// =============================================================================
// RBAC ASSIGNMENTS & NETWORK TAGS
// =============================================================================

// ---------------------------------------------------------------------------
// App Insights: Monitoring Metrics Publisher → Frontend, Backend Function
// ---------------------------------------------------------------------------
resource appInsightsTags 'Microsoft.Resources/tags@2022-09-01' = {
  name: 'default'
  scope: existingAppInsights
  properties: {
    tags: {
      roleAssignments1: '${frontendPrincipalId} Monitoring Metrics Publisher|${fastApiPrincipalId} Monitoring Metrics Publisher|${backendFuncPrincipalId} Monitoring Metrics Publisher'
    }
  }
}

// ---------------------------------------------------------------------------
// Storage Account: Storage Blob Data Contributor → FastAPI Server, Backend Function
// ---------------------------------------------------------------------------
resource storageAccountTags 'Microsoft.Resources/tags@2022-09-01' = {
  name: 'default'
  scope: existingStorageAccount
  properties: {
    tags: {
      roleAssignments1: '${fastApiPrincipalId} Storage Blob Data Contributor|${backendFuncPrincipalId} Storage Blob Data Contributor'
    }
  }
}

// ---------------------------------------------------------------------------
// OpenAI, Document Intelligence, Language: Role assignments applied via
// Azure CLI step with elevated permissions (bypasses Bicep permission issues)
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// PostgreSQL: Ingress from FastAPI Server and Backend Function
// ---------------------------------------------------------------------------
resource postgresServerTags 'Microsoft.Resources/tags@2022-09-01' = {
  name: 'default'
  scope: existingPostgresServer
  properties: {
    tags: {
      ingress1: '${fastApiAppServiceName}|${backendFunctionAppName}'
    }
  }
}

// =============================================================================
// NETWORK EGRESS TAGS ON COMPUTE RESOURCES
// =============================================================================

// ---------------------------------------------------------------------------
// Frontend App Service: Egress → FastAPI Server, Key Vault
// ---------------------------------------------------------------------------
resource frontendAppTags 'Microsoft.Resources/tags@2022-09-01' = {
  name: 'default'
  scope: existingFrontendApp
  properties: {
    tags: {
      egress1: fastApiAppServiceName
      egress2: keyVaultName
    }
  }
}

// ---------------------------------------------------------------------------
// FastAPI Server App Service: Egress → PostgreSQL, Storage, Key Vault
// ---------------------------------------------------------------------------
resource fastApiAppTags 'Microsoft.Resources/tags@2022-09-01' = {
  name: 'default'
  scope: existingFastApiApp
  properties: {
    tags: {
      egress1: '${postgresServerName}|${storageAccountName}'
      egress2: keyVaultName
      ingress1: frontendAppServiceName
    }
  }
}

// ---------------------------------------------------------------------------
// Backend Function App: Egress → AI Services, DB, Key Vault
// ---------------------------------------------------------------------------
resource backendFunctionTags 'Microsoft.Resources/tags@2022-09-01' = {
  name: 'default'
  scope: existingBackendFunction
  properties: {
    tags: {
      egress1: '${openAiName}|${aiDocIntelligenceName}|${aiLanguageName}'
      egress2: postgresServerName
      egress3: '${storageAccountName}|${keyVaultName}'
    }
  }
}

// =============================================================================
// KEY VAULT OVERRIDE (access policies + object IDs from compute principal IDs)
// =============================================================================
module keyVaultOverride 'key-vault.json' = {
  name: 'key-vault-override'
  params: {
    vaultName: keyVaultName
    objectIdList: !empty(developerGroupObjectId) ? [
      frontendPrincipalId
      fastApiPrincipalId
      backendFuncPrincipalId
      developerGroupObjectId
    ] : [
      frontendPrincipalId
      fastApiPrincipalId
      backendFuncPrincipalId
    ]
    accessPolicies: !empty(developerGroupObjectId) ? [
      {
        tenantId: tenant().tenantId
        objectId: developerGroupObjectId
        permissions: {
          keys: [ 'All' ]
          secrets: [ 'All' ]
          certificates: [ 'All' ]
        }
      }
    ] : []
    tags: {
      ingress1: '${frontendAppServiceName}|${fastApiAppServiceName}|${backendFunctionAppName}'
    }
  }
}
