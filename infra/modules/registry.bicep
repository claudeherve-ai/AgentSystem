// Container Registry module: Premium SKU (required for private endpoints and
// zone redundancy), admin user disabled, anonymous pull disabled, public
// network access disabled, private endpoint into the AgentSystem VNet, and
// AcrPull role assignments for every workload identity that needs to pull
// images.
metadata description = 'Azure Container Registry for AgentSystem container images.'

@description('Azure region for the registry and its private endpoint.')
param location string

@description('Tags applied to all resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@allowed([
  'Enabled'
  'Disabled'
])
@description('Registry public network state. Enabled is allowed only during the image bootstrap pass; the final deployment must set Disabled.')
param publicNetworkAccess string = 'Disabled'

@description('Resource ID of the subnet used for the private endpoint.')
param privateEndpointSubnetId string

@description('Resource ID of the privatelink.azurecr.io private DNS zone.')
param privateDnsZoneId string

@description('Principal IDs of workload identities that require AcrPull access.')
param pullerPrincipalIds array

@description('AcrPull built-in role definition ID.')
var acrPullRoleDefinitionId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: 'cr${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Premium'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: publicNetworkAccess
    networkRuleBypassOptions: 'AzureServices'
    zoneRedundancy: 'Disabled'
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      retentionPolicy: {
        status: 'enabled'
        days: 30
      }
      exportPolicy: {
        status: 'enabled'
      }
    }
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-acr-${resourceToken}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pe-acr-${resourceToken}'
        properties: {
          privateLinkServiceId: registry.id
          groupIds: [
            'registry'
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
        name: 'privatelink-azurecr-io'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

resource acrPullAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in pullerPrincipalIds: {
    name: guid(registry.id, principalId, acrPullRoleDefinitionId)
    scope: registry
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleDefinitionId)
    }
  }
]

@description('Resource ID of the container registry.')
output registryId string = registry.id

@description('Name of the container registry.')
output registryName string = registry.name

@description('Login server (FQDN) of the container registry.')
output loginServer string = registry.properties.loginServer
