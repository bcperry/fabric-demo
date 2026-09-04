@description('Globally unique Event Hubs namespace name.')
param namespaceName string

@description('Azure region for Event Hubs.')
param location string

@description('Event hub definitions.')
param eventHubs array

@description('Tags applied to Event Hubs resources.')
param tags object = {}

resource eventHubsNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    isAutoInflateEnabled: true
    maximumThroughputUnits: 4
    kafkaEnabled: true
    publicNetworkAccess: 'Enabled'
    minimumTlsVersion: '1.2'
    disableLocalAuth: true
  }
}

resource hubs 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = [
  for hub in eventHubs: {
    parent: eventHubsNamespace
    name: hub.name
    properties: {
      messageRetentionInDays: hub.?messageRetentionInDays ?? 1
      partitionCount: hub.?partitionCount ?? 4
      status: 'Active'
    }
  }
]

output namespaceName string = eventHubsNamespace.name
output namespaceId string = eventHubsNamespace.id
output kafkaBootstrapServer string = '${eventHubsNamespace.name}.servicebus.windows.net:9093'
output eventHubNames array = map(hubs, hub => hub.name)
