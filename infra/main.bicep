// Subscription-scoped entry point for the AgentSystem balanced-production
// architecture: creates (or reuses) the resource group and delegates all
// resource provisioning to resources.bicep. See .azure/deployment-plan.md
// for the approved architecture this template implements.
targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Deployment environment name (e.g. prod, staging). Used for resource-group naming, resource naming/tagging, and the APP_ENV variable. Matches AZD_ENV_NAME.')
param environmentName string

@description('Azure region for all newly created resources. East US 2 per the approved plan; the referenced PostgreSQL server remains in its existing Central US region regardless of this value.')
param location string = 'eastus2'

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

@description('Full resource ID of the existing PostgreSQL Flexible Server (Central US). This server is never created or deleted by this template.')
param postgresServerResourceId string

@description('Fully-qualified domain name of the existing PostgreSQL Flexible Server.')
param postgresServerFqdn string

@description('Azure region of the existing PostgreSQL Flexible Server. This can differ from the region used for new AgentSystem resources.')
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

@description('Opt-in switch to apply the approved in-place, non-destructive hardening (compute/storage/backup-retention resize) to the existing PostgreSQL server. Defaults to false so that a routine build/validate/deploy of this template never mutates the existing server.')
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

@description('Container image repository:tag for the frontend. Defaults to the registry created by this template combined with imageTag.')
param frontendImage string = ''

@description('Container image repository:tag for the API. Defaults to the registry created by this template combined with imageTag.')
param apiImage string = ''

@description('Container image repository:tag for the worker. Defaults to the registry created by this template combined with imageTag.')
param workerImage string = ''

@description('Container image repository:tag for the operator console. Defaults to the registry created by this template combined with imageTag.')
param operatorImage string = ''

@description('Immutable image tag and runtime source identifier. Supply the full 40-character commit SHA in CI.')
param imageTag string

@description('Short DNS-safe Container App revision suffix. Keep this substantially shorter than the 64-character total revision-name limit.')
@minLength(1)
@maxLength(16)
param revisionSuffix string

@description('Deploy the four workloads and workload-dependent alerts. Set false for the foundation/image bootstrap pass.')
param deployContainerApps bool = true

@description('Deploy the manually triggered, VNet-connected Alembic migration job. Set true only after the immutable API image has been pushed.')
param deployMigrationJob bool = false

@description('Microsoft Entra tenant ID used for Easy Auth / Entra bearer validation and Key Vault access.')
param entraTenantId string = subscription().tenantId

@description('Microsoft Entra application (audience) ID that the API validates bearer tokens against. Leave empty to disable Entra bearer validation.')
param entraAudience string = ''

@description('Microsoft Entra application client ID used by Container Apps built-in authentication.')
param entraClientId string

@description('Authentication mode for the API: disabled | api_key | easy_auth | entra_jwt. Production uses direct JWT validation behind the authenticated frontend/operator proxies.')
param authMode string = 'entra_jwt'

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

@description('Name of the Key Vault secret holding the AgentSystem shared API key (used only when authMode=api_key). The secret value itself must be populated out-of-band, never by this template.')
param apiKeySecretName string = 'agentsystem-api-key'

@description('Additional resource tags merged with the standard AgentSystem tag set.')
param additionalTags object = {}

resource rg 'Microsoft.Resources/resourceGroups@2024-11-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: {
    'azd-env-name': environmentName
    environment: environmentName
    workload: 'agentsystem'
    'managed-by': 'bicep'
  }
}

