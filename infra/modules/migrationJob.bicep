// Manually triggered schema migration job. It runs inside the VNet-integrated
// Container Apps environment, uses an immutable API image, and authenticates to
// PostgreSQL and ACR with a dedicated user-assigned managed identity.
metadata description = 'VNet-connected Alembic schema migration job.'

@description('Azure region for the Container Apps Job.')
param location string

@description('Tags applied to the migration job.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('Resource ID of the Container Apps managed environment.')
param environmentId string

@description('Login server of the private Azure Container Registry.')
param registryLoginServer string

@description('Resource ID of the dedicated migration managed identity.')
param migrationIdentityId string

@description('Client ID of the dedicated migration managed identity.')
param migrationIdentityClientId string

@description('Immutable API image containing the application and Alembic migrations.')
param migrationImage string

@description('Full immutable source/build identifier exposed to migration telemetry.')
param imageTag string

@description('FQDN of the existing PostgreSQL Flexible Server.')
param postgresServerFqdn string

@description('Application database name.')
param postgresDatabaseName string

@description('PostgreSQL Entra role mapped to the dedicated migration identity. This role must own the application schema.')
param postgresMigrationUsername string

@description('Application Insights connection string for migration telemetry.')
param applicationInsightsConnectionString string

resource migrationJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'job-migrate-${resourceToken}'
  location: location
  tags: union(tags, {
    workload: 'database-migration'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${migrationIdentityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 900
      replicaRetryLimit: 0
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: registryLoginServer
          identity: migrationIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'alembic'
          image: migrationImage
          command: [
            'python'
          ]
          args: [
            '-m'
            'alembic'
            'upgrade'
            'head'
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'APP_ENV', value: 'migration' }
            { name: 'APP_VERSION', value: imageTag }
            { name: 'GIT_SHA', value: imageTag }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsightsConnectionString }
            { name: 'AZURE_CLIENT_ID', value: migrationIdentityClientId }
            { name: 'AZURE_TOKEN_CREDENTIALS', value: 'prod' }
            { name: 'DATABASE_USE_ENTRA', value: 'true' }
            { name: 'DATABASE_ECHO', value: 'false' }
            { name: 'DATABASE_URL', value: 'postgresql://${postgresMigrationUsername}@${postgresServerFqdn}:5432/${postgresDatabaseName}?sslmode=require' }
          ]
        }
      ]
    }
  }
}

output name string = migrationJob.name
output id string = migrationJob.id
