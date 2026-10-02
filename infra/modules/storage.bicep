// Storage module: ZRS blob storage for artifacts, shared-key access disabled
// (Entra-only / managed-identity data access), TLS 1.2 minimum, public network
// access disabled, private endpoint into the AgentSystem VNet, soft delete and
// versioning enabled on the blob service.
metadata description = 'Blob storage for AgentSystem artifacts.'

@description('Azure region for the storage account and its private endpoint.')
param location string

@description('Tags applied to all resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('Resource ID of the subnet used for the private endpoint.')
param privateEndpointSubnetId string

@description('Resource ID of the privatelink.blob.core.windows.net private DNS zone.')
param privateDnsZoneId string

@description('Name of the blob container used for durable artifacts.')
param artifactsContainerName string = 'artifacts'

@description('Principal IDs granted the Storage Blob Data Contributor role.')
param blobDataContributorPrincipalIds array

@description('Storage Blob Data Contributor built-in role definition ID.')
var blobDataContributorRoleDefinitionId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: 'st${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Standard_ZRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    isVersioningEnabled: true
  }
}

resource artifactsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
  parent: blobService
  name: artifactsContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-blob-${resourceToken}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pe-blob-${resourceToken}'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: [
            'blob'
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
        name: 'privatelink-blob-core-windows-net'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

resource blobDataContributorAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in blobDataContributorPrincipalIds: {
    name: guid(storageAccount.id, principalId, blobDataContributorRoleDefinitionId)
    scope: storageAccount
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributorRoleDefinitionId)
    }
  }
]

@description('Resource ID of the storage account.')
output storageAccountId string = storageAccount.id

@description('Name of the storage account.')
output storageAccountName string = storageAccount.name

@description('Primary blob endpoint of the storage account.')
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
