targetScope = 'resourceGroup'

@description('Geography where email content and domain sender data are stored.')
param dataLocation string = 'Brazil'

@description('Email Communication Services resource name for validation.')
param emailServiceName string = 'ic-email-validation-6uj5qzgnzi'

@description('Azure Communication Services resource name for validation.')
param communicationServiceName string = 'ic-comm-validation-6uj5qzgnzi'

resource emailService 'Microsoft.Communication/emailServices@2025-09-01' = {
  name: emailServiceName
  location: 'global'
  properties: {
    dataLocation: dataLocation
  }
  tags: {
    application: 'ImmunoClinic'
    environment: 'validation'
  }
}

resource managedDomain 'Microsoft.Communication/emailServices/domains@2025-09-01' = {
  parent: emailService
  name: 'AzureManagedDomain'
  location: 'global'
  properties: {
    domainManagement: 'AzureManaged'
    userEngagementTracking: 'Disabled'
  }
}

resource communicationService 'Microsoft.Communication/communicationServices@2025-09-01' = {
  name: communicationServiceName
  location: 'global'
  properties: {
    dataLocation: dataLocation
    linkedDomains: [
      managedDomain.id
    ]
  }
  tags: {
    application: 'ImmunoClinic'
    environment: 'validation'
  }
}

output communicationEndpoint string = 'https://${communicationService.name}.communication.azure.com'
output senderAddress string = 'DoNotReply@${managedDomain.properties.mailFromSenderDomain}'
output emailServiceId string = emailService.id
output managedDomainId string = managedDomain.id
output communicationServiceId string = communicationService.id
