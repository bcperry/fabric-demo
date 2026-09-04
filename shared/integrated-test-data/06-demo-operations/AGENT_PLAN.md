# Agent Plan - Demo Operations

## Mission

Turn the technical solution into a repeatable 20-minute customer demonstration
with deterministic reset, preflight, fallbacks, and recovery guidance.

## Deliverables

- Presenter script with timing, transitions, questions, and exact demo actions.
- Automated local preflight plus documented cloud/Fabric preflight.
- Reset/start/stop/replay procedures scoped by run ID.
- Known-good static and recorded-stream fallback packages.
- Failure matrix for capacity, Kafka, SQL, ADLS, Eventstream, Eventhouse, reports,
  identity, and venue connectivity.
- Demo-day checklist, browser/tab layout, and backup-presenter handoff.
- Expected event counts, Gold values, and anomaly evidence.

## Acceptance

- Two consecutive runs succeed from reset without data repair.
- Core story completes in 20 minutes.
- Each live dependency has a tested fallback preserving the narrative.
- Stop conditions prevent use of wrong tenant, wrong data, or exposed credentials.
- Runbook clearly separates local actions from operations requiring authorization.

