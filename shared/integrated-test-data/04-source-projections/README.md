# Source Projections

This folder defines the non-streaming source boundaries required by the demo.

## PostgreSQL administrative source

The target is one PostgreSQL database containing:

- Test events, objectives, requirements, and required-feed registry
- Sites, assets, components, and system instances
- Readiness history
- Maintenance actions
- Inventory positions
- Findings, corrective actions, and report-review state
- Projector checkpoints
- Dead-letter records

The future sustainment projector consumes the `sustainment` Kafka topic and
performs idempotent PostgreSQL updates. Fabric mirrors these tables where the
selected environment supports it; watermark ingestion plus Delta MERGE is the
fallback.

The checked-in local capstone now includes deterministic PostgreSQL-shaped batch
files under `../data/` plus PostgreSQL DDL and upsert examples under `sql/`:

- `sql/001_schema.sql` defines the target `mda_ops` schema.
- `sql/002_projector_upserts.sql` shows idempotent `ON CONFLICT` projector patterns.
- `../data/postgres_batch_manifest.json` preserves load order, keys, watermarks,
  row counts, and checksums.

The local assets do not create or connect to a PostgreSQL service from this
repository. They define the authoritative administrative target state and the
fallback files used for rehearsal and deterministic validation.

## ADLS Gen2

The future baseline-writer will materialize deterministic emulated-test products
under:

```text
baseline/
  scenario_id=<id>/
    simulation_run_id=<id>/
      predicted_tracks/
      predicted_events/
      predicted_measures/
      environmental_assumptions/
```

Files should be Parquet or Delta. Fabric should use a OneLake shortcut where
possible; copied ingestion is the fallback.
