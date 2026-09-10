# 04 - Real-Time Ingestion

Exercise governed during-test findings through Eventstream and Eventhouse. The
runnable deterministic fixture contains 15 raw records across five event types
and six source systems, including one duplicate, one malformed record, and one
intentional delayed command event. Thirteen records form the canonical replay.
The separate full-lifecycle stream contains 405 events across 14 topics and is
available for broader integration demonstrations. A configured emulator can
publish the same contracts through an Event Hubs Kafka endpoint.

`provision-realtime` or `push-demo-04` provisions the Fabric side without
external credentials:

- `eh_mda_test` Eventhouse
- `kqldb_mda_test` read/write KQL database
- `RawIntegratedTestEvents` as the single Kafka-envelope destination
- typed `SensorObservation`, `CommandIntegration`, `SystemStatus`, and
    `TestMarker` tables maintained by transactional update policies
- `EventValidationIssue` as a non-transactional quarantine log for malformed
    or unsupported events
- `mda_test_events` Eventstream with one-day retention and low throughput

The Eventstream is intentionally empty until the Kafka endpoint and approved
Fabric connection exist. At that point, add the Kafka source, route its default
stream to `RawIntegratedTestEvents`, validate the JSON mapping for `topic`,
`key`, and `event`, and publish the Eventstream.

## Envelope and parsing

The producer sends the complete canonical record as its Kafka value:

```json
{
    "topic": "mda-test-events",
    "key": "site-alpha:tpy2-alpha-01",
    "event": {
        "event_id": "...",
        "event_type": "system.status",
        "source_system": "TPY2"
    }
}
```

The Eventstream preview therefore shows three top-level columns: `topic`,
`key`, and `event`. Earlier previews displayed each event property as a
top-level column because the producer previously sent only the flattened event
object. The nested form is intentional and matches the raw KQL table contract.

`RawIntegratedTestEvents` deliberately preserves the complete `topic`, `key`,
and `event` envelope. KQL update policies parse valid nested `event` fields into
append-only typed tables:

| `event.event_type` | Parsed destination |
|---|---|
| `sensor.observation` | `SensorObservation` |
| `command.integration` | `CommandIntegration` |
| `system.status` | `SystemStatus` |
| `test.marker`, `preservation.marker` | `TestMarker` |

The parsing functions and their update policies are defined in
`fabric-items/kqldb_mda_test.KQLDatabase/DatabaseSchema.kql`. Invalid records
remain in the raw table for evidence and replay, are excluded from typed tables,
and are copied to `EventValidationIssue` with a reason code and original
payload.

Admission and rejection share `ClassifyIntegratedTestEvents()`. This checks the
supported envelope, not every payload field or operational meaning. The dashboard
uses `CanonicalIntegratedTestEvents(startTime, endTime)` to deduplicate by
scenario/run/event ID. Typed historical tables are not retroactively cleaned by
a schema deployment and should not be treated as deduplicated event counts.

`TestSourceCoverage()` compares the latest declared source families with observed
events only for recorded runs whose event spans overlap the selected window. A
silent gap within that span remains visible. Families are not source instances;
absent declarations or entirely unrecorded runs leave completeness unknown.

Use `EventValidationHealth()` as the source for a Fabric Activator rule. Trigger
when `alert_state` equals `ALERT` (or `issue_count` is greater than zero), then
route the action to the test-data steward through Teams or email. Keeping this
policy non-transactional ensures notification processing cannot block raw-event
preservation.

## Outcome

- **Test-floor engineers:** the `MDA Live Test Control` item opens **Evidence
    Review**, with explicit clock bases, declared source-family coverage,
    deduplicated event counts, reported processing duration, and rejected
    envelopes. Automatic refresh alone does not establish live currency.
- **Leadership:** the `MDA During-Test Decision Brief` Power BI report presents
    the execution recommendation, review posture, recovery ownership,
    acknowledgment state, and evidence-backed findings. Its second page provides
    the preserved evidence and feed-health trace behind the decision.
- **Data professionals:** event contracts, source and ingest timestamps,
  ordering keys, Eventstream routing, KQL, freshness/continuity measures, and
  deterministic replay.

```bash
shared/setup-scripts/fabric_demo_cli.sh push-demo-04
shared/setup-scripts/fabric_demo_cli.sh run-demo-04
```

Replay mode and the Fabric real-time destination are implemented and
reproducible. Live mode is only claimed after the Kafka source is configured,
the Eventstream route is published, and an end-to-end event is observed.

See [LIVE_OPERATIONS_DESIGN.md](LIVE_OPERATIONS_DESIGN.md) for the role-specific
test-floor and director experiences, state semantics, demonstration sequence,
and acceptance criteria required before the demo is presented as live.

## Clock and Replay Contract

- `event_time_utc`: synthetic event time; not the receiver clock.
- `ingest_time_utc`: synthetic source receipt retained from the input.
- `published_time_utc`: actual producer publication time, added without
    overwriting the source receipt field.
- `ingestion_time()`: approximate Eventhouse receipt time; it is not proof of
    clock synchronization or exact transport latency. Old rows may return null.
- A default replay invocation creates a unique run ID and shifts the latest
    event to playback start so accelerated events do not sit in the future.
    `recorded_*` fields preserve shifted originals. `--keep-event-times` retains
    the original window; `--run-id` explicitly reuses an identity for idempotency tests.

The dashboard's raw/rejected tiles use a receipt window; its analytical tiles use
an event window. Do not reconcile those counts across unlike clocks. For the
local recorded fixture, use the [quick-look](../../shared/integrated-test-data/projections/realtime/QUICK_LOOK.md)
and its [build script](../../shared/integrated-test-data/scripts/build_review_package.py).
The package verifies local bytes and leaves review pending.

Before presentation, deploy the schema and execute
[AcceptanceChecks.kql](fabric-items/kqldb_mda_test.KQLDatabase/AcceptanceChecks.kql).
Fabric's item-definition importer does not accept ingestion-time policy commands.
Execute [ReceiptClockSetup.kql](fabric-items/kqldb_mda_test.KQLDatabase/ReceiptClockSetup.kql)
separately before ingesting the rehearsal, and verify receipt timestamps. The
setting does not add timestamps retroactively to previously ingested rows.
Require six cases and zero failures. Separately verify a post-run empty window,
a declared family with no observations, receipt timestamps, and duplicate
reconciliation in a clean rehearsal. These are service-side gates, not claims
made by local source-contract tests.