module resources 'resources.bicep' = {
  name: take('resources-${environmentName}', 64)
  scope: rg
  params: {
    environmentName: environmentName
    location: location
    alertReceiverEmail: alertReceiverEmail
    budgetAmount: budgetAmount
    logAnalyticsDailyQuotaGb: logAnalyticsDailyQuotaGb
    logAnalyticsRetentionInDays: logAnalyticsRetentionInDays
    vnetAddressPrefix: vnetAddressPrefix
    containerAppsSubnetPrefix: containerAppsSubnetPrefix
    privateEndpointsSubnetPrefix: privateEndpointsSubnetPrefix
    dynamicSessionsReadySessionInstances: dynamicSessionsReadySessionInstances
    dynamicSessionsMaxConcurrentSessions: dynamicSessionsMaxConcurrentSessions
    postgresServerResourceId: postgresServerResourceId
    postgresServerFqdn: postgresServerFqdn
    postgresServerLocation: postgresServerLocation
    postgresDatabaseName: postgresDatabaseName
    postgresApiUsername: postgresApiUsername
    postgresWorkerUsername: postgresWorkerUsername
    postgresServerName: postgresServerName
    postgresServerResourceGroupName: postgresServerResourceGroupName
    applyPostgresHardening: applyPostgresHardening
    postgresHardenedSkuName: postgresHardenedSkuName
    postgresHardenedSkuTier: postgresHardenedSkuTier
    postgresHardenedStorageSizeGb: postgresHardenedStorageSizeGb
    postgresHardenedBackupRetentionDays: postgresHardenedBackupRetentionDays
    postgresAadAdministrators: postgresAadAdministrators
    redisEnabled: redisEnabled
    durableTaskHubName: durableTaskHubName
    artifactsContainerName: artifactsContainerName
    registryPublicNetworkAccess: registryPublicNetworkAccess
    frontendImage: frontendImage
    apiImage: apiImage
    workerImage: workerImage
    operatorImage: operatorImage
    imageTag: imageTag
    revisionSuffix: revisionSuffix
    deployContainerApps: deployContainerApps
    deployMigrationJob: deployMigrationJob
    entraTenantId: entraTenantId
    entraAudience: entraAudience
    entraClientId: entraClientId
    authMode: authMode
    easyAuthEnabled: easyAuthEnabled
    entraClientSecretName: entraClientSecretName
    entraClientSecret: entraClientSecret
    azureOpenAiResourceGroupName: azureOpenAiResourceGroupName
    azureOpenAiAccountName: azureOpenAiAccountName
    azureOpenAiEndpoint: azureOpenAiEndpoint
    azureOpenAiChatDeployment: azureOpenAiChatDeployment
    azureOpenAiEmbeddingDeployment: azureOpenAiEmbeddingDeployment
    azureOpenAiApiVersion: azureOpenAiApiVersion
    apiKeySecretName: apiKeySecretName
    additionalTags: additionalTags
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT
output AZURE_CONTAINER_REGISTRY_NAME string = resources.outputs.AZURE_CONTAINER_REGISTRY_NAME
output AZURE_KEY_VAULT_NAME string = resources.outputs.AZURE_KEY_VAULT_NAME
output AZURE_KEY_VAULT_ENDPOINT string = resources.outputs.AZURE_KEY_VAULT_ENDPOINT
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = resources.outputs.AZURE_CONTAINER_APPS_ENVIRONMENT_ID
output AZURE_CONTAINER_APPS_ENVIRONMENT_DEFAULT_DOMAIN string = resources.outputs.AZURE_CONTAINER_APPS_ENVIRONMENT_DEFAULT_DOMAIN
output AZURE_LOG_ANALYTICS_WORKSPACE_NAME string = resources.outputs.AZURE_LOG_ANALYTICS_WORKSPACE_NAME
output AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING string = resources.outputs.AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING
output SERVICE_FRONTEND_NAME string = resources.outputs.SERVICE_FRONTEND_NAME
output SERVICE_FRONTEND_URI string = resources.outputs.SERVICE_FRONTEND_URI
output SERVICE_API_NAME string = resources.outputs.SERVICE_API_NAME
output SERVICE_API_URI string = resources.outputs.SERVICE_API_URI
output SERVICE_WORKER_NAME string = resources.outputs.SERVICE_WORKER_NAME
output SERVICE_OPERATOR_NAME string = resources.outputs.SERVICE_OPERATOR_NAME
output SERVICE_OPERATOR_URI string = resources.outputs.SERVICE_OPERATOR_URI
output AZURE_STORAGE_ACCOUNT_NAME string = resources.outputs.AZURE_STORAGE_ACCOUNT_NAME
output AZURE_STORAGE_BLOB_ENDPOINT string = resources.outputs.AZURE_STORAGE_BLOB_ENDPOINT
output AZURE_DURABLE_TASK_SCHEDULER_ENDPOINT string = resources.outputs.AZURE_DURABLE_TASK_SCHEDULER_ENDPOINT
output AZURE_DYNAMIC_SESSIONS_POOL_ENDPOINT string = resources.outputs.AZURE_DYNAMIC_SESSIONS_POOL_ENDPOINT
output AZURE_REDIS_HOST_NAME string = resources.outputs.AZURE_REDIS_HOST_NAME
output AZURE_POSTGRES_SERVER_FQDN string = resources.outputs.AZURE_POSTGRES_SERVER_FQDN
output DATABASE_MIGRATION_JOB_NAME string = resources.outputs.DATABASE_MIGRATION_JOB_NAME
output DATABASE_MIGRATION_IDENTITY_NAME string = resources.outputs.DATABASE_MIGRATION_IDENTITY_NAME
output DATABASE_MIGRATION_IDENTITY_PRINCIPAL_ID string = resources.outputs.DATABASE_MIGRATION_IDENTITY_PRINCIPAL_ID
