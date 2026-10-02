// Resource-group-scoped orchestrator for the approved balanced-production
// AgentSystem architecture: East US 2 VNet-integrated Container Apps
// environment hosting four workloads (public frontend, internal API,
// internal worker, internal scale-to-zero operator console), backed by
// private-endpoint-connected Key Vault/Storage/Redis, a cross-region private
// endpoint into the existing Central US PostgreSQL Flexible Server
// (referenced, never created or deleted), Durable Task Scheduler, a Dynamic
// Sessions pool, and Log Analytics/App Insights/alerts/budget observability.
// Every module is individually parameterized and independently validated;
// this file only wires their outputs together and assigns least-privilege
// RBAC between them.
metadata description = 'AgentSystem balanced-production resources (resource-group scope).'

@description('Deployment environment name (e.g. prod, staging). Used for resource naming, tagging, and the APP_ENV variable.')
param environmentName string

@description('Azure region for all newly created resources (East US 2 per the approved plan). The referenced PostgreSQL server remains in its existing Central US region regardless of this value.')
param location string

@description('Email address that receives budget and Azure Monitor alert notifications.')
param alertReceiverEmail string

@description('Monthly cost budget amount in the billing currency, with 50/80/100% notification thresholds.')
param budgetAmount int = 500

@description('Daily ingestion cap (GB) for the Log Analytics workspace.')
param logAnalyticsDailyQuotaGb int = 1

@description('Log Analytics retention in days.')
param logAnalyticsRetentionInDays int = 30

@description('VNet address space for the new East US 2 network.')
param vnetAddressPrefix string = '10.20.0.0/16'

@description('Address prefix for the Container Apps environment infrastructure subnet (requires /23 or larger).')
param containerAppsSubnetPrefix string = '10.20.0.0/23'

@description('Address prefix for the private endpoints subnet.')
param privateEndpointsSubnetPrefix string = '10.20.2.0/24'

@description('Maximum number of ready (warm) Dynamic Sessions instances.')
param dynamicSessionsReadySessionInstances int = 0

@description('Maximum number of concurrent Dynamic Sessions instances.')
param dynamicSessionsMaxConcurrentSessions int = 2

@description('Full resource ID of the existing PostgreSQL Flexible Server (Central US), e.g. /subscriptions/xxx/resourceGroups/rg-agentsystem-prod/providers/Microsoft.DBforPostgreSQL/flexibleServers/psql-genesis-dczy4r. This server is never created or deleted by this template.')
param postgresServerResourceId string

@description('Fully-qualified domain name of the existing PostgreSQL Flexible Server.')
param postgresServerFqdn string

@description('Azure region of the existing PostgreSQL Flexible Server. Used only for the explicit opt-in hardening deployment.')
param postgresServerLocation string

@description('Application database name on the PostgreSQL server.')
param postgresDatabaseName string = 'agentsystem'

@description('PostgreSQL Entra ID role name used by the API workload identity (must match a role provisioned on the server for this identity).')
param postgresApiUsername string

@description('PostgreSQL Entra ID role name used by the worker workload identity (must match a role provisioned on the server for this identity).')
param postgresWorkerUsername string

@description('Name of the existing PostgreSQL Flexible Server (final segment of postgresServerResourceId). Required only when applyPostgresHardening is true.')
param postgresServerName string = ''

@description('Resource group name of the existing PostgreSQL Flexible Server. Required only when applyPostgresHardening is true.')
param postgresServerResourceGroupName string = ''

@description('Opt-in switch to apply the approved in-place, non-destructive hardening (compute/storage/backup-retention resize) to the existing PostgreSQL server via createMode=Update. Defaults to false so that a routine build/validate/deploy of this template never mutates the existing server; enable only for a deliberate, dedicated hardening deployment per the migration sequencing in .azure/deployment-plan.md.')
param applyPostgresHardening bool = false

@description('Target PostgreSQL compute SKU name applied only when applyPostgresHardening is true.')
param postgresHardenedSkuName string = 'Standard_D2ds_v5'

@description('Target PostgreSQL compute tier applied only when applyPostgresHardening is true.')
param postgresHardenedSkuTier string = 'GeneralPurpose'

@description('Target PostgreSQL storage size in GiB applied only when applyPostgresHardening is true.')
param postgresHardenedStorageSizeGb int = 128

@description('Target PostgreSQL backup retention in days applied only when applyPostgresHardening is true.')
param postgresHardenedBackupRetentionDays int = 14

