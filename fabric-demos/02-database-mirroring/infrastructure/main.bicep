targetScope = 'resourceGroup'

@description('Short environment name used in resource names.')
@minLength(2)
@maxLength(10)
param environmentName string = 'demo'

@description('Azure region for the PostgreSQL server.')
param location string = resourceGroup().location

@description('Globally unique PostgreSQL Flexible Server name.')
@maxLength(63)
param serverName string = take('pg-mda-${environmentName}-${uniqueString(resourceGroup().id)}', 63)

@description('PostgreSQL database mirrored into Fabric.')
param databaseName string = 'mdaoperations'

@description('Microsoft Entra tenant used by PostgreSQL authentication.')
param tenantId string = tenant().tenantId

@description('Object ID of the Microsoft Entra principal administering PostgreSQL.')
param entraAdministratorObjectId string

@description('Display name or user principal name of the Microsoft Entra administrator.')
param entraAdministratorName string

@description('Microsoft Entra administrator principal type.')
@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
param entraAdministratorType string = 'User'

@description('General Purpose compute SKU. Burstable SKUs are not supported by Fabric mirroring.')
param skuName string = 'Standard_D2s_v3'

@description('Provisioned storage in GiB. Storage auto-grow is enabled.')
@minValue(32)
@maxValue(32768)
param storageSizeGB int = 128

@description('Allow connections from Azure services, including Microsoft Fabric.')
param allowAzureServices bool = true

@description('Optional first public IPv4 address allowed to run the seed. Leave blank to omit the client rule.')
param clientStartIpAddress string = ''

@description('Optional last public IPv4 address allowed to run the seed. Leave blank to use clientStartIpAddress.')
param clientEndIpAddress string = ''

@description('Tags applied to the PostgreSQL server.')
param tags object = {
  environment: environmentName
  workload: 'mda-fabric-demo'
  stage: '02-database-mirroring'
  classification: 'synthetic-unclass'
}

resource postgresqlServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: serverName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: skuName
    tier: 'GeneralPurpose'
  }
  properties: {
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: tenantId
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    createMode: 'Create'
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    storage: {
      autoGrow: 'Enabled'
      storageSizeGB: storageSizeGB
    }
    version: '17'
  }
}

resource entraAdministrator 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: postgresqlServer
  name: entraAdministratorObjectId
  properties: {
    principalName: entraAdministratorName
    principalType: entraAdministratorType
    tenantId: tenantId
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgresqlServer
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.UTF8'
  }
  dependsOn: [
    entraAdministrator
  ]
}

resource allowAzureServicesRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = if (allowAzureServices) {
  parent: postgresqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
  dependsOn: [
    database
  ]
}

resource clientRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = if (!empty(clientStartIpAddress)) {
  parent: postgresqlServer
  name: 'SeedClient'
  properties: {
    startIpAddress: clientStartIpAddress
    endIpAddress: empty(clientEndIpAddress) ? clientStartIpAddress : clientEndIpAddress
  }
  dependsOn: [
    allowAzureServicesRule
  ]
}

output serverName string = postgresqlServer.name
output serverId string = postgresqlServer.id
output fullyQualifiedDomainName string = postgresqlServer.properties.fullyQualifiedDomainName
output databaseName string = database.name
output systemAssignedIdentityPrincipalId string = postgresqlServer.identity.principalId
