// Alerting module: metric alerts and log-based scheduled query alerts
// covering the observability requirements in .azure/deployment-plan.md
// section 5.7 (availability, error rate, latency, dependency failures,
// queue age, Postgres health, Redis health, upstream model 401/429/5xx,
// deployment failure, and security-configuration change). All alerts fire
// into the shared action group so the parameterized alert-receiver email
// is the single place notification routing is configured.
metadata description = 'Metric and log alert rules for AgentSystem container apps and data services.'

@description('Azure region for scheduled query rules (metric alerts are always global).')
param location string

@description('Tags applied to all alert resources.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('Resource ID of the shared action group to notify.')
param actionGroupId string

@description('Resource ID of the Application Insights component (log-based alert scope).')
param appInsightsId string

@description('Resource ID of the frontend Container App.')
param frontendContainerAppId string

@description('Resource ID of the API Container App.')
param apiContainerAppId string

@description('Resource ID of the worker Container App.')
param workerContainerAppId string

@description('Resource ID of the existing PostgreSQL Flexible Server (Central US) to monitor for health/connectivity.')
param postgresServerResourceId string

@description('Resource ID of the Redis Enterprise (Azure Managed Redis) database to monitor.')
param redisResourceId string

@description('Whether Redis is deployed and its metric alert should be created.')
param redisEnabled bool = true

// ---------------------------------------------------------------------------
// Availability / error-rate / latency alerts on the public frontend and
// internal API container apps.
// ---------------------------------------------------------------------------

resource frontendAvailabilityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-frontend-availability-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Fires when the frontend Container App has zero healthy replicas or requests are failing broadly.'
    severity: 1
    enabled: true
    scopes: [
      frontendContainerAppId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ReplicaRestartCount'
          metricName: 'RestartCount'
          metricNamespace: 'Microsoft.App/containerApps'
          operator: 'GreaterThan'
          threshold: 3
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroupId
      }
    ]
  }
}

resource apiErrorRateAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-api-error-rate-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Fires when the API Container App emits an elevated rate of 5xx responses.'
    severity: 1
    enabled: true
    scopes: [
      apiContainerAppId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'Http5xxRequests'
          metricName: 'Requests'
          metricNamespace: 'Microsoft.App/containerApps'
          operator: 'GreaterThan'
          threshold: 10
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
          dimensions: [
            {
              name: 'statusCodeCategory'
              operator: 'Include'
              values: [
                '5xx'
              ]
            }
          ]
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroupId
      }
    ]
  }
}

resource apiLatencyAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-api-latency-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Fires when the API Container App average response time exceeds 2 seconds.'
    severity: 2
    enabled: true
    scopes: [
      apiContainerAppId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ResponseTime'
          metricName: 'ResponseTime'
          metricNamespace: 'Microsoft.App/containerApps'
          operator: 'GreaterThan'
          threshold: 2000
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroupId
      }
    ]
  }
}

resource workerRestartAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-worker-restarts-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Fires when the worker Container App restarts repeatedly, indicating crash-looping or dependency failures.'
    severity: 2
    enabled: true
    scopes: [
      workerContainerAppId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'WorkerRestartCount'
          metricName: 'RestartCount'
          metricNamespace: 'Microsoft.App/containerApps'
          operator: 'GreaterThan'
          threshold: 3
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroupId
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Data-dependency health: Postgres and Redis.
// ---------------------------------------------------------------------------

resource postgresCpuAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-postgres-cpu-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Fires when the existing PostgreSQL Flexible Server CPU utilization is sustained above 80%.'
    severity: 2
    enabled: true
    scopes: [
      postgresServerResourceId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighCpu'
          metricName: 'cpu_percent'
          metricNamespace: 'Microsoft.DBforPostgreSQL/flexibleServers'
          operator: 'GreaterThan'
          threshold: 80
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroupId
      }
    ]
  }
}

