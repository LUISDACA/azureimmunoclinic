targetScope = 'resourceGroup'

@description('The Container Apps environment created by demo-foundation.bicep.')
param environmentName string = 'cae-immunoclinic-demo'

@description('The private ACR name created by demo-foundation.bicep.')
param registryName string

@description('The verified backend image tag to use for the migration job.')
param imageTag string

@description('The Key Vault name created by demo-foundation.bicep.')
param keyVaultName string

@description('The user-assigned managed identity resource ID for API workload calls.')
param workloadIdentityResourceId string

@description('The user-assigned managed identity resource ID for ACR image pulls.')
param pullIdentityResourceId string

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

resource migrations 'Microsoft.App/jobs@2025-01-01' = {
  name: 'cj-immunoclinic-migrations-demo'
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
      triggerType: 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 0
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
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
      ]
    }
    template: {
      containers: [
        {
          name: 'alembic'
          image: '${registry.properties.loginServer}/immunoclinic-api:${imageTag}'
          command: [
            'alembic'
          ]
          args: [
            'upgrade'
            'head'
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
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
              name: 'VACCINE_REMINDER_ENABLED'
              value: 'false'
            }
          ]
        }
      ]
    }
  }
}

output migrationJobName string = migrations.name
