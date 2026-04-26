@description('Name of the parent Azure Speech resource')
param speechResourceName string

@description('Principal ID to assign the role to')
param principalId string

@description('Principal type: User, Group, or ServicePrincipal')
param principalType string = 'User'

// Cognitive Services Speech User - data plane (recognition / synthesis)
var cognitiveServicesSpeechUserRoleId = 'f2dc8367-1007-4938-bd23-fe263f013447'

// Cognitive Services Speech Contributor - manage Custom Speech projects, datasets, models, endpoints
var cognitiveServicesSpeechContributorRoleId = '0e75ca1e-0464-4b4d-8b93-68208a576181'

resource speechAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: speechResourceName
}

resource speechUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(speechAccount.id, principalId, cognitiveServicesSpeechUserRoleId)
  scope: speechAccount
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesSpeechUserRoleId)
    principalType: principalType
  }
}

resource speechContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(speechAccount.id, principalId, cognitiveServicesSpeechContributorRoleId)
  scope: speechAccount
  properties: {
    principalId: principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesSpeechContributorRoleId)
    principalType: principalType
  }
}
