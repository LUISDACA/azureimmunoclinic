targetScope = 'resourceGroup'

@secure()
@description('Random 32-byte base64 BFF key; pass through a protected parameter file.')
param bffSessionKey string

var suffix = '6uj5qzgnzi'
var nextAppName = 'ic-next-validation-${suffix}'
var keyVaultName = 'kv-ic-val-${suffix}'
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource nextApp 'Microsoft.Web/sites@2023-12-01' existing = {
  name: nextAppName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource databaseUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = {
  parent: keyVault
  name: 'database-url'
}

resource databaseUrlReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(databaseUrlSecret.id, nextAppName, keyVaultSecretsUserRoleId)
  scope: databaseUrlSecret
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: nextApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource appSettings 'Microsoft.Web/sites/config@2023-12-01' = {
  parent: nextApp
  name: 'appsettings'
  dependsOn: [
    databaseUrlReader
  ]
  properties: {
    API_INTERNAL_URL: 'https://ic-validation-${suffix}.azurewebsites.net'
    BFF_ORIGIN: 'https://${nextAppName}.azurewebsites.net'
    BFF_DATABASE_URL: '@Microsoft.KeyVault(SecretUri=${keyVault.properties.vaultUri}secrets/database-url/)'
    BFF_SESSION_KEY: bffSessionKey
    NODE_ENV: 'production'
    WEBSITE_NODE_DEFAULT_VERSION: '~20'
    PORT: '3000'
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'false'
  }
}

output appOrigin string = 'https://${nextAppName}.azurewebsites.net'
