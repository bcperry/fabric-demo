@description('Microsoft Fabric capacity name.')
param capacityName string

@description('Azure region for the Fabric capacity.')
param location string

@description('Fabric SKU such as F2, F4, or F8.')
@allowed([
  'F2'
  'F4'
  'F8'
  'F16'
  'F32'
  'F64'
])
param skuName string = 'F2'

@description('UPN of the licensed Fabric capacity administrator.')
param adminUpn string

@description('Tags applied to the capacity.')
param tags object = {}

resource fabricCapacity 'Microsoft.Fabric/capacities@2023-11-01' = {
  name: capacityName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: 'Fabric'
  }
  properties: {
    administration: {
      members: [
        adminUpn
      ]
    }
  }
}

output capacityName string = fabricCapacity.name
output capacityId string = fabricCapacity.id
output capacityUrl string = 'https://app.fabric.microsoft.com'
