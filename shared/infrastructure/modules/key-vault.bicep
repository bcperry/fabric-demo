@description('Globally unique Key Vault name.')
param keyVaultName string

@description('Azure region for Key Vault.')
param location string

@description('Optional object ID receiving Key Vault Secrets Officer.')
param operatorObjectId string = ''

@description('Principal type for the operator role assignment.')
@allowed([
  'User'
  'Group'
  'ServicePrincipal'
])
param operatorPrincipalType string = 'User'

@description('Tags applied to Key Vault.')
param tags object = {}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenant().tenantId
    enableRbacAuthorization: true
    enabledForDeployment: false
    enabledForTemplateDeployment: true
    enablePurgeProtection: false
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource secretsOfficerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(operatorObjectId)) {
  name: guid(keyVault.id, operatorObjectId, 'secrets-officer')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
    )
    principalId: operatorObjectId
    principalType: operatorPrincipalType
  }
}

output keyVaultName string = keyVault.name
output keyVaultId string = keyVault.id
output keyVaultUri string = keyVault.properties.vaultUri
