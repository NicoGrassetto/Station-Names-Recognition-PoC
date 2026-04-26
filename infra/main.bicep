targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (used for resource naming)')
param environmentName string

@description('Primary location for all resources')
param location string

@description('Principal ID of the user deploying the template (for RBAC)')
param principalId string

var resourceGroupName = 'rg-${environmentName}'
var aiResourceName = 'aoai-${environmentName}'
var realtimeDeploymentName = 'gpt-realtime-1-5'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
}

module aiResource 'core/ai-resource.bicep' = {
  name: 'ai-resource'
  scope: rg
  params: {
    name: aiResourceName
    location: location
  }
}

module realtimeDeployment 'core/ai-model-deployment.bicep' = {
  name: 'realtime-deployment'
  scope: rg
  params: {
    aiResourceName: aiResource.outputs.name
    deploymentName: realtimeDeploymentName
    modelName: 'gpt-realtime-1.5'
    modelVersion: '2026-02-23'
  }
}

module roleAssignment 'core/role-assignment.bicep' = {
  name: 'role-assignment'
  scope: rg
  params: {
    aiResourceName: aiResource.outputs.name
    principalId: principalId
  }
}

output AZURE_OPENAI_ENDPOINT string = aiResource.outputs.endpoint
output AZURE_OPENAI_DEPLOYMENT string = realtimeDeploymentName
output AZURE_RESOURCE_GROUP string = rg.name
