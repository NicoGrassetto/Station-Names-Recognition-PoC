@description('Name of the parent Azure OpenAI resource')
param aiResourceName string

@description('Name for the model deployment')
param deploymentName string

@description('Model name to deploy')
param modelName string

@description('Model version to deploy')
param modelVersion string

@description('Deployment capacity (TPM in thousands)')
param capacity int = 1

resource aiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: aiResourceName
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiAccount
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

output name string = deployment.name
