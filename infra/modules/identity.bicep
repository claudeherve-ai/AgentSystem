// Identity module: one dedicated user-assigned managed identity per
// workload (frontend, API, worker, operator console, schema migration). Each
// Container App or Job
// uses only its own user-assigned identity (no system-assigned identity),
// which keeps the deployment within the plan's identity budget and gives a
// stable, pre-provisionable principal ID for RBAC wiring (ACR pull, Key
// Vault secret access, Storage/Durable Task/Postgres/Redis roles) that can
// be granted before the Container App itself is created.
metadata description = 'User-assigned managed identities for AgentSystem workloads.'

@description('Azure region for identity resources.')
param location string

@description('Tags applied to all resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-api-${resourceToken}'
  location: location
  tags: tags
}

resource workerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-worker-${resourceToken}'
  location: location
  tags: tags
}

resource frontendIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-frontend-${resourceToken}'
  location: location
  tags: tags
}

resource operatorIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-operator-${resourceToken}'
  location: location
  tags: tags
}

resource migrationIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-migrate-${resourceToken}'
  location: location
  tags: tags
}

@description('Resource ID and principal ID of the API workload identity.')
output apiIdentity object = {
  id: apiIdentity.id
  principalId: apiIdentity.properties.principalId
  clientId: apiIdentity.properties.clientId
}

@description('Resource ID and principal ID of the worker workload identity.')
output workerIdentity object = {
  id: workerIdentity.id
  principalId: workerIdentity.properties.principalId
  clientId: workerIdentity.properties.clientId
}

@description('Resource ID and principal ID of the frontend workload identity.')
output frontendIdentity object = {
  id: frontendIdentity.id
  principalId: frontendIdentity.properties.principalId
  clientId: frontendIdentity.properties.clientId
}

@description('Resource ID and principal ID of the operator console workload identity.')
output operatorIdentity object = {
  id: operatorIdentity.id
  principalId: operatorIdentity.properties.principalId
  clientId: operatorIdentity.properties.clientId
}

@description('Resource ID, principal ID, client ID, and name of the schema-migration identity.')
output migrationIdentity object = {
  id: migrationIdentity.id
  principalId: migrationIdentity.properties.principalId
  clientId: migrationIdentity.properties.clientId
  name: migrationIdentity.name
}
