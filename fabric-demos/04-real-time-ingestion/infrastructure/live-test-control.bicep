targetScope = 'resourceGroup'

param location string = 'eastus2'
param environmentName string = 'cae-mda-live-test-eastus2'
param registryName string = 'mdalive4u6mawdzlpyh4'
param jobName string = 'job-mda-live-test'
param identityName string = 'id-mda-live-test-control'
param appName string = 'ca-mda-live-test-control'
param deployApp bool = false
@description('Single-tenant API application client ID. Required when deployApp is true.')
param appClientId string = ''
@description('Control service image with immutable sha256 digest. Required when deployApp is true.')
param controlImage string = ''
@description('Approved job image with immutable sha256 digest. Required when deployApp is true.')
param jobImage string = ''
@description('Identities are not ready. This deployment intentionally denies every protected request.')
@allowed(['{}'])
param roleMapJson string = '{}'

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: environmentName
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource job 'Microsoft.App/jobs@2024-03-01' existing = {
  name: jobName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource jobRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, jobName, 'live-test-control-job-operator')
  properties: {
    roleName: 'Live Test Control Job Operator ${uniqueString(resourceGroup().id)}'
    description: 'Read, start, inspect and stop the existing synthetic live-test job only.'
    type: 'CustomRole'
    permissions: [
      {
        actions: [
          'Microsoft.App/jobs/read'
          'Microsoft.App/jobs/start/action'
          'Microsoft.App/jobs/executions/read'
          'Microsoft.App/jobs/stop/action'
        ]
        notActions: []
        dataActions: []
        notDataActions: []
      }
    ]
    assignableScopes: [resourceGroup().id]
  }
}

resource jobAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(job.id, identity.id, 'live-test-control-job-operator')
  scope: job
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: jobRole.id
  }
}

resource registryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, 'pull')
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = if (deployApp) {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {'${identity.id}': {}}
  }
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {server: registry.properties.loginServer, identity: identity.id}
      ]
    }
    template: {
      containers: [
        {
          name: 'control-service'
          image: controlImage
          env: [
            {name: 'CONTROL_TENANT_ID', value: tenant().tenantId}
            {name: 'CONTROL_AUDIENCE', value: appClientId}
            {name: 'CONTROL_ROLE_MAP_JSON', value: roleMapJson}
            {name: 'CONTROL_IMAGE', value: jobImage}
            {name: 'CONTROL_JOB_RESOURCE_ID', value: job.id}
            {name: 'CONTROL_IDENTITY_CLIENT_ID', value: identity.properties.clientId}
            {name: 'PGUSER', value: identity.name}
          ]
          resources: {cpu: json('0.25'), memory: '0.5Gi'}
          probes: [
            {
              type: 'Liveness'
              httpGet: {path: '/health', port: 8000, scheme: 'HTTP'}
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {path: '/health', port: 8000, scheme: 'HTTP'}
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {minReplicas: 0, maxReplicas: 1}
    }
  }
  dependsOn: [registryPull, jobAssignment]
}

output identityResourceId string = identity.id
output identityClientId string = identity.properties.clientId
output identityPrincipalId string = identity.properties.principalId
output jobRoleDefinitionId string = jobRole.id
output jobRoleAssignmentId string = jobAssignment.id
output registryPullAssignmentId string = registryPull.id
output jobResourceId string = job.id
output environmentResourceId string = environment.id
output registryResourceId string = registry.id
output costScope string = resourceGroup().id
output apiClientId string = appClientId
output controlImageDigestReference string = controlImage
output jobImageDigestReference string = jobImage
output appResourceId string = deployApp ? app.id : ''
output endpoint string = deployApp ? 'https://${app.?properties.configuration.ingress.fqdn ?? ''}' : ''
