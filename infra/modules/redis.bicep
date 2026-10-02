// Redis module: Azure Managed Redis (Redis Enterprise) Balanced B0, Entra-only
// authentication (access keys disabled), TLS-encrypted client protocol, and a
// private endpoint into the AgentSystem VNet. Data-plane access is granted via
// access policy assignments mapped to workload managed identities, not shared
// keys.
metadata description = 'Azure Managed Redis cache for AgentSystem coordination/caching.'

@description('Azure region for the Redis cluster and its private endpoint.')
param location string

@description('Tags applied to all resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('Resource ID of the subnet used for the private endpoint.')
param privateEndpointSubnetId string

@description('Resource ID of the privatelink.redis.azure.net private DNS zone.')
param privateDnsZoneId string

@description('Array of { principalId, principalName } objects granted default data-access on the Redis database via Entra ID.')
param dataAccessPrincipals array

resource redisEnterprise 'Microsoft.Cache/redisEnterprise@2025-04-01' = {
  name: 'redis-${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Balanced_B0'
  }
  properties: {
    minimumTlsVersion: '1.2'
  }
}

resource database 'Microsoft.Cache/redisEnterprise/databases@2025-04-01' = {
  parent: redisEnterprise
  name: 'default'
  properties: {
    clientProtocol: 'Encrypted'
    clusteringPolicy: 'EnterpriseCluster'
    evictionPolicy: 'NoEviction'
    accessKeysAuthentication: 'Disabled'
    port: 10000
  }
}

// Access policy assignment resource names must be alphanumeric only (no
// hyphens), so principal-derived unique suffixes are stripped of non
// alphanumeric characters via a safe, deterministic transform.
resource accessPolicyAssignments 'Microsoft.Cache/redisEnterprise/databases/accessPolicyAssignments@2025-04-01' = [
  for principal in dataAccessPrincipals: {
    parent: database
    name: uniqueString(principal.principalId)
    properties: {
      accessPolicyName: 'default'
      user: {
        objectId: principal.principalId
      }
    }
  }
]

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-redis-${resourceToken}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pe-redis-${resourceToken}'
        properties: {
          privateLinkServiceId: redisEnterprise.id
          groupIds: [
            'redisEnterprise'
          ]
        }
      }
    ]
  }
}

resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-redis-azure-net'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

@description('Resource ID of the Redis Enterprise cluster.')
output redisId string = redisEnterprise.id

@description('Host name of the Redis Enterprise cluster.')
output hostName string = redisEnterprise.properties.hostName

@description('Resource ID of the default database.')
output databaseId string = database.id

@description('TLS port of the default database.')
output port int = database.properties.port
