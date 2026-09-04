# Agent Plan - Contracts

## Mission

Make `01-contracts` the authoritative, versioned interface for all producers,
projectors, Fabric ingestion, and analytics.

## Deliverables

- Complete JSON Schemas for scenario, envelope, sensor, status, command,
  sustainment, scenario-control, predicted baseline, and data-quality events.
- Add contracts from `DATA_SOURCE_EMULATION_PLAN.md` for target/interceptor
  telemetry, range instrumentation observations, independent ground truth,
  environment, instrumentation health, network health, readiness polls,
  operator/test-control markers, and synthetic safety status.
- Example valid and intentionally invalid records for every event family.
- Topic/key/partition matrix and compatibility policy.
- Data dictionary covering identifiers, units, timestamps, nullability, enums,
  synthetic bounds, and lineage fields.
- Contract validator that resolves relative `$ref` values offline.
- Versioning rules for additive, breaking, and deprecated fields.

## Domain requirements

- One shared `scenario_id`, `simulation_run_id`, `test_event_id`, and `track_id`
  must correlate the integrated TPY-2, battle-management, THAAD, Army-integration,
  Patriot, and sustainment lanes.
- Event time, publish time, and Fabric ingestion time must remain distinct.
- Measurement time and source-clock identity must also remain distinct for
  telemetry, optical, receiver, and ground-truth observations.
- Locations use fictional coordinates and carry the not-for-navigation notice.
- Abstract command events must not imply real fire-control interfaces.

## Non-goals

- Do not generate production code or Fabric tables here.
- Do not add real system message formats or performance values.

## Acceptance

- Every example validates or fails for its documented reason.
- Duplicate system IDs, invalid classifications, naive timestamps, and out-of-range
  synthetic measures fail validation.
- Compatibility tests prove existing `1.0.0` examples remain accepted.
- `scripts/validate_local.py` executes contract validation without network access.

