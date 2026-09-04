# Agent Plan - Eventhouse

## Mission

Create source-controlled KQL definitions for the real-time path from Eventstream
to operational monitoring and anomaly investigation.

## Deliverables

- Tables preserving every envelope field and typed payload field.
- JSON ingestion mappings for each Event Hub.
- Retention, caching, update-policy, and deduplication decisions.
- Reusable KQL functions for latest status, live freshness, track timeline,
  sequence gaps, duplicates, publisher-to-Fabric lag, and delayed acknowledgements.
- Real-Time Dashboard query set with expected columns and sample results.
- Reset commands scoped by run ID, never broad destructive commands.

## Acceptance

- Setup is idempotent with `.create-merge`/`.create-or-alter`.
- Queries filter by `simulation_run_id`.
- Freshness uses publish or Fabric ingestion time, not accelerated event time.
- Exactly one delayed integration event appears in the baseline scenario.
- Raw payload fidelity remains available for forensic drill-through.

