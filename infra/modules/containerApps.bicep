// Container Apps module: wires the four AgentSystem workloads (public
// frontend, internal API, internal worker, internal scale-to-zero operator
// console) onto the shared managed environment, each with least-privilege
// managed identities, Key-Vault-referenced secrets, and probes/scaling per
// the approved plan. Every plain (non-secret) environment variable here is
// derived from other module outputs (FQDNs, endpoints, resource IDs) so no
// connection detail is hardcoded and no literal secret value ever appears in
// this template.
metadata description = 'The four AgentSystem Container Apps (frontend, API, worker, operator console).'

@description('Deployment environment name (e.g. prod, staging), used for the APP_ENV variable and resource naming.')
param environmentName string

@description('Azure region for the Container Apps.')
param location string

@description('Tags applied to all resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('Resource ID of the Container Apps managed environment.')
param environmentId string

@description('Login server (FQDN) of the container registry.')
param registryLoginServer string

@description('URI of the Key Vault used for secret references.')
param keyVaultUri string

@description('Resource ID of the frontend user-assigned managed identity.')
param frontendIdentityId string

@description('Client ID of the frontend user-assigned managed identity.')
param frontendIdentityClientId string

@description('Principal (object) ID of the frontend user-assigned managed identity.')
param frontendIdentityPrincipalId string

@description('Resource ID of the API user-assigned managed identity.')
param apiIdentityId string

@description('Client ID of the API user-assigned managed identity.')
param apiIdentityClientId string

@description('Principal (object) ID of the API user-assigned managed identity.')
param apiIdentityPrincipalId string

@description('Resource ID of the worker user-assigned managed identity.')
param workerIdentityId string

@description('Client ID of the worker user-assigned managed identity.')
param workerIdentityClientId string

@description('Principal (object) ID of the worker user-assigned managed identity.')
param workerIdentityPrincipalId string

@description('Resource ID of the operator console user-assigned managed identity.')
param operatorIdentityId string

@description('Client ID of the operator console user-assigned managed identity.')
param operatorIdentityClientId string

@description('Principal (object) ID of the operator console user-assigned managed identity.')
param operatorIdentityPrincipalId string

@description('Container image repository:tag for the frontend, e.g. myacr.azurecr.io/agentsystem-frontend:sha-abc1234.')
param frontendImage string

@description('Container image repository:tag for the API.')
param apiImage string

@description('Container image repository:tag for the worker.')
param workerImage string

@description('Container image repository:tag for the operator console.')
param operatorImage string

@description('Immutable build/version identifier used for APP_VERSION, CONTAINER_APP_REVISION, and GIT_SHA. CI supplies the full commit SHA.')
param imageTag string

@description('Short DNS-safe suffix used only for Azure Container Apps revision names.')
@minLength(1)
@maxLength(16)
param revisionSuffix string

@description('FQDN of the referenced PostgreSQL Flexible Server.')
param postgresServerFqdn string

@description('Application database name on the PostgreSQL server.')
param postgresDatabaseName string = 'agentsystem'

@description('PostgreSQL Entra ID role name used by the API workload identity (must match a role provisioned on the server for this identity; conventionally the API user-assigned identity display name).')
param postgresApiUsername string

@description('PostgreSQL Entra ID role name used by the worker workload identity (must match a role provisioned on the server for this identity; conventionally the worker user-assigned identity display name).')
param postgresWorkerUsername string

@description('Whether Redis coordination is enabled.')
param redisEnabled bool = true

@description('Host name of the Redis Enterprise (Azure Managed Redis) cluster.')
param redisHostName string

@description('TLS port of the Redis database.')
param redisPort int

@description('Microsoft Entra scope used to acquire Redis access tokens.')
param redisEntraScope string = 'https://redis.azure.com/.default'

@description('Endpoint of the Durable Task Scheduler.')
param durableTaskEndpoint string

@description('Name of the Durable Task task hub.')
param durableTaskHubName string

@description('Primary blob endpoint of the storage account used for artifact storage.')
param blobEndpoint string

@description('Name of the blob container used for durable artifacts.')
param artifactsContainerName string = 'artifacts'

@description('Management endpoint of the Dynamic Sessions pool used for code sandboxing.')
param dynamicSessionsEndpoint string

@description('Microsoft Entra tenant ID used for Easy Auth / Entra bearer validation.')
param entraTenantId string = subscription().tenantId

@description('Microsoft Entra application (audience) ID that the API validates bearer tokens against. Leave empty to disable Entra bearer validation.')
param entraAudience string = ''

@description('Microsoft Entra application client ID used by Container Apps built-in authentication.')
param entraClientId string = ''

@description('Authentication mode for the API: disabled | api_key | easy_auth | entra_jwt.')
param authMode string = 'easy_auth'

@description('Whether Container Apps built-in authentication protects the frontend/operator and the API trusts their forwarded identity headers.')
param easyAuthEnabled bool = true

@description('Key Vault secret holding the Microsoft Entra application client secret used by built-in authentication.')
param entraClientSecretName string = 'microsoft-provider-authentication-secret'

@description('Endpoint of the Azure OpenAI resource used by the API/worker (authenticated via managed identity, never an API key).')
param azureOpenAiEndpoint string = ''

@description('Azure OpenAI chat completion deployment name.')
param azureOpenAiChatDeployment string = ''

@description('Azure OpenAI embedding deployment name. Leave empty to disable vector embeddings.')
param azureOpenAiEmbeddingDeployment string = ''

@description('Azure OpenAI REST API version used by the Agent Framework OpenAIChatCompletionClient on the API and worker. Must match a version supported by the target deployment.')
param azureOpenAiApiVersion string = '2024-12-01-preview'

@description('Application Insights connection string for OpenTelemetry export.')
param applicationInsightsConnectionString string

@description('Name of the Key Vault secret holding the AgentSystem shared API key (used only when authMode=api_key).')
param apiKeySecretName string = 'agentsystem-api-key'

var apiKeySecretUri = '${keyVaultUri}secrets/${apiKeySecretName}'
var entraClientSecretUri = '${keyVaultUri}secrets/${entraClientSecretName}'

// Shared plain environment variables common to every workload.
var commonEnv = [
  { name: 'APP_ENV', value: environmentName }
  { name: 'APP_VERSION', value: imageTag }
  { name: 'CONTAINER_APP_REVISION', value: imageTag }
  { name: 'GIT_SHA', value: imageTag }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsightsConnectionString }
]

