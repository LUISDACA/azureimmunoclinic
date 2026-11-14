targetScope = 'resourceGroup'

@description('Approved Azure region for this isolated validation environment.')
param location string = resourceGroup().location

@secure()
@description('Generated PostgreSQL administrator password. Never put this value in source control.')
param postgresAdminPassword string

@secure()
@description('Generated FastAPI signing secret.')
param secretKey string

@secure()
@description('Generated FastAPI refresh-token secret.')
param refreshSecretKey string

@secure()
@description('Generated bootstrap administrator password; retrieve it from the protected local file.')
param initialAdminPassword string

@description('Bootstrap administrator address for the isolated validation instance.')
param adminEmail string = 'admin@immunoclinic.example.com'

@description('IPv4 address permitted to reach the restricted SCM deployment endpoint.')
param allowedClientIPv4 string

@description('PostgreSQL administrator login.')
param postgresAdminLogin string = 'immunoclinicadmin'

var suffix = take(uniqueString(subscription().id, resourceGroup().id), 10)
var appName = 'ic-validation-${suffix}'
var planName = 'asp-ic-validation-${suffix}'
var postgresName = 'pg-ic-validation-${suffix}'
var storageName = 'icvalidation${suffix}'
var keyVaultName = 'kv-ic-val-${suffix}'
var privateDnsZoneName = 'private-${suffix}.postgres.database.azure.com'
var subnetPrefix = '10.42.0.0/16'
var postgresSubnetPrefix = '10.42.0.0/28'
var appSubnetPrefix = '10.42.0.32/27'
var blobContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
var acsCommunicationServiceName = 'ic-comm-validation-6uj5qzgnzi'
var acsEmailServiceName = 'ic-email-validation-6uj5qzgnzi'
var databaseUrl = 'postgresql+asyncpg://${postgresAdminLogin}:${postgresAdminPassword}@${postgres.properties.fullyQualifiedDomainName}:5432/immunoclinic?ssl=require'
var apiBaseUrl = 'https://${app.properties.defaultHostName}/api/v1'

resource acsCommunicationService 'Microsoft.Communication/communicationServices@2025-09-01' existing = {
  name: acsCommunicationServiceName
}

resource acsEmailService 'Microsoft.Communication/emailServices@2025-09-01' existing = {
  name: acsEmailServiceName
}

resource acsManagedDomain 'Microsoft.Communication/emailServices/domains@2025-09-01' existing = {
  parent: acsEmailService
  name: 'AzureManagedDomain'
}

resource network 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'vnet-ic-validation-${suffix}'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [subnetPrefix]
    }
    subnets: [
      {
        name: 'postgres'
        properties: {
          addressPrefix: postgresSubnetPrefix
          delegations: [
            {
              name: 'postgres-flexible-server'
              properties: {
                serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers'
              }
            }
          ]
        }
      }
      {
        name: 'appservice-integration'
        properties: {
          addressPrefix: appSubnetPrefix
          delegations: [
            {
              name: 'appservice-vnet-integration'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
          serviceEndpoints: [
            {
              service: 'Microsoft.Storage'
            }
          ]
        }
      }
    ]
  }
}

resource postgresSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  parent: network
  name: 'postgres'
}

resource appSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  parent: network
  name: 'appservice-integration'
}

resource postgresPrivateDns 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateDnsZoneName
  location: 'global'
}

resource postgresDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: postgresPrivateDns
  name: 'ic-validation-vnet-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: network.id
    }
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    version: '17'
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      delegatedSubnetResourceId: postgresSubnet.id
      privateDnsZoneArmResourceId: postgresPrivateDns.id
      publicNetworkAccess: 'Disabled'
    }
    storage: {
      storageSizeGB: 32
      autoGrow: 'Disabled'
    }
  }
  dependsOn: [postgresDnsLink]
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: 'immunoclinic'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: [
        {
          action: 'Allow'
          id: appSubnet.id
        }
      ]
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource evidenceContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'evidence'
  properties: {
    publicAccess: 'None'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled'
  }
}

resource databaseUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'database-url'
  properties: {
    value: databaseUrl
  }
}

resource secretKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'secret-key'
  properties: {
    value: secretKey
  }
}

resource refreshSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'refresh-secret-key'
  properties: {
    value: refreshSecretKey
  }
}

resource adminPasswordSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'admin-password'
  properties: {
    value: initialAdminPassword
  }
}

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
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

