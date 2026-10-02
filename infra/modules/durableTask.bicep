// Durable Task Scheduler module: Consumption-tier scheduler with a single
// task hub used by the worker for durable orchestration state. Consumption
// SKU is public-network only (no private endpoint support), so access is
// secured via Entra ID RBAC (Durable Task Data Contributor) rather than
// network isolation.
metadata description = 'Durable Task Scheduler (Consumption) for AgentSystem orchestrations.'

@description('Azure region for the scheduler.')
param location string

@description('Tags applied to all resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('Name of the task hub used by the worker.')
param taskHubName string = 'agentsystem'

@description('Principal IDs granted Durable Task Data Contributor access for orchestration client operations.')
param dataContributorPrincipalIds array

@description('Principal IDs granted Durable Task Worker access for orchestration execution.')
param workerPrincipalIds array

@description('Durable Task Worker built-in role definition ID.')
var durableTaskWorkerRoleDefinitionId = '80d0d6b0-f522-40a4-8886-a5a11720c375'

@description('Durable Task Data Contributor built-in role definition ID.')
var durableTaskDataContributorRoleDefinitionId = '0ad04412-c4d5-4796-b79c-f76d14c8d402'

resource scheduler 'Microsoft.DurableTask/schedulers@2025-11-01' = {
  name: 'dts-${resourceToken}'
  location: location
  tags: tags
  properties: {
    ipAllowlist: [
      '0.0.0.0/0'
    ]
    sku: {
      name: 'Consumption'
    }
  }
}

resource taskHub 'Microsoft.DurableTask/schedulers/taskhubs@2025-11-01' = {
  parent: scheduler
  name: taskHubName
  properties: {}
}

resource dataContributorAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in dataContributorPrincipalIds: {
    name: guid(scheduler.id, principalId, durableTaskDataContributorRoleDefinitionId)
    scope: scheduler
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', durableTaskDataContributorRoleDefinitionId)
    }
  }
]

resource workerAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in workerPrincipalIds: {
    name: guid(scheduler.id, principalId, durableTaskWorkerRoleDefinitionId)
    scope: scheduler
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', durableTaskWorkerRoleDefinitionId)
    }
  }
]

@description('Resource ID of the Durable Task Scheduler.')
output schedulerId string = scheduler.id

@description('Endpoint of the Durable Task Scheduler.')
output endpoint string = scheduler.properties.endpoint

@description('Name of the task hub.')
output taskHubName string = taskHub.name
