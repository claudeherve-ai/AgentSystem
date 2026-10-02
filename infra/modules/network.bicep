// Network module: VNet, subnets, NSGs, and private DNS zones for the AgentSystem
// East US 2 Container Apps environment and its private-endpoint-connected data services.
metadata description = 'Virtual network, subnets, NSGs, and private DNS zones for AgentSystem.'

@description('Azure region for all network resources.')
param location string

@description('Tags applied to all resources in this module.')
param tags object

@description('Short, unique resource token used for deterministic naming.')
@minLength(13)
@maxLength(13)
param resourceToken string

@description('VNet address space.')
param vnetAddressPrefix string = '10.20.0.0/16'

@description('Address prefix for the Container Apps environment infrastructure subnet (requires /23 or larger).')
param containerAppsSubnetPrefix string = '10.20.0.0/23'

@description('Address prefix for the private endpoints subnet.')
param privateEndpointsSubnetPrefix string = '10.20.2.0/24'

var vnetName = 'vnet-${resourceToken}'
var containerAppsSubnetName = 'snet-containerapps'
var privateEndpointsSubnetName = 'snet-privateendpoints'

// NSG for the Container Apps infrastructure subnet: allow only the traffic the
// managed environment itself requires; all inbound app traffic terminates at the
// environment's ingress, not directly on the subnet.
resource nsgContainerApps 'Microsoft.Network/networkSecurityGroups@2024-07-01' = {
  name: 'nsg-containerapps-${resourceToken}'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowAzureLoadBalancerInbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowContainerAppsEastWest'
        properties: {
          priority: 110
          access: 'Allow'
          direction: 'Inbound'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: 'VirtualNetwork'
        }
      }
      {
        name: 'DenyAllInbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

// NSG for the private endpoints subnet: private endpoints only accept inbound
// traffic from within the VNet; no internet exposure.
resource nsgPrivateEndpoints 'Microsoft.Network/networkSecurityGroups@2024-07-01' = {
  name: 'nsg-privateendpoints-${resourceToken}'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowVnetInbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          destinationAddressPrefix: 'VirtualNetwork'
        }
      }
      {
        name: 'DenyAllInbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: containerAppsSubnetName
        properties: {
          addressPrefix: containerAppsSubnetPrefix
          networkSecurityGroup: {
            id: nsgContainerApps.id
          }
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: privateEndpointsSubnetName
        properties: {
          addressPrefix: privateEndpointsSubnetPrefix
          networkSecurityGroup: {
            id: nsgPrivateEndpoints.id
          }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

resource containerAppsSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' existing = {
  parent: vnet
  name: containerAppsSubnetName
}

resource privateEndpointsSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' existing = {
  parent: vnet
  name: privateEndpointsSubnetName
}

// Private DNS zones for every private-endpoint-connected service.
var privateDnsZoneNames = [
  'privatelink.postgres.database.azure.com'
  'privatelink.redis.azure.net'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.vaultcore.azure.net'
  'privatelink.azurecr.io'
]

resource privateDnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [
  for zoneName in privateDnsZoneNames: {
    name: zoneName
    location: 'global'
    tags: tags
  }
]

resource privateDnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [
  for (zoneName, i) in privateDnsZoneNames: {
    parent: privateDnsZones[i]
    name: 'link-${vnetName}'
    location: 'global'
    tags: tags
    properties: {
      registrationEnabled: false
      virtualNetwork: {
        id: vnet.id
      }
    }
  }
]

@description('Resource ID of the VNet.')
output vnetId string = vnet.id

@description('Name of the VNet.')
output vnetName string = vnet.name

@description('Resource ID of the Container Apps environment infrastructure subnet.')
output containerAppsSubnetId string = containerAppsSubnet.id

@description('Resource ID of the private endpoints subnet.')
output privateEndpointsSubnetId string = privateEndpointsSubnet.id

@description('Map of private DNS zone name to resource ID.')
output privateDnsZoneIds object = {
  postgres: privateDnsZones[0].id
  redis: privateDnsZones[1].id
  blob: privateDnsZones[2].id
  keyVault: privateDnsZones[3].id
  acr: privateDnsZones[4].id
}
