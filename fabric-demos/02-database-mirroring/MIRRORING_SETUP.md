# PostgreSQL Mirroring Setup

## External Source

The Stage 02-only Azure PostgreSQL deployment is
[`infrastructure/main.bicep`](./infrastructure/main.bicep). It configures the
General Purpose server, system identity, Entra-only authentication, and network
access required by Fabric Mirroring. Run Azure CLI's supported
`fabric-mirroring start` workflow to configure logical replication and the
managed `azure_cdc` components for `mdaoperations`.
For an existing PostgreSQL server, create database `mdaoperations`, then apply
[`001_schema.sql`](../../shared/integrated-test-data/04-source-projections/sql/001_schema.sql).

For a large demonstration, run [`sql/seed_large.sql`](./sql/seed_large.sql)
before creating the Fabric mirror. At default scale it generates 34,674
deterministic rows across 15 operational and projector tables. The 18 major
hardware components are assigned to 120 distributed-integration, live-intercept,
and operational-exercise events through `event_participant`. Alternatively,
load the smaller files listed in
[`postgres_batch_manifest.json`](../../shared/integrated-test-data/data/postgres_batch_manifest.json)
in manifest order. Use the table name implied by each file name and preserve the
provided primary keys and timestamps.

`seed_large.sql` uses `TRUNCATE`, which Fabric Mirroring does not replicate.
If the mirror already exists, stop mirroring before rerunning the seed, then
start mirroring after the seed commits. Restarting performs a clean snapshot
and discovers newly added source tables; do not edit the table selection while
the destructive seed is running.

## Fabric

In the `mda-fabric-demo` workspace:

1. Select **New item → Mirrored database → Azure Database for PostgreSQL**.
2. Name it `MDA Operations Mirror`.
3. Enter the external server and `mdaoperations` database connection details.
4. Select **Organizational account** authentication and sign in as the Entra
   principal mapped by `seed_large.sql`. Do not select Basic authentication.
5. Select these `mda_ops` tables: `test_event`, `test_objective`,
   `required_feed`, `site`, `system_instance`, `event_participant`, `readiness_history`,
   `maintenance_action`, `inventory_position`, `finding`, `finding_evidence`,
   `corrective_action`, `report_review`, `projector_checkpoint`, and
   `projector_dead_letter`.
6. Start mirroring and wait for every table to report **Running**.
7. Expose the mirrored tables to `01_validate_mirror` through its attached
   Lakehouse or SQL analytics context.
8. Record the mirrored database item in workspace lineage and run the validation
   notebook.

## Demo Checks

- Source and mirror row counts agree with the batch manifest.
- The newest `recorded_at_utc` or `updated_at_utc` value is visible in Fabric.
- A controlled source update appears in the mirror without rerunning an export.
- The mirrored tables connect to the Stage 03 star-schema build.

If native PostgreSQL mirroring is unavailable, label the path **incremental
fallback**, ingest the same manifest in order, and do not describe it as mirroring.
