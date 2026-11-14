targetScope = 'resourceGroup'

@description('Approved region for the isolated validation web app.')
param location string = resourceGroup().location

@description('Only this workstation may access the validation UI and SCM site.')
param allowedClientIPv4 string

var suffix = '6uj5qzgnzi'
var appName = 'ic-next-validation-${suffix}'
var planName = 'asp-ic-next-validation-${suffix}'
var integrationSubnetName = 'appservice-next'
var subnetPrefix = '10.42.0.64/27'

resource network 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: 'vnet-ic-validation-${suffix}'
}

resource integrationSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: network
  name: integrationSubnetName
  properties: {
    addressPrefix: subnetPrefix
    delegations: [
      {
        name: 'appservice-next-delegation'
        properties: {
          serviceName: 'Microsoft.Web/serverFarms'
        }
      }
    ]
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  kind: 'linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
    size: 'B1'
    family: 'B'
    capacity: 1
  }
  properties: {
    reserved: true
  }
}

resource nextApp 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'NODE|20-lts'
      appCommandLine: 'node server.js'
      alwaysOn: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      http20Enabled: true
      ipSecurityRestrictions: [
        {
          name: 'validation-client'
          description: 'Only the approved validation workstation can access Next.'
          ipAddress: allowedClientIPv4
          action: 'Allow'
          priority: 100
        }
        {
          name: 'deny-all'
          description: 'Deny all other inbound traffic.'
          ipAddress: 'Any'
          action: 'Deny'
          priority: 2147483647
        }
      ]
      scmIpSecurityRestrictionsUseMain: true
    }
  }
}

// Runtime settings and Key Vault access are applied separately so rerunning
// this infrastructure template cannot replace or erase secret app settings.
output appName string = appName
output appOrigin string = 'https://${appName}.azurewebsites.net'
output appSubnetId string = integrationSubnet.id