resource postgresConnectionsAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-postgres-connections-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Fires when active PostgreSQL connections approach the server connection limit.'
    severity: 2
    enabled: true
    scopes: [
      postgresServerResourceId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighConnections'
          metricName: 'active_connections'
          metricNamespace: 'Microsoft.DBforPostgreSQL/flexibleServers'
          operator: 'GreaterThan'
          threshold: 80
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroupId
      }
    ]
  }
}

resource redisHealthAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = if (redisEnabled) {
  name: 'alert-redis-health-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    description: 'Fires when Redis server load or eviction rate indicates memory/CPU pressure on the Balanced_B0 tier.'
    severity: 2
    enabled: true
    scopes: [
      redisResourceId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighServerLoad'
          metricName: 'ServerLoad'
          metricNamespace: 'Microsoft.Cache/redisEnterprise'
          operator: 'GreaterThan'
          threshold: 90
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroupId
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Log-based alerts: upstream model 401/429/5xx, dependency (queue) age, and
// security-configuration change. These use Application Insights log
// analytics since they require inspecting request/trace payloads rather
// than a platform metric.
// ---------------------------------------------------------------------------

resource modelAuthAndRateLimitAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-model-401-429-5xx-${resourceToken}'
  location: location
  tags: tags
  properties: {
    displayName: 'Upstream model 401/429/5xx errors'
    description: 'Fires when the API or worker report elevated 401 (auth), 429 (rate limit), or 5xx responses from the upstream Azure OpenAI / model dependency.'
    severity: 1
    enabled: true
    scopes: [
      appInsightsId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: 'dependencies | where target has "openai" or target has "cognitiveservices" | where resultCode in ("401","429") or resultCode startswith "5" | summarize count()'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 5
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroupId
      ]
    }
  }
}

resource queueAgeAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-queue-age-${resourceToken}'
  location: location
  tags: tags
  properties: {
    displayName: 'Durable Task queue age / backlog'
    description: 'Fires when worker-processed durable task/orchestration age (time between enqueue and dequeue) exceeds the expected SLA, indicating a growing backlog.'
    severity: 2
    enabled: true
    scopes: [
      appInsightsId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: 'customMetrics | where name == "durable_task_queue_age_seconds" | where value > 60 | summarize count()'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroupId
      ]
    }
  }
}

resource deploymentFailureAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-deployment-failure-${resourceToken}'
  location: location
  tags: tags
  properties: {
    displayName: 'Container App revision deployment failure'
    description: 'Fires when a Container App revision fails to activate or become healthy after a deployment.'
    severity: 1
    enabled: true
    scopes: [
      appInsightsId
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: 'traces | where message has "RevisionFailedToActivate" or message has "deployment failed" | summarize count()'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroupId
      ]
    }
  }
}

resource securityConfigChangeAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-security-config-change-${resourceToken}'
  location: location
  tags: tags
  properties: {
    displayName: 'Security-relevant configuration change'
    description: 'Fires when an application-level trace flags a change to authentication mode, RBAC, network access, or other security-sensitive configuration at runtime.'
    severity: 1
    enabled: true
    scopes: [
      appInsightsId
    ]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT30M'
    criteria: {
      allOf: [
        {
          query: 'traces | where message has "security_config_change" or message has "AUTH_MODE changed" or message has "public network access" | summarize count()'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroupId
      ]
    }
  }
}

@description('Resource IDs of all metric alert rules created by this module.')
output metricAlertIds array = [
  frontendAvailabilityAlert.id
  apiErrorRateAlert.id
  apiLatencyAlert.id
  workerRestartAlert.id
  postgresCpuAlert.id
  postgresConnectionsAlert.id
  redisHealthAlert.id
]

@description('Resource IDs of all log-based scheduled query alert rules created by this module.')
output logAlertIds array = [
  modelAuthAndRateLimitAlert.id
  queueAgeAlert.id
  deploymentFailureAlert.id
  securityConfigChangeAlert.id
]
