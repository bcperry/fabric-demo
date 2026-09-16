param location string = resourceGroup().location
param computeLocation string = 'eastus2'
param eventHubsNamespaceName string = 'evh-mda-demo04-nqajiaxw'
param deployJob bool = false
param imageTag string = 'live-test-v1'
param fabricWorkspacePrincipalId string = '1e4bc00c-7bac-4c5d-9bcd-a399e53e8ac4'

var suffix = uniqueString(resourceGroup().id)

resource namespace 'Microsoft.EventHub/namespaces@2024-01-01' existing = {
  name: eventHubsNamespaceName
}

resource hub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: namespace
  name: 'target-vehicle-telemetry'
  properties: {
    partitionCount: 2
    messageRetentionInDays: 1
  }
}

resource consumer 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  parent: hub
  name: 'fabric-live-test'
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-mda-live-test'
  location: location
}

resource receiver 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(hub.id, fabricWorkspacePrincipalId, 'receiver')
  scope: hub
  properties: {
    principalId: fabricWorkspacePrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a638d3c7-ab3a-418d-83e6-5f17a39d4fde')
  }
}

resource sender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(hub.id, identity.id, 'sender')
  scope: hub
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2b629674-e913-4c01-ae53-ef4638d8f975')
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'mdalive${suffix}'
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, 'pull')
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-mda-live-test-${computeLocation}'
  location: computeLocation
  properties: {
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
  }
}

resource job 'Microsoft.App/jobs@2024-03-01' = if (deployJob) {
  name: 'job-mda-live-test'
  location: computeLocation
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1020
      replicaRetryLimit: 0
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      registries: [
        { server: registry.properties.loginServer, identity: identity.id }
      ]
    }
    template: {
      containers: [
        {
          name: 'target-vehicle'
          image: '${registry.properties.loginServer}/target-vehicle:${imageTag}'
          args: ['--transport', 'kafka', '--event-hubs', '--duration', '900']
          env: [
            { name: 'KAFKA_BOOTSTRAP_SERVERS', value: '${namespace.name}.servicebus.windows.net:9093' }
            { name: 'KAFKA_TOPIC', value: hub.name }
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'VEHICLE_ID', value: 'target-01' }
          ]
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
        }
      ]
    }
  }
  dependsOn: [pull, sender]
}

output registryName string = registry.name
output jobResourceId string = resourceId('Microsoft.App/jobs', 'job-mda-live-test')
output eventHubResourceId string = hub.id
output kafkaBootstrapServers string = '${namespace.name}.servicebus.windows.net:9093'