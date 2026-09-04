# Agent Plan - Lakehouse and Medallion Model

## Mission

Build parameterized Fabric notebooks for Bronze, Silver, and Gold mission data
products using the contracts and source projections.

## Deliverables

1. Bronze ingestion/register notebook for streaming history, SQL snapshots, and ADLS baseline.
2. Silver canonical dimensions: site, asset, family, instance, component,
   scenario, test event, track, time, and model version.
3. Silver facts: observations, status, command events, participation, readiness,
   maintenance, predicted events/tracks, measures, and anomalies.
4. Gold products: live health, observed-versus-predicted, sensor-to-effector
   timeline, integrated readiness, objective status, anomaly evidence, quality,
   and quick-look summary.
5. Shared reconciliation and data-quality result tables.

## Reuse targets

- Demo 02 medallion conventions.
- Demo 05 dimensions/facts, date dimension, joins, and integrity checks.
- Demo 06 MERGE, quarantine, time travel, and run logging.

## Acceptance

- Notebooks are independently rerunnable and parameterized by run ID.
- No inferred schema for production paths; contracts drive types.
- Duplicate, late, missing-key, and invalid-enum records are quarantined.
- Every Gold measure has a documented formula and expected baseline value.
- A clean rerun produces identical Gold outputs.

