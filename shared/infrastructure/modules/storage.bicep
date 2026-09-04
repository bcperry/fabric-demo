@description('Globally unique ADLS Gen2 storage account name.')
param storageAccountName string

@description('Azure region for the storage account.')
param location string

@description('Primary analytical container name retained for demo compatibility.')
param containerName string = 'silver'

@description('Additional private containers to create.')
param additionalContainerNames array = []

@description('Tags applied to all resources.')
param tags object = {}

var containerNames = concat([
  'bronze'
  containerName
  'gold'
], additionalContainerNames)

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [
  for name in containerNames: {
    parent: blobService
    name: name
    properties: {
      publicAccess: 'None'
    }
  }
]

output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output dfsEndpoint string = storageAccount.properties.primaryEndpoints.dfs
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output containerNames array = containerNames
