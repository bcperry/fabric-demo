# Fabric Implementation Map

No Fabric items are created automatically. This folder holds source-controlled
definitions and implementation instructions.

## Planned workspace

| Item | Suggested name | Purpose |
| --- | --- | --- |
| Workspace | `MDA Integrated Test Demo` | Capacity-assigned project boundary |
| Eventhouse | `eh_mda_test` | Streaming hot path |
| KQL Database | `kqldb_mda_test` | Event tables and real-time queries |
| Lakehouse | `lh_mda_test` | Bronze, Silver, and Gold Delta data |
| Pipeline | `pl_mda_sources` | PostgreSQL fallback ingestion and orchestration |
| Semantic model | `sm_mda_test` | Shared test/readiness measures |
| Power BI report | `MDA Test and Readiness` | Historical and leadership views |
| Real-Time Dashboard | `MDA Live Test Control` | Live event monitoring |

The checked-in local assets under `../data/` are the authoritative rehearsal
package for this folder. They provide:

- One deterministic observed stream fallback file with all integrated topics.
- PostgreSQL-shaped administrative batches plus a load-order manifest.
- ADLS-style baseline files for predicted tracks, command events, measures, and environment assumptions.

## Eventstream routing

| Event Hub | Eventhouse table | Durable destination |
| --- | --- | --- |
| `sensor-observation` | `SensorObservation` | Bronze sensor events |
| `system-status` | `SystemStatus` | Bronze system status |
| `command-integration` | `CommandIntegration` | Bronze command events |
| `sustainment` | `SustainmentEvent` | PostgreSQL projector plus Bronze |
| `target-telemetry` | `TargetTelemetry` | Bronze target telemetry |
| `interceptor-telemetry` | `InterceptorTelemetry` | Bronze interceptor telemetry |
| `instrumentation-observation` | `InstrumentationObservation` | Bronze instrumentation and optical evidence |
| `ground-truth-observation` | `GroundTruthObservation` | Bronze independent reference track |
| `environment-observation` | `EnvironmentObservation` | Bronze environment context |
| `instrumentation-health` | `InstrumentationHealth` | Bronze health evidence |
| `network-health` | `NetworkHealth` | Bronze network evidence |
| `readiness-poll` | `ReadinessPoll` | Bronze readiness evidence |
| `operator-test-event` | `OperatorTestEvent` | Bronze authoritative decision markers |
| `safety-status` | `SafetyStatus` | Bronze advisory-only safety evidence |

Run `eventhouse/setup.kql` in the KQL database before connecting Eventstream.
Use `eventhouse/demo-queries.kql` as the starting point for the Real-Time
Dashboard and anomaly investigation.

## Lakehouse layers

- Bronze preserves raw event, PostgreSQL, and ADLS source fidelity.
- Silver resolves canonical site, system, track, test, readiness, and maintenance
  entities.
- Gold produces integrated readiness, sensor-to-effector timeline,
  observed-versus-predicted measures, anomaly evidence, data quality, and
  quick-look summaries.

The intended local-to-Fabric mapping is:

- Bronze observed stream tables from `../data/observed_eventstream.jsonl`
- Bronze PostgreSQL fallback tables from `../data/postgres_*.csv`
- Bronze baseline files from `../data/baseline/**`

Authoritative human decisions must remain sourced from `OperatorTestEvent` or
PostgreSQL review tables. `SafetyStatus` is evidence only.

Notebook and pipeline definitions will be added only after the three source
boundaries are validated independently.
