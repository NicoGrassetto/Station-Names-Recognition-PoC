@description('Name of the Azure Speech resource')
param name string

@description('Location for the resource')
param location string

@description('SKU for the Speech resource. S0 (Standard) is required for Custom Speech.')
param skuName string = 'S0'

resource speechAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  kind: 'SpeechServices'
  sku: {
    name: skuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: name
    // NOTE: For production, set publicNetworkAccess to 'Disabled' and use Private Endpoints
    publicNetworkAccess: 'Enabled'
  }
}

output name string = speechAccount.name
output endpoint string = speechAccount.properties.endpoint
output id string = speechAccount.id
output region string = speechAccount.location
output principalId string = speechAccount.identity.principalId
