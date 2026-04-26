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
var speechResourceName = 'speech-${environmentName}'
// Storage account names: 3-24 lowercase alphanumeric. Strip non-alphanumerics from environmentName.
var storageAccountName = take(toLower(replace(replace('st${environmentName}${uniqueString(subscription().id, environmentName)}', '-', ''), '_', '')), 24)
var trainingContainerName = 'speech-training'

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
module speechResource 'core/speech-resource.bicep' = {
  name: 'speech-resource'
  scope: rg
  params: {
    name: speechResourceName
    location: location
    skuName: 'S0'
  }
}

module speechRoleAssignment 'core/speech-role-assignment.bicep' = {
  name: 'speech-role-assignment'
  scope: rg
  params: {
    speechResourceName: speechResource.outputs.name
    principalId: principalId
  }
}

module storageResource 'core/storage-resource.bicep' = {
  name: 'storage-resource'
  scope: rg
  params: {
    name: storageAccountName
    location: location
    containerName: trainingContainerName
    readerPrincipalId: speechResource.outputs.principalId
    readerPrincipalType: 'ServicePrincipal'
    userPrincipalId: principalId
  }
}

output AZURE_OPENAI_ENDPOINT string = aiResource.outputs.endpoint
output AZURE_OPENAI_DEPLOYMENT string = realtimeDeploymentName
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_SPEECH_ENDPOINT string = speechResource.outputs.endpoint
output AZURE_SPEECH_RESOURCE_NAME string = speechResource.outputs.name
output AZURE_SPEECH_REGION string = speechResource.outputs.region
output AZURE_STORAGE_ACCOUNT string = storageResource.outputs.name
output AZURE_STORAGE_BLOB_ENDPOINT string = storageResource.outputs.blobEndpoint
output AZURE_STORAGE_CONTAINER string = storageResource.outputs.containerName
