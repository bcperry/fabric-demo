@description('Globally unique PostgreSQL flexible server name.')
param serverName string

@description('PostgreSQL database name.')
param databaseName string

@description('Azure region for PostgreSQL resources.')
param location string

@description('Bootstrap PostgreSQL administrator login used only for initial setup.')
param administratorLogin string

@secure()
@description('Bootstrap PostgreSQL administrator password supplied only at deployment time.')
param administratorLoginPassword string

@description('Tenant ID used for Microsoft Entra authentication on PostgreSQL.')
param tenantId string

@description('Tags applied to PostgreSQL resources.')
param tags object = {}

resource postgresqlServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: serverName
  location: location
  tags: tags
  sku: {
    name: 'Standard_B2s'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Enabled'
      tenantId: tenantId
    }
    availabilityZone: '1'
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
      storageSizeGB: 32
    }
    version: '16'
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgresqlServer
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.UTF8'
  }
}

output serverName string = postgresqlServer.name
output serverId string = postgresqlServer.id
output databaseName string = database.name
output fullyQualifiedDomainName string = postgresqlServer.properties.fullyQualifiedDomainName
