# 02 - Database Mirroring

Mirror the external PostgreSQL `mdaoperations` database into Microsoft Fabric.
The source stores the operational side of the same simulated release loaded in
Demo 01: test events, objectives, required feeds, sites, systems, readiness,
maintenance, findings, evidence, corrective actions, and report reviews.

## Outcome

- **Leadership:** see current readiness and open findings without waiting for a
  manually exported CSV.
- **Data professionals:** configure an external source, observe CDC-backed
  replication, inspect freshness and lineage, and validate source-to-mirror row
  counts.

## Build

1. Deploy [`infrastructure/main.bicep`](./infrastructure/main.bicep), or identify
  an existing PostgreSQL database that meets the mirroring prerequisites.
2. Run [`sql/seed_large.sql`](./sql/seed_large.sql) to load 34,674
  deterministic, related rows at the default scale. The source separates 18
  major hardware components from their assignments across 120 test events; row
  volume never represents additional fielded assets. The smaller checked-in CSV
  batches remain available for fast validation and fallback ingestion.
3. Create a Fabric mirrored database named `MDA Operations Mirror` using the
  PostgreSQL endpoint and an approved Microsoft Entra organizational account.
4. Select the `mda_ops` tables listed in `MIRRORING_SETUP.md`.
5. Run `01_validate_mirror` after replication reaches Running.

The deployment disables PostgreSQL password authentication. The repository never
stores database credentials. The checked-in CSV files are
both the deterministic source seed and the fallback when native mirroring is
not available in the selected Fabric region or capacity.

The Bicep deploys PostgreSQL 17 on General Purpose compute with a system-assigned
identity, 128 GiB auto-growing storage, and public Azure-service access for
Fabric. Azure CLI's supported preparation workflow configures logical WAL and
the managed `azure_cdc` components. The system identity is required by Fabric
Mirroring; an Entra principal owns the source tables and authenticates the
Fabric connection. See
[`infrastructure/README.md`](./infrastructure/README.md) for secure deployment
and seed commands.
