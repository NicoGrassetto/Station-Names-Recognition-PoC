@description('Name of the Azure OpenAI resource')
param name string

@description('Location for the resource')
param location string

resource aiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: name
    // NOTE: For production, set publicNetworkAccess to 'Disabled' and use Private Endpoints
    publicNetworkAccess: 'Enabled'
  }
}

output name string = aiAccount.name
output endpoint string = aiAccount.properties.endpoint
output id string = aiAccount.id
