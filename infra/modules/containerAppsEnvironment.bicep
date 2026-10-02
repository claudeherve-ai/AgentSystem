// Container Apps environment module: VNet-integrated managed environment
// (external, i.e. public static IP at the environment level) on the
// Consumption workload profile, wired to Log Analytics, plus a Dynamic
// Sessions pool used for sandboxed code execution. Per-app public/internal
// exposure is controlled independently on each Container App's own ingress
// configuration (see containerApp.bicep / containerApps.bicep): only the
// frontend sets ingress.external=true, all other apps set it to false and
// remain reachable only from within the VNet.
metadata description = 'Container Apps managed environment and Dynamic Sessions pool for AgentSystem.'

@description('Azure region for the managed environment.')
param location string

@description('Tags applied to all resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('Resource ID of the delegated subnet for the managed environment.')
param infrastructureSubnetId string

@description('Log Analytics workspace customer (workspace) ID for appLogsConfiguration.')
param logAnalyticsCustomerId string

@description('Log Analytics workspace shared key, retrieved at deployment time via listKeys() by the caller. Not a literal secret; required because appLogsConfiguration has no managed-identity alternative.')
@secure()
param logAnalyticsSharedKey string

@description('Maximum number of ready (warm) Dynamic Sessions instances.')
param dynamicSessionsReadySessionInstances int = 0

@description('Maximum number of concurrent Dynamic Sessions instances.')
param dynamicSessionsMaxConcurrentSessions int = 2

@description('Principal IDs allowed to execute code in the Dynamic Sessions pool.')
param sessionExecutorPrincipalIds array = []

@description('Azure ContainerApps Session Executor built-in role definition ID.')
var sessionExecutorRoleDefinitionId = '0fb8eba5-a2bb-4abe-b1c1-49dfad359bb0'

resource managedEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-${resourceToken}'
  location: location
  tags: tags
  properties: {
    vnetConfiguration: {
      // internal:false provisions a public static IP for the environment so
      // the frontend Container App's external ingress is reachable from the
      // internet, while API/worker/operator apps set ingress.external=false
      // on their own Container App resource and remain reachable only from
      // within the VNet / other apps in the environment. The environment
      // remains fully VNet-integrated either way (infrastructureSubnetId is
      // still required and enforced).
      internal: false
      infrastructureSubnetId: infrastructureSubnetId
    }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    zoneRedundant: false
  }
}

resource sessionPool 'Microsoft.App/sessionPools@2025-01-01' = {
  name: 'sp-${resourceToken}'
  location: location
  tags: tags
  properties: {
    environmentId: managedEnvironment.id
    poolManagementType: 'Dynamic'
    containerType: 'PythonLTS'
    scaleConfiguration: {
      maxConcurrentSessions: dynamicSessionsMaxConcurrentSessions
      readySessionInstances: dynamicSessionsReadySessionInstances
    }
    dynamicPoolConfiguration: {
      lifecycleConfiguration: {
        lifecycleType: 'Timed'
        cooldownPeriodInSeconds: 300
        maxAlivePeriodInSeconds: 3600
      }
    }
  }
}

resource sessionExecutorAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in sessionExecutorPrincipalIds: {
    name: guid(sessionPool.id, principalId, sessionExecutorRoleDefinitionId)
    scope: sessionPool
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', sessionExecutorRoleDefinitionId)
    }
  }
]

@description('Resource ID of the managed environment.')
output environmentId string = managedEnvironment.id

@description('Name of the managed environment.')
output environmentName string = managedEnvironment.name

@description('Default domain of the managed environment (used to construct container app FQDNs).')
output defaultDomain string = managedEnvironment.properties.defaultDomain

@description('Resource ID of the Dynamic Sessions pool.')
output sessionPoolId string = sessionPool.id

@description('Management endpoint of the Dynamic Sessions pool.')
output sessionPoolManagementEndpoint string = sessionPool.properties.poolManagementEndpoint