// Shared data-plane connectivity variables for the API and worker, which both
// talk to Postgres, Redis, Durable Task, and Blob Storage.
var dataPlaneEnvBase = [
  { name: 'DATABASE_USE_ENTRA', value: 'true' }
  { name: 'DATABASE_ECHO', value: 'false' }
  { name: 'REDIS_ENABLED', value: string(redisEnabled) }
  { name: 'REDIS_USE_ENTRA', value: 'true' }
  { name: 'REDIS_TLS', value: 'true' }
  { name: 'REDIS_ENTRA_SCOPE', value: redisEntraScope }
  { name: 'DURABLE_MODE', value: 'dts' }
  { name: 'DURABLE_TASK_ENDPOINT', value: durableTaskEndpoint }
  { name: 'DURABLE_TASK_HUB', value: durableTaskHubName }
  { name: 'ARTIFACT_MODE', value: 'blob' }
  { name: 'BLOB_ACCOUNT_URL', value: blobEndpoint }
  { name: 'BLOB_CONTAINER', value: artifactsContainerName }
]

var redisUrlEnv = redisEnabled ? [
  { name: 'REDIS_URL', value: 'rediss://${redisHostName}:${redisPort}' }
] : []

var openAiEnv = empty(azureOpenAiEndpoint) || empty(azureOpenAiChatDeployment) ? [] : concat([
  { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAiEndpoint }
  { name: 'AZURE_OPENAI_USE_ENTRA', value: 'true' }
  { name: 'AZURE_OPENAI_CHAT_COMPLETION_MODEL', value: azureOpenAiChatDeployment }
], empty(azureOpenAiApiVersion) ? [] : [
  { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
], empty(azureOpenAiEmbeddingDeployment) ? [] : [
  { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: azureOpenAiEmbeddingDeployment }
])

var apiKeySecretRefs = authMode == 'api_key' ? [
  {
    name: 'AGENTSYSTEM_API_KEY'
    secretRef: apiKeySecretName
    keyVaultUrl: apiKeySecretUri
  }
] : []

var builtInAuthSecretRefs = easyAuthEnabled ? [
  {
    name: 'ENTRA_CLIENT_SECRET'
    secretRef: entraClientSecretName
    keyVaultUrl: entraClientSecretUri
  }
] : []

// -----------------------------------------------------------------------
// Frontend: public-facing static site served by nginx. The frontend source
// reads Vite env vars (VITE_API_BASE_URL etc.) via import.meta.env, which
// Vite substitutes as literal text at build time; there is no runtime
// config shim (e.g. window.__RUNTIME_CONFIG__) in the existing frontend
// source, and adding one is out of scope for this infrastructure change.
// Build-time configuration is therefore supplied as Docker build ARGs (see
// frontend/Dockerfile and azure.yaml's docker.buildArgs) with
// VITE_API_BASE_URL defaulting to the same-origin relative path '/api', so
// the browser always calls the frontend's own origin.
//
// The internal, non-publicly-routable API app is reached via an nginx
// reverse-proxy rule (frontend/Dockerfile's nginx.conf.template) that
// forwards '/api/' to the API app's internal FQDN. That FQDN is only known
// at deploy time, so it is supplied as the API_INTERNAL_BASE_URL container
// environment variable and substituted into the nginx config at container
// start via the official nginx image's envsubst-on-templates mechanism
// (no image rebuild required when the API's FQDN changes).
// '/health/*' liveness/readiness/startup probes are served locally by
// nginx (not proxied), so the frontend's own health does not depend on
// downstream API availability.
// -----------------------------------------------------------------------
module frontendApp 'containerApp.bicep' = {
  name: 'ca-frontend-${resourceToken}'
  params: {
    name: 'ca-frontend-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'frontend' })
    environmentId: environmentId
    userAssignedIdentityId: frontendIdentityId
    image: frontendImage
    registryServer: registryLoginServer
    externalIngress: true
    targetPort: 8080
    ingressEnabled: true
    cpu: '0.25'
    memory: '0.5Gi'
    minReplicas: 1
    maxReplicas: 3
    includeHttpProbes: true
    // Dedicated nginx-only probe paths (never proxied to the API) so a
    // transient backend outage cannot cascade into ACA restarting the
    // frontend container. The SPA's own `/health/ready` calls (used for its
    // in-app backend-status widget) are reverse-proxied straight through to
    // the API by nginx and are intentionally NOT used for these probes.
    livenessPath: '/healthz/live'
    readinessPath: '/healthz/ready'
    startupPath: '/healthz/live'
    environmentVariables: concat(
      commonEnv,
      [
        { name: 'AZURE_CLIENT_ID', value: frontendIdentityClientId }
        { name: 'AZURE_TOKEN_CREDENTIALS', value: 'prod' }
        { name: 'API_INTERNAL_BASE_URL', value: 'https://${apiApp.outputs.fqdn}' }
      ]
    )
    keyVaultSecretRefs: builtInAuthSecretRefs
    entraAuthenticationEnabled: easyAuthEnabled
    entraTenantId: entraTenantId
    entraClientId: entraClientId
    entraAllowedAudience: entraClientId
    entraClientCredentialSettingName: entraClientSecretName
    authExcludedPaths: [
      '/healthz/*'
    ]
    revisionSuffix: revisionSuffix
  }
}

// -----------------------------------------------------------------------
// API: internal-only ingress, reached by the frontend and operator console
// within the managed environment (never exposed publicly).
// -----------------------------------------------------------------------
module apiApp 'containerApp.bicep' = {
  name: 'ca-api-${resourceToken}'
  params: {
    name: 'ca-api-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'api' })
    environmentId: environmentId
    userAssignedIdentityId: apiIdentityId
    image: apiImage
    registryServer: registryLoginServer
    externalIngress: false
    targetPort: 8080
    ingressEnabled: true
    cpu: '0.5'
    memory: '1Gi'
    minReplicas: 1
    maxReplicas: 10
    includeHttpProbes: true
    environmentVariables: concat(
      commonEnv,
      dataPlaneEnvBase,
      redisUrlEnv,
      openAiEnv,
      [
        { name: 'AZURE_CLIENT_ID', value: apiIdentityClientId }
        { name: 'AZURE_TOKEN_CREDENTIALS', value: 'prod' }
        { name: 'REDIS_USERNAME', value: apiIdentityPrincipalId }
        { name: 'DATABASE_URL', value: 'postgresql://${postgresApiUsername}@${postgresServerFqdn}:5432/${postgresDatabaseName}?sslmode=require' }
        { name: 'DYNAMIC_SESSIONS_ENDPOINT', value: dynamicSessionsEndpoint }
        { name: 'CODE_SANDBOX_MODE', value: 'dynamic_sessions' }
        { name: 'AUTH_MODE', value: authMode }
        { name: 'EASY_AUTH_ENABLED', value: 'false' }
        { name: 'ENTRA_TENANT_ID', value: entraTenantId }
        { name: 'ENTRA_AUDIENCE', value: entraAudience }
        { name: 'ENTRA_AUTHORITY', value: '${environment().authentication.loginEndpoint}${entraTenantId}' }
      ]
    )
    keyVaultSecretRefs: apiKeySecretRefs
    revisionSuffix: revisionSuffix
  }
}

// -----------------------------------------------------------------------
// Worker: no HTTP ingress; there is no publicly documented/ground-truthed
// KEDA custom scale rule for Durable Task Scheduler (Consumption) queue
// depth at the time of writing, so this deploys with a static replica
// range (minReplicas/maxReplicas) as the approved interim scaling
// behavior rather than guessing at an unverified custom scale rule
// schema. Revisit and add a customScaleRules entry once a supported
// Durable Task KEDA scaler is confirmed.
// -----------------------------------------------------------------------
module workerApp 'containerApp.bicep' = {
  name: 'ca-worker-${resourceToken}'
  params: {
    name: 'ca-worker-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'worker' })
    environmentId: environmentId
    userAssignedIdentityId: workerIdentityId
    image: workerImage
    registryServer: registryLoginServer
    externalIngress: false
    targetPort: 8080
    ingressEnabled: false
    cpu: '0.5'
    memory: '1Gi'
    minReplicas: 1
    maxReplicas: 5
    includeHttpProbes: false
    environmentVariables: concat(
      commonEnv,
      dataPlaneEnvBase,
      redisUrlEnv,
      openAiEnv,
      [
        { name: 'AZURE_CLIENT_ID', value: workerIdentityClientId }
        { name: 'AZURE_TOKEN_CREDENTIALS', value: 'prod' }
        { name: 'REDIS_USERNAME', value: workerIdentityPrincipalId }
        { name: 'DATABASE_URL', value: 'postgresql://${postgresWorkerUsername}@${postgresServerFqdn}:5432/${postgresDatabaseName}?sslmode=require' }
      ]
    )
    revisionSuffix: revisionSuffix
  }
}

// -----------------------------------------------------------------------
// Operator console: internal-only, scale-to-zero Streamlit dashboard used by
// operators for diagnostics; calls the internal API rather than talking to
// data services directly.
// -----------------------------------------------------------------------
module operatorApp 'containerApp.bicep' = {
  name: 'ca-operator-${resourceToken}'
  params: {
    name: 'ca-operator-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'operator' })
    environmentId: environmentId
    userAssignedIdentityId: operatorIdentityId
    image: operatorImage
    registryServer: registryLoginServer
    externalIngress: false
    targetPort: 8501
    ingressEnabled: true
    cpu: '0.25'
    memory: '0.5Gi'
    minReplicas: 0
    maxReplicas: 1
    includeHttpProbes: true
    livenessPath: '/_stcore/health'
    readinessPath: '/_stcore/health'
    startupPath: '/_stcore/health'
    environmentVariables: concat(
      commonEnv,
      [
        { name: 'AZURE_CLIENT_ID', value: operatorIdentityClientId }
        { name: 'AZURE_TOKEN_CREDENTIALS', value: 'prod' }
        { name: 'AGENTSYSTEM_MODE', value: 'dashboard' }
        { name: 'AGENTSYSTEM_API_URL', value: 'https://${apiApp.outputs.fqdn}' }
      ]
    )
    keyVaultSecretRefs: builtInAuthSecretRefs
    entraAuthenticationEnabled: easyAuthEnabled
    entraTenantId: entraTenantId
    entraClientId: entraClientId
    entraAllowedAudience: entraClientId
    entraClientCredentialSettingName: entraClientSecretName
    authExcludedPaths: [
      '/_stcore/health'
    ]
    revisionSuffix: revisionSuffix
  }
}

@description('Outputs for each of the four Container Apps: id, name, fqdn, and the principal ID of the dedicated user-assigned identity used for its RBAC/registry/secret access.')
output frontend object = {
  id: frontendApp.outputs.id
  name: frontendApp.outputs.name
  fqdn: frontendApp.outputs.fqdn
  principalId: frontendIdentityPrincipalId
}

output api object = {
  id: apiApp.outputs.id
  name: apiApp.outputs.name
  fqdn: apiApp.outputs.fqdn
  principalId: apiIdentityPrincipalId
}

output worker object = {
  id: workerApp.outputs.id
  name: workerApp.outputs.name
  principalId: workerIdentityPrincipalId
}

output operatorConsole object = {
  id: operatorApp.outputs.id
  name: operatorApp.outputs.name
  fqdn: operatorApp.outputs.fqdn
  principalId: operatorIdentityPrincipalId
}
