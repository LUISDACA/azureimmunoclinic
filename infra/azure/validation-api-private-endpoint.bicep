targetScope = 'resourceGroup'

@description('Approved region for the isolated validation network resources.')
param location string = resourceGroup().location

var suffix = '6uj5qzgnzi'
var privateEndpointSubnetName = 'appservice-private-endpoints'
var privateEndpointSubnetPrefix = '10.42.0.96/27'

resource network 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: 'vnet-ic-validation-${suffix}'
}

resource apiSite 'Microsoft.Web/sites@2023-12-01' existing = {
  name: 'ic-validation-${suffix}'
}

resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: network
  name: privateEndpointSubnetName
  properties: {
    addressPrefix: privateEndpointSubnetPrefix
    privateEndpointNetworkPolicies: 'Disabled'
  }
}

resource apiPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.azurewebsites.net'
  location: 'global'
}

resource apiPrivateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: apiPrivateDnsZone
  name: 'ic-validation-vnet-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: network.id
    }
  }
}

resource apiPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-ic-validation-api'
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: 'api-connection'
        properties: {
          privateLinkServiceId: apiSite.id
          groupIds: [
            'sites'
          ]
          requestMessage: 'Private access from the isolated Next validation app.'
        }
      }
    ]
  }
}

resource apiPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: apiPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'azurewebsites'
        properties: {
          privateDnsZoneId: apiPrivateDnsZone.id
        }
      }
    ]
  }
}

output apiPrivateEndpointId string = apiPrivateEndpoint.id
