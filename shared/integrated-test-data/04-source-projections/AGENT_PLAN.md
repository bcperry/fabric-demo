# Agent Plan - Source Projections

## Mission

Implement the two non-streaming source boundaries: administrative/operations
state in PostgreSQL and emulated-test baseline products in ADLS Gen2.

## PostgreSQL projector deliverables

- Passwordless consumer using workload identity.
- Idempotent projection of administrative and sustainment events into test events,
  objectives, required feeds, sites, systems, readiness, maintenance, inventory,
  configuration, findings, corrective actions, and report-review tables.
- Composite per-topic/per-partition checkpoints.
- Dead-letter storage with reason and raw payload.
- Transaction boundaries preventing checkpoint advancement before data commits.
- Managed identity or approved PostgreSQL identity bootstrap and removal of the
  temporary bootstrap password.

## Baseline writer deliverables

- Deterministic predicted tracks, events, measures, model metadata, and
  environmental assumptions.
- Parquet or Delta output partitioned by scenario and run ID.
- Manifest containing counts, checksums, schema versions, and generation timestamp.
- Replay/fallback packages generated from the same scenario.

## Tests

- PostgreSQL migration idempotency and referential integrity.
- Projector replay, duplicates, out-of-order events, poison records, and restart.
- Baseline reproducibility and checksum stability.
- Contract validation for every written record.

## Acceptance

- A local database substitute can exercise projector logic without Azure.
- Reprocessing the same partition does not duplicate operational state.
- Fabric can mirror PostgreSQL where supported or ingest it incrementally using
  `UpdatedAtUtc`.
- ADLS layout matches `README.md` and contains no sensitive or real-world data.

