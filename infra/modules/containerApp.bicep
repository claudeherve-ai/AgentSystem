// Reusable Container App module. Uses a single dedicated user-assigned
// managed identity per app (no system-assigned identity, keeping the
// deployment within the plan's identity budget) for managed-identity-only
// ACR pull and Key-Vault-referenced secrets (no literal secret values ever
// appear in the template), plus liveness/readiness/startup HTTP probes and
// HTTP-based autoscaling. Image tags are supplied per-deployment (immutable
// digests/tags), and the revision suffix is derived from the image
// tag/build metadata so revisions are traceable to a specific build
// (commit SHA).
metadata description = 'Reusable Azure Container Apps module for AgentSystem workloads.'

@description('Name of the Container App.')
param name string

@description('Azure region for the Container App.')
param location string

@description('Tags applied to the Container App.')
param tags object

@description('Resource ID of the Container Apps managed environment.')
param environmentId string

@description('Name of the Consumption workload profile to run on.')
param workloadProfileName string = 'Consumption'

@description('Resource ID of the user-assigned managed identity used for ACR pull and Key Vault secret access.')
param userAssignedIdentityId string

@description('Container image reference, e.g. myacr.azurecr.io/api:sha-abc1234. Must be an immutable tag or digest, never floating "latest" in production.')
param image string

@description('Login server (FQDN) of the container registry, e.g. myacr.azurecr.io.')
param registryServer string

@description('Whether ingress is exposed externally (true only for the public frontend).')
param externalIngress bool = false

@description('TCP port the container listens on (must match the component image entrypoint).')
param targetPort int

@description('Whether ingress is enabled at all (false for the worker, which has no HTTP listener).')
param ingressEnabled bool = true

@description('CPU cores allocated to the container, as a decimal string understood by the ARM json() function, e.g. \'0.5\'.')
param cpu string = '0.5'

@description('Memory allocated to the container, e.g. \'1Gi\'.')
param memory string = '1Gi'

@description('Minimum replica count (0 enables scale-to-zero).')
param minReplicas int = 1

@description('Maximum replica count.')
param maxReplicas int = 3

@description('Whether to include HTTP probes at all (disable only if a component genuinely has no health endpoint).')
param includeHttpProbes bool = true

@description('HTTP path for the liveness probe.')
param livenessPath string = '/health/live'

@description('HTTP path for the readiness probe.')
param readinessPath string = '/health/ready'

@description('HTTP path for the startup probe.')
param startupPath string = '/health/startup'

@description('Plain (non-secret) environment variables for the container.')
param environmentVariables array = []

@description('Key-Vault-referenced secret environment variables. Each item: { name: <container env var name>, secretRef: <secret name>, keyVaultUrl: <full secret URI> }.')
param keyVaultSecretRefs array = []

@description('HTTP concurrent-request scale rule threshold. Ignored when ingressEnabled is false (a queue-based scale rule should be supplied via customScaleRules in that case).')
param httpScaleConcurrentRequests string = '50'

@description('Additional custom scale rules (for example, Azure Storage Queue length for the worker). Each item follows the Container Apps scale rule schema.')
param customScaleRules array = []

@description('Revision suffix used to label this revision with build/commit metadata (for example, the short commit SHA). Must be a valid DNS label segment.')
param revisionSuffix string = ''

@description('Enable Azure Container Apps built-in Microsoft Entra authentication for this app.')
param entraAuthenticationEnabled bool = false

@description('Microsoft Entra tenant ID used by built-in authentication.')
param entraTenantId string = ''

@description('Microsoft Entra application client ID used by built-in authentication.')
param entraClientId string = ''

@description('Audience accepted by built-in authentication. Defaults to the client ID when empty.')
param entraAllowedAudience string = ''

@description('Container App credential setting name used by built-in authentication.')
param entraClientCredentialSettingName string = ''

@description('Paths excluded from built-in authentication, normally local health probes only.')
param authExcludedPaths array = []

var secretEnvVars = [
  for secret in keyVaultSecretRefs: {
    name: secret.name
    secretRef: secret.secretRef
  }
]

resource containerApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    workloadProfileName: workloadProfileName
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: ingressEnabled ? {
        external: externalIngress
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      } : null
      registries: [
        {
          server: registryServer
          identity: userAssignedIdentityId
        }
      ]
      secrets: [
        for secret in keyVaultSecretRefs: {
          name: secret.secretRef
          keyVaultUrl: secret.keyVaultUrl
          identity: userAssignedIdentityId
        }
      ]
    }
    template: {
      revisionSuffix: empty(revisionSuffix) ? null : revisionSuffix
      containers: [
        {
          name: name
          image: image
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: concat(environmentVariables, secretEnvVars)
          probes: includeHttpProbes && ingressEnabled ? [
            {
              type: 'Liveness'
              httpGet: {
                path: livenessPath
                port: targetPort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 15
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: readinessPath
                port: targetPort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 5
              periodSeconds: 10
              failureThreshold: 3
            }
            {
              type: 'Startup'
              httpGet: {
                path: startupPath
                port: targetPort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              failureThreshold: 30
            }
          ] : []
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: concat(
          (ingressEnabled ? [
            {
              name: 'http-scale'
              http: {
                metadata: {
                  concurrentRequests: httpScaleConcurrentRequests
                }
              }
            }
          ] : []),
          customScaleRules
        )
      }
    }
  }
}

resource authConfig 'Microsoft.App/containerApps/authConfigs@2025-01-01' = if (entraAuthenticationEnabled) {
  parent: containerApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      excludedPaths: authExcludedPaths
      redirectToProvider: 'azureactivedirectory'
      unauthenticatedClientAction: 'RedirectToLoginPage'
    }
    httpSettings: {
      requireHttps: true
      routes: {
        apiPrefix: '/.auth'
      }
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        isAutoProvisioned: false
        registration: {
          clientId: entraClientId
          clientSecretSettingName: entraClientCredentialSettingName
          openIdIssuer: '${environment().authentication.loginEndpoint}${entraTenantId}/v2.0'
        }
        validation: {
          allowedAudiences: [
            empty(entraAllowedAudience) ? entraClientId : entraAllowedAudience
          ]
        }
      }
    }
    login: {
      preserveUrlFragmentsForLogins: false
      tokenStore: {
        enabled: true
      }
    }
  }
}

@description('Resource ID of the Container App.')
output id string = containerApp.id

@description('Name of the Container App.')
output name string = containerApp.name

@description('Fully-qualified domain name of the Container App (only populated when ingress is enabled).')
output fqdn string = ingressEnabled ? (containerApp.properties.configuration.?ingress.?fqdn ?? '') : ''
