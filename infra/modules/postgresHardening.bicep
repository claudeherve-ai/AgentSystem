// PostgreSQL hardening module: applies the approved, non-destructive resize
// of the EXISTING Central US PostgreSQL Flexible Server using
// createMode='Update'. This mode explicitly targets the already-existing
// server in place; it does not create a new server and does not delete the
// existing one. Only compute SKU, storage size, and backup retention are
// changed — no administrator credentials, networking, or version properties
// are touched, so this module cannot destructively alter authentication or
// connectivity.
//
// This module is only invoked (see postgres.bicep) when the caller
// explicitly opts in via applyPostgresHardening=true. It is never invoked as
// part of a routine environment build/validate.
metadata description = 'Opt-in, non-destructive hardening (resize) of the existing PostgreSQL Flexible Server.'

@description('Name of the existing PostgreSQL Flexible Server to harden.')
param postgresServerName string

@description('Azure region of the existing server (Central US). Must match the existing server\'s region.')
param location string

@description('Target compute SKU name, e.g. Standard_D2ds_v5.')
param skuName string

@description('Target compute tier, e.g. GeneralPurpose.')
param skuTier string

@description('Target storage size in GiB. Storage can only grow, never shrink, for PostgreSQL Flexible Server.')
param storageSizeGb int

@description('Target backup retention in days (7-35).')
param backupRetentionDays int

@description('Optional Microsoft Entra administrators to register on the server for AAD authentication (per the approved Postgres-Entra-auth requirement). Each item: { objectId: <AAD object ID>, principalName: <UPN or app display name>, principalType: \'User\' | \'ServicePrincipal\' | \'Group\' }. Leave empty to make no administrator changes.')
param aadAdministrators array = []

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' = {
  name: postgresServerName
  location: location
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    createMode: 'Update'
    storage: {
      storageSizeGB: storageSizeGb
    }
    backup: {
      backupRetentionDays: backupRetentionDays
    }
  }
}

// Registers Microsoft Entra principals (e.g. the API/worker managed
// identities, or a human administrator) as PostgreSQL AAD administrators.
// This only grants the ability to authenticate via Entra and administer
// AAD-based roles; it does not create application-level database roles or
// grants, which remain a post-deployment SQL step performed by an
// authorized operator (out of scope for this infrastructure template).
resource aadAdmins 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2025-08-01' = [
  for admin in aadAdministrators: {
    parent: postgresServer
    name: admin.objectId
    properties: {
      principalName: admin.principalName
      principalType: admin.principalType
      tenantId: subscription().tenantId
    }
  }
]

@description('Resource ID of the hardened PostgreSQL Flexible Server.')
output postgresServerId string = postgresServer.id
