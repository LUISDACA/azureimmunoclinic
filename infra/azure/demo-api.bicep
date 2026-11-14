targetScope = 'resourceGroup'

@description('The Container Apps environment created by demo-foundation.bicep.')
param environmentName string = 'cae-immunoclinic-demo'

@description('The private ACR name created by demo-foundation.bicep.')
param registryName string

@description('The image tag to deploy, for example the verified Git commit SHA.')
param imageTag string

@description('The Key Vault name created by demo-foundation.bicep.')
param keyVaultName string

@description('The storage account name from demo-foundation.bicep outputs.')
param storageAccountName string

@description('The user-assigned managed identity client ID for API workload calls.')
param workloadIdentityClientId string

@description('The user-assigned managed identity resource ID for API workload calls.')
param workloadIdentityResourceId string

@description('The user-assigned managed identity resource ID for ACR image pulls.')
param pullIdentityResourceId string

@description('Synthetic administrator email for the non-production environment.')
param adminEmail string = 'admin-demo@immunoclinic.invalid'

resource containerEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: environmentName
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'mi-immunoclinic-demo-workload'
}

resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'mi-immunoclinic-demo-pull'
}

resource api 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-immunoclinic-api-demo'
  location: resourceGroup().location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workloadIdentityResourceId}': {}
      '${pullIdentityResourceId}': {}
    }
  }
  properties: {
    environmentId: containerEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: registry.properties.loginServer
          identity: pullIdentity.id
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/database-url'
          identity: workloadIdentity.id
        }
        {
          name: 'secret-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/secret-key'
          identity: workloadIdentity.id
        }
        {
          name: 'refresh-secret-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/refresh-secret-key'
          identity: workloadIdentity.id
        }
        {
          name: 'admin-password'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/admin-password'
          identity: workloadIdentity.id
        }
      ]
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${registry.properties.loginServer}/immunoclinic-api:${imageTag}'
          resources: {
          cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'SECRET_KEY'
              secretRef: 'secret-key'
            }
            {
              name: 'REFRESH_SECRET_KEY'
              secretRef: 'refresh-secret-key'
            }
            {
              name: 'ADMIN_PASSWORD'
              secretRef: 'admin-password'
            }
            {
              name: 'ADMIN_EMAIL'
              value: adminEmail
            }
            {
              name: 'ADMIN_FIRST_NAME'
              value: 'Demo'
            }
            {
              name: 'ADMIN_LAST_NAME'
              value: 'Admin'
            }
            {
              name: 'STORAGE_TYPE'
              value: 'azure_blob'
            }
            {
              name: 'AZURE_STORAGE_ACCOUNT_URL'
              value: 'https://${storageAccountName}.blob.${environment().suffixes.storage}'
            }
            {
              name: 'AZURE_STORAGE_CONTAINER'
              value: 'evidence'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: workloadIdentityClientId
            }
            {
              name: 'DEBUG'
              value: 'false'
            }
            {
              name: 'EMAIL_ENABLED'
              value: 'false'
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
              name: 'CORS_ORIGINS'
              value: '[]'
            }
          ]
          probes: [
            {
              type: 'Readiness'
              httpGet: {
                path: '/'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 25
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output apiName string = api.name
output apiFqdn string = api.properties.configuration.ingress.fqdn
output apiBaseUrl string = 'https://${api.properties.configuration.ingress.fqdn}/api/v1'
