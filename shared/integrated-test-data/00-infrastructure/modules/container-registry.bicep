@description('Globally unique Azure Container Registry name.')
param registryName string

@description('Azure region for the registry.')
param location string

@description('Tags applied to the registry.')
param tags object = {}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

output registryName string = registry.name
output registryId string = registry.id
output loginServer string = registry.properties.loginServer
