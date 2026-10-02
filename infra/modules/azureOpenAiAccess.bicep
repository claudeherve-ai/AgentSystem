targetScope = 'resourceGroup'

metadata description = 'Least-privilege Azure OpenAI inference role assignments for AgentSystem workloads.'

@description('Name of the existing Azure AI Services/OpenAI account.')
param accountName string

@description('Principal IDs that need chat-completion or embedding inference access.')
param inferencePrincipalIds array

@description('Cognitive Services OpenAI User built-in role definition ID.')
var openAiUserRoleDefinitionId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: accountName
}

resource inferenceAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in inferencePrincipalIds: {
    name: guid(account.id, principalId, openAiUserRoleDefinitionId)
    scope: account
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleDefinitionId)
    }
  }
]
