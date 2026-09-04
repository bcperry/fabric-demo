targetScope = 'resourceGroup'

@description('Short environment name used in resource names.')
@maxLength(8)
param environmentName string = 'dev'

@description('Azure region for all supported resources.')
param location string = resourceGroup().location

@description('Object ID of the user or group administering demo secrets.')
param operatorPrincipalId string

@description('Principal type for the operator.')
@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
param operatorPrincipalType string = 'User'

@description('Existing Fabric capacity resource ID. Fabric capacity is managed outside this deployment.')
param existingFabricCapacityId string

@description('Tenant ID used to enable Microsoft Entra authentication on PostgreSQL.')
param tenantId string

@description('PostgreSQL bootstrap administrator login.')
param postgresAdministratorLogin string = 'mdaadmin'

@secure()
@description('PostgreSQL bootstrap administrator password supplied at deployment time.')
param postgresAdministratorPassword string

@description('AKS node VM size.')
param aksNodeVmSize string = 'Standard_D2s_v5'

@description('Kubernetes namespace used by emulator workloads.')
param kubernetesNamespace string = 'mda-demo'

@description('Kubernetes service account used by emulator workloads.')
param kubernetesServiceAccount string = 'mda-emulators'

@description('Tags applied to every resource.')
param tags object = {
  environment: environmentName
  project: 'mda-integrated-test-operations'
  workload: 'fabric-demo'
  classification: 'synthetic-unclass'
}

var suffix = toLower(environmentName)
var uniqueSuffix = uniqueString(resourceGroup().id)
var storageAccountName = take('stmda${suffix}${uniqueSuffix}', 24)
var registryName = take('acrmda${suffix}${uniqueSuffix}', 50)
var keyVaultName = take('kv-mda-${suffix}-${uniqueSuffix}', 24)
var eventHubsNamespaceName = take('evh-mda-${suffix}-${uniqueSuffix}', 50)
var postgresServerName = take('pg-mda-${suffix}-${uniqueSuffix}', 63)
var aksClusterName = 'aks-mda-${suffix}'
var workloadIdentityName = 'id-mda-emulators-${suffix}'

module storage '../../../shared/infrastructure/modules/storage.bicep' = {
  name: 'deploy-storage'
  params: {
    storageAccountName: storageAccountName
    location: location
    containerName: 'baseline'
    additionalContainerNames: [
      'replay'
      'fallback'
      'silver'
    ]
    tags: tags
  }
}

module keyVault '../../../shared/infrastructure/modules/key-vault.bicep' = {
  name: 'deploy-key-vault'
  params: {
    keyVaultName: keyVaultName
    location: location
    operatorObjectId: operatorPrincipalId
    operatorPrincipalType: operatorPrincipalType
    tags: tags
  }
}

module registry 'modules/container-registry.bicep' = {
  name: 'deploy-container-registry'
  params: {
    registryName: registryName
    location: location
    tags: tags
  }
}

module eventHubs 'modules/event-hubs.bicep' = {
  name: 'deploy-event-hubs'
  params: {
    namespaceName: eventHubsNamespaceName
    location: location
    eventHubs: [
      {
        name: 'sensor-observation'
        partitionCount: 4
      }
      {
        name: 'system-status'
        partitionCount: 4
      }
      {
        name: 'command-integration'
        partitionCount: 4
      }
      {
        name: 'sustainment'
        partitionCount: 2
      }
      {
        name: 'scenario-control'
        partitionCount: 1
      }
    ]
    tags: tags
  }
}

module postgresql 'modules/postgresql.bicep' = {
  name: 'deploy-postgresql'
  params: {
    serverName: postgresServerName
    databaseName: 'mdaoperations'
    location: location
    administratorLogin: postgresAdministratorLogin
    administratorLoginPassword: postgresAdministratorPassword
    tenantId: tenantId
    tags: tags
  }
}

module aks 'modules/aks.bicep' = {
  name: 'deploy-aks'
  params: {
    clusterName: aksClusterName
    location: location
    dnsPrefix: aksClusterName
    nodeVmSize: aksNodeVmSize
    tags: tags
  }
}

resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: workloadIdentityName
  location: location
  tags: tags
}

resource federatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: workloadIdentity
  name: 'mda-emulators'
  properties: {
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: aks.outputs.oidcIssuerUrl
    subject: 'system:serviceaccount:${kubernetesNamespace}:${kubernetesServiceAccount}'
  }
}

resource eventHubsNamespace 'Microsoft.EventHub/namespaces@2024-01-01' existing = {
  name: eventHubsNamespaceName
}

resource eventHubsSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(eventHubsNamespace.id, workloadIdentityName, 'event-hubs-sender')
  scope: eventHubsNamespace
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '2b629674-e913-4c01-ae53-ef4638d8f975'
    )
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource storageContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, workloadIdentityName, 'storage-blob-contributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    )
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource registryResource 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registryResource.id, aksClusterName, 'acr-pull')
  scope: registryResource
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
    principalId: aks.outputs.kubeletObjectId
    principalType: 'ServicePrincipal'
  }
}

output existingFabricCapacityId string = existingFabricCapacityId
output storageAccountName string = storage.outputs.storageAccountName
output adlsGen2Endpoint string = storage.outputs.dfsEndpoint
output adlsContainerNames array = storage.outputs.containerNames
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output containerRegistryName string = registry.outputs.registryName
output containerRegistryLoginServer string = registry.outputs.loginServer
output eventHubsNamespaceName string = eventHubs.outputs.namespaceName
output kafkaBootstrapServer string = eventHubs.outputs.kafkaBootstrapServer
output postgresServerName string = postgresql.outputs.serverName
output postgresDatabaseName string = postgresql.outputs.databaseName
output postgresServerFqdn string = postgresql.outputs.fullyQualifiedDomainName
output aksClusterName string = aks.outputs.clusterName
output workloadIdentityClientId string = workloadIdentity.properties.clientId
output kubernetesNamespace string = kubernetesNamespace
output kubernetesServiceAccount string = kubernetesServiceAccount