@description('Optional Microsoft Entra administrators to register on the PostgreSQL server when applyPostgresHardening is true. Each item: { objectId, principalName, principalType }.')
param postgresAadAdministrators array = []

@description('Whether Redis coordination/caching is enabled for the API and worker.')
param redisEnabled bool = true

@description('Name of the Durable Task task hub used by the worker.')
param durableTaskHubName string = 'agentsystem'

@description('Name of the blob container used for durable artifacts.')
param artifactsContainerName string = 'artifacts'

@allowed([
  'Enabled'
  'Disabled'
])
@description('Registry public network state. Use Enabled only for the bootstrap image push and Disabled for the final deployment.')
param registryPublicNetworkAccess string = 'Disabled'

@description('Container image repository:tag for the frontend, e.g. myacr.azurecr.io/agentsystem-frontend:sha-abc1234. Defaults to the registry created by this template combined with imageTag.')
param frontendImage string = ''

@description('Container image repository:tag for the API. Defaults to the registry created by this template combined with imageTag.')
param apiImage string = ''

@description('Container image repository:tag for the worker. Defaults to the registry created by this template combined with imageTag.')
param workerImage string = ''

@description('Container image repository:tag for the operator console. Defaults to the registry created by this template combined with imageTag.')
param operatorImage string = ''

@description('Immutable build/version identifier used for image tags and runtime source traceability. CI supplies the full commit SHA.')
param imageTag string

@description('Short DNS-safe Container App revision suffix, independent from the full immutable image tag.')
@minLength(1)
@maxLength(16)
param revisionSuffix string

@description('Deploy the four workloads and workload-dependent alerts. Set false for the foundation/image bootstrap pass.')
param deployContainerApps bool = true

@description('Deploy the manually triggered Alembic migration job. Set true after the immutable API image exists in the registry.')
param deployMigrationJob bool = false

@description('Microsoft Entra tenant ID used for Easy Auth / Entra bearer validation and Key Vault access.')
param entraTenantId string = subscription().tenantId

@description('Microsoft Entra application (audience) ID that the API validates bearer tokens against. Leave empty to disable Entra bearer validation.')
param entraAudience string = ''

@description('Microsoft Entra application client ID used by Container Apps built-in authentication.')
param entraClientId string

@description('Authentication mode for the API: disabled | api_key | easy_auth | entra_jwt.')
param authMode string = 'easy_auth'

@description('Whether Container Apps built-in authentication protects the frontend/operator and the API trusts their forwarded identity headers.')
param easyAuthEnabled bool = true

@description('Name of the Key Vault secret holding the Entra application client secret for Container Apps built-in authentication.')
param entraClientSecretName string = 'microsoft-provider-authentication-secret'

@secure()
@description('Microsoft Entra application client secret supplied securely by the deployment environment.')
param entraClientSecret string

@description('Resource group containing the existing Azure AI Services/OpenAI account.')
param azureOpenAiResourceGroupName string

@description('Name of the existing Azure AI Services/OpenAI account.')
param azureOpenAiAccountName string

@description('Endpoint of the existing Azure AI Services/OpenAI account.')
param azureOpenAiEndpoint string

@description('Azure OpenAI chat completion deployment name.')
param azureOpenAiChatDeployment string

@description('Azure OpenAI embedding deployment name. Leave empty to disable vector embeddings.')
param azureOpenAiEmbeddingDeployment string = ''

@description('Azure OpenAI REST API version used by the Agent Framework OpenAIChatCompletionClient on the API and worker. Must match a version supported by the target deployment.')
param azureOpenAiApiVersion string = '2024-12-01-preview'

@description('Name of the Key Vault secret holding the AgentSystem shared API key (used only when authMode=api_key). The secret value itself must be populated out-of-band by an operator/CI pipeline, never by this template.')
param apiKeySecretName string = 'agentsystem-api-key'

@description('Additional resource tags merged with the standard AgentSystem tag set.')
param additionalTags object = {}

var resourceToken = toLower(uniqueString(resourceGroup().id, environmentName, location))

var tags = union(
  {
    'azd-env-name': environmentName
    environment: environmentName
    workload: 'agentsystem'
    'managed-by': 'bicep'
  },
  additionalTags
)

// ---------------------------------------------------------------------------
// Foundational modules with no dependencies on one another.
// ---------------------------------------------------------------------------

