@description('AKS cluster name.')
param clusterName string

@description('Azure region for AKS.')
param location string

@description('DNS prefix for the AKS API server.')
param dnsPrefix string

@description('Initial system node count.')
@minValue(1)
param nodeCount int = 1

@description('Virtual machine size for system nodes.')
param nodeVmSize string = 'Standard_D2s_v5'

@description('Tags applied to AKS resources.')
param tags object = {}

resource cluster 'Microsoft.ContainerService/managedClusters@2024-05-01' = {
  name: clusterName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: dnsPrefix
    enableRBAC: true
    oidcIssuerProfile: {
      enabled: true
    }
    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }
    agentPoolProfiles: [
      {
        name: 'system'
        count: nodeCount
        vmSize: nodeVmSize
        osType: 'Linux'
        osSKU: 'AzureLinux'
        mode: 'System'
        type: 'VirtualMachineScaleSets'
        enableAutoScaling: false
      }
    ]
    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
      networkPolicy: 'azure'
      loadBalancerSku: 'standard'
      outboundType: 'loadBalancer'
    }
  }
}

output clusterName string = cluster.name
output clusterId string = cluster.id
output oidcIssuerUrl string = cluster.properties.oidcIssuerProfile.issuerURL
output kubeletObjectId string = cluster.properties.identityProfile.kubeletidentity.objectId
