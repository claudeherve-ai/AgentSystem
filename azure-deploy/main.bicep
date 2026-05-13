param location string = 'eastus2'
param envName string = 'agentsystem-prod'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: 'acragentsystemow0scq'
}

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: 'ca-env-agentsystem'
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${envName}'
  location: location
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-agentsystem'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8501
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'agentsystem'
          image: '${acr.properties.loginServer}/agentsystem:v5'
          resources: {
            cpu: any('1.0')
            memory: '2.0Gi'
          }
          env: [
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: 'https://tedcherve-6038-resource.cognitiveservices.azure.com/'
            }
          ]
        }
      ]
    }
  }
}
