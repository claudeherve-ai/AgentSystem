// Postgres module: references the EXISTING Central US PostgreSQL Flexible
// Server (never created or deleted by this template) and adds a cross-region
// private endpoint from the new East US 2 VNet so Container Apps can reach it
// privately. Server-side hardening (SKU/storage/backup retention resize) is
// applied to the existing resource via its own properties, without recreating
// or deleting it.
metadata description = 'Reference to and private connectivity for the existing PostgreSQL Flexible Server.'

@description('Full resource ID of the existing PostgreSQL Flexible Server (Central US), e.g. /subscriptions/xxx/resourceGroups/rg-agentsystem-prod/providers/Microsoft.DBforPostgreSQL/flexibleServers/psql-genesis-dczy4r.')
param postgresServerResourceId string

@description('Fully-qualified domain name of the existing PostgreSQL Flexible Server, e.g. psql-genesis-dczy4r.postgres.database.azure.com.')
param postgresServerFqdn string

@description('Azure region of the East US 2 VNet where the private endpoint is created (private endpoints can target resources in other regions).')
param location string

@description('Tags applied to resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('Resource ID of the subnet used for the private endpoint.')
param privateEndpointSubnetId string

@description('Resource ID of the privatelink.postgres.database.azure.com private DNS zone.')
param privateDnsZoneId string

@description('Name of the existing PostgreSQL Flexible Server (final segment of postgresServerResourceId). Required only when applyHardening is true, since createMode=Update targets the server by name/scope.')
param postgresServerName string = ''

@description('Resource group name of the existing PostgreSQL Flexible Server. Required only when applyHardening is true.')
param postgresServerResourceGroupName string = ''

@description('Opt-in switch to apply the approved in-place hardening (compute/storage/backup-retention resize) to the existing server via createMode=Update. Defaults to false: this template never mutates the existing server unless explicitly enabled by an operator in a follow-up, deliberate deployment. createMode=Update never recreates or deletes the server.')
param applyPostgresHardening bool = false

@description('Target compute SKU name applied only when applyHardening is true, e.g. Standard_D2ds_v5 (from Standard_B1ms).')
param postgresHardenedSkuName string = 'Standard_D2ds_v5'

@description('Target compute tier applied only when applyHardening is true.')
param postgresHardenedSkuTier string = 'GeneralPurpose'

@description('Target storage size in GiB applied only when applyHardening is true (from 32 to 128 per the approved plan). Storage can only grow, never shrink.')
param postgresHardenedStorageSizeGb int = 128

@description('Target backup retention in days applied only when applyHardening is true (from 7 to 14 per the approved plan).')
param postgresHardenedBackupRetentionDays int = 14

@description('Optional Microsoft Entra administrators to register on the server when applyHardening is true. Each item: { objectId, principalName, principalType }.')
param postgresAadAdministrators array = []

// Approved, opt-in, non-destructive hardening of the EXISTING PostgreSQL
// Flexible Server: createMode='Update' explicitly targets the already
// existing server in place (resize compute/storage, extend backup
// retention). It never creates a new server and never deletes the existing
// one. Disabled by default (applyPostgresHardening=false) so that building
// or validating this template can never trigger a mutation; an operator
// must deliberately opt in for a dedicated hardening deployment, per the
// migration sequencing described in .azure/deployment-plan.md section 5.2.
module postgresHardening 'postgresHardening.bicep' = if (applyPostgresHardening) {
  name: 'postgres-hardening-${resourceToken}'
  scope: resourceGroup(postgresServerResourceGroupName)
  params: {
    postgresServerName: postgresServerName
    location: location
    skuName: postgresHardenedSkuName
    skuTier: postgresHardenedSkuTier
    storageSizeGb: postgresHardenedStorageSizeGb
    backupRetentionDays: postgresHardenedBackupRetentionDays
    aadAdministrators: postgresAadAdministrators
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pe-psql-${resourceToken}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pe-psql-${resourceToken}'
        properties: {
          privateLinkServiceId: postgresServerResourceId
          groupIds: [
            'postgresqlServer'
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
        name: 'privatelink-postgres-database-azure-com'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

@description('Resource ID of the referenced PostgreSQL Flexible Server (pass-through of the input parameter).')
output postgresServerId string = postgresServerResourceId

@description('FQDN of the referenced PostgreSQL Flexible Server (pass-through of the input parameter).')
output postgresServerFqdn string = postgresServerFqdn

@description('Resource ID of the private endpoint created for cross-region private connectivity.')
output privateEndpointId string = privateEndpoint.id
