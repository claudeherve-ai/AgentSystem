// Key Vault module: RBAC-authorized, soft-delete + purge protection enabled,
// public network access disabled, private endpoint into the AgentSystem VNet.
// Secrets are populated by CI/CD or operators after provisioning; Container
// Apps reference them via configuration.secrets[].keyVaultUrl bound to their
// managed identity, never via hardcoded values.
metadata description = 'Key Vault for AgentSystem application secrets.'

@description('Azure region for the Key Vault and its private endpoint.')
param location string

@description('Tags applied to all resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('Resource ID of the subnet used for the private endpoint.')
param privateEndpointSubnetId string

@description('Resource ID of the privatelink.vaultcore.azure.net private DNS zone.')
param privateDnsZoneId string

@description('Microsoft Entra tenant ID used by the vault.')
param tenantId string = subscription().tenantId

@description('Principal IDs granted the Key Vault Secrets User role (read-only secret access).')
param secretsUserPrincipalIds array

@description('Name of the secret used by Container Apps built-in Microsoft Entra authentication.')
param entraClientSecretName string

@secure()
@description('Microsoft Entra application client secret. Supplied only as a secure deployment parameter.')
param entraClientSecret string

@description('Key Vault Secrets User built-in role definition ID.')
var secretsUserRoleDefinitionId = '4633458b-17de-408a-b874-0445c86b69e6'

resource keyVault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: 'kv-${resourceToken}'
  location: location
  tags: tags
  properties: {
    tenantId: tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    accessPolicies: []
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource entraProviderSecret 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = {
  parent: keyVault
  name: entraClientSecretName
  properties: {
    value: entraClientSecret
    attributes: {
      enabled: true
    }
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-kv-${resourceToken}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pe-kv-${resourceToken}'
        properties: {
          privateLinkServiceId: keyVault.id
          groupIds: [
            'vault'
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
        name: 'privatelink-vaultcore-azure-net'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

resource secretsUserAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in secretsUserPrincipalIds: {
    name: guid(keyVault.id, principalId, secretsUserRoleDefinitionId)
    scope: keyVault
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsUserRoleDefinitionId)
    }
  }
]

@description('Resource ID of the Key Vault.')
output keyVaultId string = keyVault.id

@description('Name of the Key Vault.')
output keyVaultName string = keyVault.name

@description('URI of the Key Vault.')
output keyVaultUri string = keyVault.properties.vaultUri
