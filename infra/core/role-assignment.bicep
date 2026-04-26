@description('Name of the parent Azure OpenAI resource')
param aiResourceName string

@description('Principal ID to assign the role to')
param principalId string

@description('Principal type: User, Group, or ServicePrincipal')
param principalType string = 'User'

// Cognitive Services OpenAI User role
var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource aiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: aiResourceName
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, principalId, cognitiveServicesOpenAIUserRoleId)
  scope: aiAccount
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalType: principalType
  }
}
