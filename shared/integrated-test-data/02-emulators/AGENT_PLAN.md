# Agent Plan - Emulators

## Mission

Evolve the current deterministic engine into the complete configurable source
suite defined by `DATA_SOURCE_EMULATION_PLAN.md` and Demos 09-10.

## Deliverables

- Separate system-family profile modules behind a shared producer interface.
- Scenario controller with start, pause, resume, stop, reset, replay, and phase changes.
- Seeded fictional location assignment and stable mission identities.
- Predicted and observed timelines sharing one run clock and run ID.
- Normal, degraded, anomaly, recovery, late, duplicate, missing-sequence, and
  schema-mismatch profiles.
- Representative synthetic sensor, status, performance, maintenance, inventory,
  configuration, communications, and qualification data.
- Low-fidelity target/interceptor telemetry, range receiver and optical
  observations, independent ground truth, and environment profiles.
- Instrumentation health, abstract network health, readiness polls,
  operator/test-control markers, and synthetic safety-status profiles.
- Faker-backed random-on-boot exploration and explicit-seed rehearsal modes,
  with a persisted identity/run manifest before event publication.
- JSONL, file, and Kafka/OAuth transports.
- Structured health and delivery metrics without logging credentials.

## Constraints

- Instance count changes through configuration, not copied code.
- Kafka mode is explicit; local JSONL remains the default.
- Event IDs are deterministic within a run and unique across runs.
- Publisher timestamp is actual emit time.
- No real tactical logic or performance envelopes.

## Tests

- Determinism, run uniqueness, filtering, ordering, anomaly timing, location
  separation, contract validation, reconnect behavior, and failed delivery.
- Each family emits only its allowed event types.
- Full 180-second scenario produces the documented expected event counts.
- Multi-rate source clocks, drift, dropout, and recovery produce the documented
  time-alignment and source-failure conclusions.

## Acceptance

- Unit coverage includes every system family and anomaly type.
- Offline container runs non-root and emits valid events.
- Six producers given the same start/run ID produce one coherent timeline.
- Failed Kafka flush returns a nonzero process result.

