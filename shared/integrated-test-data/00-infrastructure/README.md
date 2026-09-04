# MDA Demo Infrastructure

This composition is the current infrastructure baseline for the synthetic MDA
Fabric demo:

- Azure Kubernetes Service with OIDC and workload identity
- Azure Container Registry
- Azure Event Hubs Standard with Kafka support
- Azure Database for PostgreSQL Flexible Server
- ADLS Gen2
- Azure Key Vault
- User-assigned workload identity and least-privilege data-plane roles

It does not deploy a new Fabric capacity. Pass the resource ID of the existing
MCAPS Fabric capacity so the deployment output records the environment
relationship.

## Preview against an existing resource group

This contacts Azure and requires an existing resource group, but it does not
create or update resources:

```powershell
$password = Read-Host "Temporary PostgreSQL bootstrap password" -AsSecureString

.\deploy.ps1 `
  -SubscriptionId "<subscription-id>" `
  -ResourceGroupName "<existing-resource-group>" `
  -ExistingFabricCapacityId "<fabric-capacity-resource-id>" `
  -PostgresAdministratorPassword $password `
  -WhatIf
```

For fully offline validation, run `../scripts/validate_local.py` instead.

## Deploy

```powershell
$password = Read-Host "Temporary PostgreSQL bootstrap password" -AsSecureString

.\deploy.ps1 `
  -SubscriptionId "<subscription-id>" `
  -ExistingFabricCapacityId "<fabric-capacity-resource-id>" `
  -PostgresAdministratorPassword $password
```

The PostgreSQL login is for initial schema bootstrap only. Emulator workloads use AKS
workload identity for Event Hubs and ADLS. A later database-bootstrap step will
create the Microsoft Entra roles required by the projector and ingestion
pipeline before password authentication can be reduced or disabled.

No emulator workloads or Fabric workspace items are deployed by this layer.

The ADLS container layout created by the shared storage module is:

- `bronze`
- `baseline`
- `replay`
- `fallback`
- `silver`
- `gold`

The approved runtime model remains one PostgreSQL administrative database,
running locally in a container for development and on a managed PostgreSQL
service for cloud demonstrations. Native Fabric PostgreSQL mirroring remains the
preferred managed path when the selected region and capacity support it.
