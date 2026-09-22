targetScope = 'resourceGroup'

param location string = 'eastus2'
@description('Existing environment. Set its logs destination to azure-monitor with az containerapp env update before deploying this template; this template does not replace environment properties.')
param environmentName string = 'cae-mda-live-test-eastus2'
@description('Confirmed budget notification email. The signed-in account is not assumed to be the recipient.')
@minLength(1)
param budgetContactEmail string
@description('First day of the current month in UTC, for example 2026-09-01T00:00:00Z.')
@minLength(1)
param budgetStartDate string
@description('Future expiration in UTC, later than budgetStartDate, for example 2027-09-01T00:00:00Z.')
@minLength(1)
param budgetEndDate string

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: environmentName
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-mda-live-test'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    features: {
      disableLocalAuth: true
    }
  }
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'live-test-logs'
  scope: environment
  properties: {
    workspaceId: workspace.id
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
  }
}

@description('Resource-group-wide monthly cost alerts, not a spending cap. Amount is in the subscription billing currency (USD for the approved $50 budget).')
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: 'budget-mda-live-test'
  properties: {
    category: 'Cost'
    amount: 50
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
      endDate: budgetEndDate
    }
    notifications: {
      actual80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [budgetContactEmail]
      }
      actual100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: [budgetContactEmail]
      }
    }
  }
}

output logAnalyticsWorkspaceId string = workspace.id
output budgetResourceId string = budget.id
