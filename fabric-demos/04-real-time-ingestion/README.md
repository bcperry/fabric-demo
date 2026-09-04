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
the typed tables used by reports:

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

Use `EventValidationHealth()` as the source for a Fabric Activator rule. Trigger
when `alert_state` equals `ALERT` (or `issue_count` is greater than zero), then
route the action to the test-data steward through Teams or email. Keeping this
policy non-transactional ensures notification processing cannot block raw-event
preservation.

## Outcome

- **Test-floor engineers:** the `MDA Live Test Control` Real-Time Dashboard
    queries Eventhouse directly with live refresh. It presents raw-event volume,
    latest source readiness, a mission timeline, command-flow latency, and the
    malformed-event quarantine queue in one operational view.
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
