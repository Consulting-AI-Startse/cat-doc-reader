// ============================================================================
// model-deployment.bicep — AI Model Deployment
// Uses governed ARM JSON template from JFrog (cognitive-service-model-deployment.json)
// Deploys LLM and embedding models to an Azure OpenAI instance.
// Input: comma-separated model:version pairs (e.g. "gpt-4o:2024-08-06,text-embedding-ada-002:2")
// ============================================================================

// --------------- Project Identity ---------------
param projectName string
param environment string

// --------------- Model Input ---------------
// Comma-separated model:version pairs, e.g. "gpt-4o:2024-08-06,text-embedding-ada-002:2"
param modelVersionPairs string

// ======================== Naming Convention ========================
var prefix = '${projectName}-${environment}'
var openAiName = '${prefix}-openai'
var contentFilterName = '${prefix}-content-filter'

// ======================== Parse Input ========================
// Strip spaces (handles "gpt-4o:2024-08-06, text-embedding-ada-002:2") and split on comma
var sanitizedInput = replace(modelVersionPairs, ' ', '')
var rawPairsArray = split(sanitizedInput, ',')

// ======================== Model Deployments ========================
// Guard: skip empty entries (trailing comma) and entries missing a colon separator
module modelDeploy 'cognitive-service-model-deployment.json' = [for (pair, i) in rawPairsArray: if (pair != '' && length(split(pair, ':')) == 2 && split(pair, ':')[0] != '' && split(pair, ':')[1] != '') {
  name: 'model-deploy-${i}-${split(pair, ':')[0]}-${split(pair, ':')[1]}'
  params: {
    name: split(pair, ':')[0]
    connectedAiInstance: openAiName
    contentFilter: contentFilterName
    deploymentSku: 'GlobalStandard'
    tokensperminratelimit: 1000
    modelDetails: {
      format: 'OpenAI'
      name: split(pair, ':')[0]
      version: split(pair, ':')[1]
    }
  }
}]
