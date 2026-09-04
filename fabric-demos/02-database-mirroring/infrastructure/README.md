# Stage 02 PostgreSQL Infrastructure

This template deploys an Azure Database for PostgreSQL 17 Flexible Server and
the `mdaoperations` database for Microsoft Fabric Mirroring. It uses General
Purpose compute because Fabric does not support Burstable source servers. The
server has a system-assigned managed identity and accepts Microsoft Entra
authentication only; PostgreSQL password authentication is disabled.

## Deploy

Set the target subscription and resource group. The following example uses the
signed-in Entra user as the PostgreSQL administrator:

```bash
az account set --subscription '<subscription-id>'
ENTRA_ADMIN_NAME="$(az account show --query user.name --output tsv)"
ENTRA_ADMIN_OBJECT_ID="$(az ad signed-in-user show --query id --output tsv)"
CLIENT_IP="$(curl -fsS https://api.ipify.org)"

az deployment group create \
  --resource-group '<resource-group>' \
  --template-file fabric-demos/02-database-mirroring/infrastructure/main.bicep \
  --parameters \
    entraAdministratorName="$ENTRA_ADMIN_NAME" \
    entraAdministratorObjectId="$ENTRA_ADMIN_OBJECT_ID" \
    entraAdministratorType=User \
    clientStartIpAddress="$CLIENT_IP"
```

Review with `az deployment group what-if` before replacing `create` when the
resource group contains existing infrastructure.

The deployment enables public access and the `0.0.0.0` Azure-services firewall
rule so Fabric can connect. The second firewall rule is restricted to the
supplied client IP. Use a virtual network data gateway and disable public access
for environments requiring network isolation.

## Prepare Mirroring

Use Azure's supported preparation workflow to configure logical replication,
install the managed `azure_cdc` components, and allowlist `mdaoperations`. New
servers already contain the GA mirroring components; do not manually add
`azure_cdc` to `azure.extensions` or `shared_preload_libraries`.

```bash
az postgres flexible-server fabric-mirroring start \
  --resource-group '<resource-group>' \
  --server-name "$SERVER_NAME" \
  --database-names mdaoperations \
  --yes
```

## Seed

The script is destructive within the `mda_ops` schema: it truncates and rebuilds
the synthetic population. Run it before creating the mirror to avoid replicating
the initial load through logical WAL.

```bash
SERVER_NAME="$(az deployment group show \
  --resource-group '<resource-group>' \
  --name '<deployment-name>' \
  --query properties.outputs.serverName.value \
  --output tsv)"

export PGPASSWORD="$(az account get-access-token \
  --resource-type oss-rdbms \
  --query accessToken \
  --output tsv)"
psql \
  "host=${SERVER_NAME}.postgres.database.azure.com port=5432 dbname=mdaoperations user=${ENTRA_ADMIN_NAME} sslmode=require keepalives=1 keepalives_idle=30 keepalives_interval=10 keepalives_count=12" \
  -v fabric_principal_name="$ENTRA_ADMIN_NAME" \
  -f fabric-demos/02-database-mirroring/sql/seed_large.sql
unset PGPASSWORD
```

`PGPASSWORD` carries a short-lived Entra access token because `psql` has no
separate token argument. No database password is created or stored. For a
dedicated Entra user, group, service principal, or managed identity, map it as a
PostgreSQL Entra role first and pass its role name as `fabric_principal_name`.

The default `seed_scale=1` creates 34,674 rows around a fixed inventory of 18
major hardware components and 120 test events. `seed_scale` increases historical
event volume, not fielded asset inventory. Individual controls are also
available: `test_event_count`, `readiness_points`, `maintenance_per_system`, and
`findings_per_event`.

After seeding, follow [`../MIRRORING_SETUP.md`](../MIRRORING_SETUP.md).