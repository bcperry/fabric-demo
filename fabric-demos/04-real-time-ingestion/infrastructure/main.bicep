@description('Azure region for the Event Hubs namespace.')
param location string = resourceGroup().location

@description('Object ID granted permission to publish events.')
param senderPrincipalId string

@description('Short workload prefix used in resource names.')
@minLength(3)
@maxLength(20)
param namePrefix string = 'mda-demo04'

var uniqueSuffix = substring(uniqueString(subscription().id, resourceGroup().id), 0, 8)
var namespaceName = take('evh-${namePrefix}-${uniqueSuffix}', 50)
var eventHubName = 'mda-test-events'

resource eventHubsNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: namespaceName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    isAutoInflateEnabled: false
    kafkaEnabled: true
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

resource eventHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubsNamespace
  name: eventHubName
  properties: {
    messageRetentionInDays: 1
    partitionCount: 2
  }
}

resource senderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(eventHub.id, senderPrincipalId, 'event-hubs-data-sender')
  scope: eventHub
  properties: {
    principalId: senderPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '2b629674-e913-4c01-ae53-ef4638d8f975'
    )
  }
}

output kafkaBootstrapServer string = '${eventHubsNamespace.name}.servicebus.windows.net:9093'
output eventHubName string = eventHub.name
output namespaceName string = eventHubsNamespace.name
