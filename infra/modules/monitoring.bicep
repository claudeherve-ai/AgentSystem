// Monitoring module: Log Analytics workspace (daily-capped), workspace-based
// Application Insights, an action group for alert notifications, and a monthly
// cost budget with 50/80/100% thresholds.
metadata description = 'Observability and cost-guardrail resources for AgentSystem.'

@description('Azure region for monitoring resources.')
param location string

@description('Tags applied to all resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('Daily ingestion cap (GB) for the Log Analytics workspace.')
param logAnalyticsDailyQuotaGb int = 1

@description('Log Analytics retention in days.')
param logAnalyticsRetentionInDays int = 30

@description('Email address that receives budget and alert notifications.')
param alertReceiverEmail string

@description('Monthly budget amount in the billing currency.')
param budgetAmount int = 500

@description('Environment name used to scope the budget name and time window.')
param environmentName string

@description('Start date (first of current month) for the budget time period. utcNow() may only be used as a parameter default, so this is computed at deployment time.')
param budgetStartDate string = utcNow('yyyy-MM-01')

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: 'log-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: logAnalyticsRetentionInDays
    workspaceCapping: {
      dailyQuotaGb: logAnalyticsDailyQuotaGb
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${resourceToken}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
    DisableIpMasking: false
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: take('ag${resourceToken}', 12)
    enabled: true
    emailReceivers: [
      {
        name: 'operatorEmail'
        emailAddress: alertReceiverEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

resource budget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: 'budget-${environmentName}'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    notifications: {
      actual_50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: [
          alertReceiverEmail
        ]
      }
      actual_80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [
          alertReceiverEmail
        ]
      }
      forecasted_100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: [
          alertReceiverEmail
        ]
      }
    }
  }
}

@description('Resource ID of the Log Analytics workspace.')
output logAnalyticsWorkspaceId string = logAnalytics.id

@description('Name of the Log Analytics workspace.')
output logAnalyticsWorkspaceName string = logAnalytics.name

@description('Customer ID (workspace ID) of the Log Analytics workspace.')
output logAnalyticsCustomerId string = logAnalytics.properties.customerId

@description('Resource ID of the Application Insights component.')
output appInsightsId string = appInsights.id

@description('Connection string for the Application Insights component.')
output appInsightsConnectionString string = appInsights.properties.ConnectionString

@description('Resource ID of the action group used for alert notifications.')
output actionGroupId string = actionGroup.id