module network 'modules/network.bicep' = {
  name: 'network-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    vnetAddressPrefix: vnetAddressPrefix
    containerAppsSubnetPrefix: containerAppsSubnetPrefix
    privateEndpointsSubnetPrefix: privateEndpointsSubnetPrefix
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    logAnalyticsDailyQuotaGb: logAnalyticsDailyQuotaGb
    logAnalyticsRetentionInDays: logAnalyticsRetentionInDays
    alertReceiverEmail: alertReceiverEmail
    budgetAmount: budgetAmount
    environmentName: environmentName
  }
}

module identity 'modules/identity.bicep' = {
  name: 'identity-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
  }
}

// ---------------------------------------------------------------------------
// Data/registry/secret services: each depends on network (private endpoint
// subnet + private DNS zone) and identity (least-privilege RBAC principals).
// ---------------------------------------------------------------------------

module registry 'modules/registry.bicep' = {
  name: 'registry-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    publicNetworkAccess: registryPublicNetworkAccess
    privateEndpointSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneId: network.outputs.privateDnsZoneIds.acr
    pullerPrincipalIds: [
      identity.outputs.frontendIdentity.principalId
      identity.outputs.apiIdentity.principalId
      identity.outputs.workerIdentity.principalId
      identity.outputs.operatorIdentity.principalId
      identity.outputs.migrationIdentity.principalId
    ]
  }
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    privateEndpointSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneId: network.outputs.privateDnsZoneIds.keyVault
    tenantId: entraTenantId
    entraClientSecretName: entraClientSecretName
    entraClientSecret: entraClientSecret
    // Frontend/operator read the Entra provider secret. API reads the legacy
    // shared key only when api_key mode is deliberately selected.
    secretsUserPrincipalIds: [
      identity.outputs.frontendIdentity.principalId
      identity.outputs.apiIdentity.principalId
      identity.outputs.operatorIdentity.principalId
    ]
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    privateEndpointSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneId: network.outputs.privateDnsZoneIds.blob
    artifactsContainerName: artifactsContainerName
    // Only the API and worker read/write blob artifacts.
    blobDataContributorPrincipalIds: [
      identity.outputs.apiIdentity.principalId
      identity.outputs.workerIdentity.principalId
    ]
  }
}

module redis 'modules/redis.bicep' = if (redisEnabled) {
  name: 'redis-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    privateEndpointSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneId: network.outputs.privateDnsZoneIds.redis
    // Only the API and worker connect to Redis.
    dataAccessPrincipals: [
      {
        principalId: identity.outputs.apiIdentity.principalId
        principalName: 'id-api-${resourceToken}'
      }
      {
        principalId: identity.outputs.workerIdentity.principalId
        principalName: 'id-worker-${resourceToken}'
      }
    ]
  }
}

module durableTask 'modules/durableTask.bicep' = {
  name: 'durabletask-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    taskHubName: durableTaskHubName
    // Only the API (enqueues orchestrations) and worker (executes them) need
    // Durable Task data-plane access.
    dataContributorPrincipalIds: [
      identity.outputs.apiIdentity.principalId
    ]
    workerPrincipalIds: [
      identity.outputs.workerIdentity.principalId
    ]
  }
}

// ---------------------------------------------------------------------------
// Existing PostgreSQL Flexible Server: referenced only, plus a cross-region
// private endpoint from the new East US 2 VNet. Never created or deleted.
// ---------------------------------------------------------------------------

module postgres 'modules/postgres.bicep' = {
  name: 'postgres-${resourceToken}'
  params: {
    postgresServerResourceId: postgresServerResourceId
    postgresServerFqdn: postgresServerFqdn
    location: postgresServerLocation
    tags: tags
    resourceToken: resourceToken
    privateEndpointSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneId: network.outputs.privateDnsZoneIds.postgres
    postgresServerName: postgresServerName
    postgresServerResourceGroupName: postgresServerResourceGroupName
    applyPostgresHardening: applyPostgresHardening
    postgresHardenedSkuName: postgresHardenedSkuName
    postgresHardenedSkuTier: postgresHardenedSkuTier
    postgresHardenedStorageSizeGb: postgresHardenedStorageSizeGb
    postgresHardenedBackupRetentionDays: postgresHardenedBackupRetentionDays
    postgresAadAdministrators: postgresAadAdministrators
  }
}

// ---------------------------------------------------------------------------
// Container Apps managed environment: needs the network's delegated subnet
// and the Log Analytics workspace's customer ID + a listKeys()-retrieved
// shared key (appLogsConfiguration has no managed-identity alternative).
// ---------------------------------------------------------------------------