resource app 'Microsoft.Web/sites@2024-04-01' = {
  name: appName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    clientAffinityEnabled: false
    publicNetworkAccess: 'Enabled'
    virtualNetworkSubnetId: appSubnet.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appCommandLine: 'python -m alembic upgrade head && python -m gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 1 --bind 0.0.0.0:8000 --timeout 120'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      healthCheckPath: '/'
      vnetRouteAllEnabled: true
      // The app/API is intentionally internet-accessible; FastAPI authz and
      // endpoint permissions protect application data. Keep SCM separately restricted.
      ipSecurityRestrictions: []
      ipSecurityRestrictionsDefaultAction: 'Allow'
      scmIpSecurityRestrictions: [
        {
          name: 'validation-client-scm'
          description: 'Only the approved validation workstation can deploy.'
          action: 'Allow'
          ipAddress: '${allowedClientIPv4}/32'
          priority: 100
        }
      ]
      scmIpSecurityRestrictionsDefaultAction: 'Deny'
      appSettings: [
        {
          name: 'DATABASE_URL'
          value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/database-url/)'
        }
        {
          name: 'SECRET_KEY'
          value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/secret-key/)'
        }
        {
          name: 'REFRESH_SECRET_KEY'
          value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/refresh-secret-key/)'
        }
        {
          name: 'ADMIN_PASSWORD'
          value: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/admin-password/)'
        }
        {
          name: 'ADMIN_EMAIL'
          value: adminEmail
        }
        {
          name: 'ADMIN_FIRST_NAME'
          value: 'Validation'
        }
        {
          name: 'ADMIN_LAST_NAME'
          value: 'Administrator'
        }
        {
          name: 'STORAGE_TYPE'
          value: 'azure_blob'
        }
        {
          name: 'AZURE_STORAGE_ACCOUNT_URL'
          value: 'https://${storage.name}.blob.${environment().suffixes.storage}'
        }
        {
          name: 'AZURE_STORAGE_CONTAINER'
          value: evidenceContainer.name
        }
        {
          name: 'DEBUG'
          value: 'false'
        }
        {
          name: 'EMAIL_ENABLED'
          value: 'true'
        }
        {
          name: 'FRONTEND_URL'
          value: 'https://ic-next-validation-${suffix}.azurewebsites.net'
        }
        {
          name: 'AZURE_COMMUNICATION_EMAIL_ENDPOINT'
          value: 'https://${acsCommunicationService.name}.communication.azure.com'
        }
        {
          name: 'AZURE_COMMUNICATION_EMAIL_SENDER'
          value: 'DoNotReply@${acsManagedDomain.properties.mailFromSenderDomain}'
        }
        {
          name: 'AZURE_COMMUNICATION_EMAIL_TIMEOUT_SECONDS'
          value: '60'
        }
        {
          name: 'FCM_ENABLED'
          value: 'false'
        }
        {
          name: 'VACCINE_REMINDER_ENABLED'
          value: 'false'
        }
        {
          name: 'STARTUP_BOOTSTRAP_ENABLED'
          value: 'false'
        }
        {
          name: 'CORS_ORIGINS'
          value: '[]'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'PORT'
          value: '8000'
        }
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
      ]
    }
  }
  dependsOn: [
    database
    databaseUrlSecret
    secretKeySecret
    refreshSecret
    adminPasswordSecret
  ]
}

resource appLogs 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: app
  name: 'logs'
  properties: {
    applicationLogs: {
      azureBlobStorage: {
        level: 'Off'
      }
      azureTableStorage: {
        level: 'Off'
        // Required by the ARM type; unused while this destination is disabled.
        sasUrl: ''
      }
      fileSystem: {
        level: 'Off'
      }
    }
    detailedErrorMessages: {
      enabled: false
    }
    failedRequestsTracing: {
      enabled: false
    }
    httpLogs: {
      fileSystem: {
        enabled: false
      }
    }
  }
}

resource blobContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, app.id, blobContributorRoleId)
  scope: storage
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributorRoleId)
  }
}

resource keyVaultSecretsAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, app.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
  }
}

output appName string = app.name
output appHostName string = app.properties.defaultHostName
output apiBaseUrl string = apiBaseUrl
output postgresServerName string = postgres.name
output postgresHost string = postgres.properties.fullyQualifiedDomainName
output postgresDatabaseName string = database.name
output storageAccountName string = storage.name
output storageContainerName string = evidenceContainer.name
output keyVaultName string = keyVault.name
output resourceSuffix string = suffix
