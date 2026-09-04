# MDA Demo Contracts

These JSON Schemas define the stable boundary between scenario configuration,
Kubernetes-hosted producers, Azure Event Hubs, projection services, and Fabric.

All payloads are synthetic and UNCLASS. Field names describe demo concepts, not
real system interfaces.

## Schemas

| Schema | Purpose |
| --- | --- |
| `common/event-envelope.schema.json` | Shared identity, ordering, time, source, and classification fields |
| `scenario.schema.json` | Deterministic sites, systems, instances, profiles, and anomaly configuration |
| `events/sensor-observation.schema.json` | Synthetic detections and track observations |
| `events/system-status.schema.json` | Health, readiness, component, and performance status |
| `events/command-integration.schema.json` | Abstract correlation, cueing, assignment, and acknowledgement |
| `events/sustainment.schema.json` | Maintenance, inventory, configuration, qualification, and readiness changes |
| `events/target-telemetry.schema.json` | Target telemetry source-family records from the Demo 09 integration slice |
| `events/interceptor-telemetry.schema.json` | Interceptor telemetry source-family records from the Demo 09 integration slice |
| `events/instrumentation-observation.schema.json` | Range receiver and optical observations |
| `events/groundtruth-observation.schema.json` | Independent ground-truth reference observations |
| `events/environment-observation.schema.json` | Environment context records |
| `events/instrumentation-health.schema.json` | Instrumentation health evidence from the Demo 10 slice |
| `events/network-health.schema.json` | Abstract communications and network health evidence |
| `events/readiness-poll.schema.json` | Authoritative readiness poll responses |
| `events/operator-test-event.schema.json` | Authoritative operator and test-control markers |
| `events/safety-status.schema.json` | Advisory-only safety-status evidence |

`examples/scenario.integrated-defense.json` is the first deterministic scenario
configuration. Its coordinates, rates, measures, and thresholds are invented.
Positive and negative examples for every event schema are generated under
`examples/*.positive.json` and `examples/*.negative.json` by `generate.py`.

## Contract rules

- Every event uses UTC RFC 3339 timestamps.
- Every event includes `schema_version`, `scenario_id`, `site_id`, and a stable
  source identity.
- Ordering is scoped explicitly with `ordering_key` and `sequence_number`.
- Producers may add payload fields only after the schema version changes.
- Consumers must quarantine invalid records; they must not silently discard them.
- Coordinates are synthetic and marked not for navigation.