// The existing-resource reference below is used only to retrieve the
// workspace's shared key via listKeys() (appLogsConfiguration has no
// managed-identity alternative). Its name must be a deterministic,
// compile-time-known expression rather than a module output, so it
// duplicates monitoring.bicep's exact naming convention ('log-<token>')
// instead of referencing monitoring.outputs.logAnalyticsWorkspaceName.
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' existing = {
  name: 'log-${resourceToken}'
  dependsOn: [
    monitoring
  ]
}

module containerAppsEnvironment 'modules/containerAppsEnvironment.bicep' = {
  name: 'cae-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    infrastructureSubnetId: network.outputs.containerAppsSubnetId
    logAnalyticsCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
    dynamicSessionsReadySessionInstances: dynamicSessionsReadySessionInstances
    dynamicSessionsMaxConcurrentSessions: dynamicSessionsMaxConcurrentSessions
    sessionExecutorPrincipalIds: [
      identity.outputs.apiIdentity.principalId
    ]
  }
}

// ---------------------------------------------------------------------------
// The four AgentSystem Container Apps, wired to every service above.
// ---------------------------------------------------------------------------

module azureOpenAiAccess 'modules/azureOpenAiAccess.bicep' = {
  name: 'azure-openai-access-${resourceToken}'
  scope: resourceGroup(azureOpenAiResourceGroupName)
  params: {
    accountName: azureOpenAiAccountName
    inferencePrincipalIds: [
      identity.outputs.apiIdentity.principalId
      identity.outputs.workerIdentity.principalId
    ]
  }
}

module migrationJob 'modules/migrationJob.bicep' = if (deployMigrationJob) {
  name: 'migration-job-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    environmentId: containerAppsEnvironment.outputs.environmentId
    registryLoginServer: registry.outputs.loginServer
    migrationIdentityId: identity.outputs.migrationIdentity.id
    migrationIdentityClientId: identity.outputs.migrationIdentity.clientId
    migrationImage: !empty(apiImage) ? apiImage : '${registry.outputs.loginServer}/agentsystem-api:${imageTag}'
    imageTag: imageTag
    postgresServerFqdn: postgres.outputs.postgresServerFqdn
    postgresDatabaseName: postgresDatabaseName
    postgresMigrationUsername: identity.outputs.migrationIdentity.name
    applicationInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
  }
}

module containerApps 'modules/containerApps.bicep' = if (deployContainerApps) {
  name: 'containerapps-${resourceToken}'
  params: {
    environmentName: environmentName
    location: location
    tags: tags
    resourceToken: resourceToken
    environmentId: containerAppsEnvironment.outputs.environmentId
    registryLoginServer: registry.outputs.loginServer
    keyVaultUri: keyVault.outputs.keyVaultUri
    frontendIdentityId: identity.outputs.frontendIdentity.id
    frontendIdentityClientId: identity.outputs.frontendIdentity.clientId
    frontendIdentityPrincipalId: identity.outputs.frontendIdentity.principalId
    apiIdentityId: identity.outputs.apiIdentity.id
    apiIdentityClientId: identity.outputs.apiIdentity.clientId
    apiIdentityPrincipalId: identity.outputs.apiIdentity.principalId
    workerIdentityId: identity.outputs.workerIdentity.id
    workerIdentityClientId: identity.outputs.workerIdentity.clientId
    workerIdentityPrincipalId: identity.outputs.workerIdentity.principalId
    operatorIdentityId: identity.outputs.operatorIdentity.id
    operatorIdentityClientId: identity.outputs.operatorIdentity.clientId
    operatorIdentityPrincipalId: identity.outputs.operatorIdentity.principalId
    frontendImage: !empty(frontendImage) ? frontendImage : '${registry.outputs.loginServer}/agentsystem-frontend:${imageTag}'
    apiImage: !empty(apiImage) ? apiImage : '${registry.outputs.loginServer}/agentsystem-api:${imageTag}'
    workerImage: !empty(workerImage) ? workerImage : '${registry.outputs.loginServer}/agentsystem-worker:${imageTag}'
    operatorImage: !empty(operatorImage) ? operatorImage : '${registry.outputs.loginServer}/agentsystem-operator:${imageTag}'
    imageTag: imageTag
    revisionSuffix: revisionSuffix
    postgresServerFqdn: postgres.outputs.postgresServerFqdn
    postgresDatabaseName: postgresDatabaseName
    postgresApiUsername: postgresApiUsername
    postgresWorkerUsername: postgresWorkerUsername
    redisEnabled: redisEnabled
    // The null-forgiving operator (!) is safe here: redis is only accessed
    // inside the redisEnabled-guarded branch, so it is always deployed
    // whenever this branch executes.
    redisHostName: redisEnabled ? redis!.outputs.hostName : ''
    redisPort: redisEnabled ? redis!.outputs.port : 10000
    durableTaskEndpoint: durableTask.outputs.endpoint
    durableTaskHubName: durableTask.outputs.taskHubName
    blobEndpoint: storage.outputs.blobEndpoint
    artifactsContainerName: artifactsContainerName
    dynamicSessionsEndpoint: containerAppsEnvironment.outputs.sessionPoolManagementEndpoint
    entraTenantId: entraTenantId
    entraAudience: entraAudience
    entraClientId: entraClientId
    authMode: authMode
    easyAuthEnabled: easyAuthEnabled
    entraClientSecretName: entraClientSecretName
    azureOpenAiEndpoint: azureOpenAiEndpoint
    azureOpenAiChatDeployment: azureOpenAiChatDeployment
    azureOpenAiEmbeddingDeployment: azureOpenAiEmbeddingDeployment
    azureOpenAiApiVersion: azureOpenAiApiVersion
    applicationInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    apiKeySecretName: apiKeySecretName
  }
}

// ---------------------------------------------------------------------------
// Alerts: depend on the action group/App Insights and the Container Apps'
// resource IDs, so they are wired last.
// ---------------------------------------------------------------------------

module alerts 'modules/alerts.bicep' = if (deployContainerApps) {
  name: 'alerts-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    actionGroupId: monitoring.outputs.actionGroupId
    appInsightsId: monitoring.outputs.appInsightsId
    frontendContainerAppId: containerApps!.outputs.frontend.id
    apiContainerAppId: containerApps!.outputs.api.id
    workerContainerAppId: containerApps!.outputs.worker.id
    postgresServerResourceId: postgresServerResourceId
    redisResourceId: redisEnabled ? redis!.outputs.redisId : ''
    redisEnabled: redisEnabled
  }
}

// ---------------------------------------------------------------------------
// Outputs consumed by azd and by operators.
// ---------------------------------------------------------------------------

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = registry.outputs.registryName
output AZURE_KEY_VAULT_NAME string = keyVault.outputs.keyVaultName
output AZURE_KEY_VAULT_ENDPOINT string = keyVault.outputs.keyVaultUri
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = containerAppsEnvironment.outputs.environmentId
output AZURE_CONTAINER_APPS_ENVIRONMENT_DEFAULT_DOMAIN string = containerAppsEnvironment.outputs.defaultDomain
output AZURE_LOG_ANALYTICS_WORKSPACE_NAME string = monitoring.outputs.logAnalyticsWorkspaceName
output AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString
output SERVICE_FRONTEND_NAME string = deployContainerApps ? containerApps!.outputs.frontend.name : ''
output SERVICE_FRONTEND_URI string = deployContainerApps ? 'https://${containerApps!.outputs.frontend.fqdn}' : ''
output SERVICE_API_NAME string = deployContainerApps ? containerApps!.outputs.api.name : ''
output SERVICE_API_URI string = deployContainerApps ? 'https://${containerApps!.outputs.api.fqdn}' : ''
output SERVICE_WORKER_NAME string = deployContainerApps ? containerApps!.outputs.worker.name : ''
output SERVICE_OPERATOR_NAME string = deployContainerApps ? containerApps!.outputs.operatorConsole.name : ''
output SERVICE_OPERATOR_URI string = deployContainerApps ? 'https://${containerApps!.outputs.operatorConsole.fqdn}' : ''
output AZURE_STORAGE_ACCOUNT_NAME string = storage.outputs.storageAccountName
output AZURE_STORAGE_BLOB_ENDPOINT string = storage.outputs.blobEndpoint
output AZURE_DURABLE_TASK_SCHEDULER_ENDPOINT string = durableTask.outputs.endpoint
output AZURE_DYNAMIC_SESSIONS_POOL_ENDPOINT string = containerAppsEnvironment.outputs.sessionPoolManagementEndpoint
output AZURE_REDIS_HOST_NAME string = redisEnabled ? redis!.outputs.hostName : ''
output AZURE_POSTGRES_SERVER_FQDN string = postgres.outputs.postgresServerFqdn
output DATABASE_MIGRATION_JOB_NAME string = deployMigrationJob ? migrationJob!.outputs.name : ''
output DATABASE_MIGRATION_IDENTITY_NAME string = identity.outputs.migrationIdentity.name
output DATABASE_MIGRATION_IDENTITY_PRINCIPAL_ID string = identity.outputs.migrationIdentity.principalId
