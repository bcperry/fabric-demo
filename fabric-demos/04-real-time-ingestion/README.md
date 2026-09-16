# 04 - Real-Time Ingestion

## On-demand Live Test

The separate [Live Test folder](https://app.fabric.microsoft.com/groups/10327698-2b0d-446f-9b1b-beabe18a4bda/list?subfolderId=124442)
contains an on-demand synthetic asset stream, independent of the governed evidence stream below.

1. Open [Start Live Test](https://app.fabric.microsoft.com/groups/10327698-2b0d-446f-9b1b-beabe18a4bda/synapsenotebooks/0025467b-0c80-4b3d-ae03-241016221e19) and select **Run all**.
2. On the first run in a Spark session, complete the Microsoft device-code sign-in shown in the cell output. Use an account with permission to read/start/stop `job-mda-live-test` in the commercial demo subscription. Tokens remain in session memory, not notebook source. Tenant Conditional Access may restrict this flow.
3. Open [Live Test - Asset Monitor](https://app.fabric.microsoft.com/groups/10327698-2b0d-446f-9b1b-beabe18a4bda/kustodashboards/f4b3e1bd-a1c1-4bd3-a581-98fc9a6912f0). The map shows five-second breadcrumb positions from the current flight's last hour, plus a distinct latest-position marker labeled with asset and freshness status. Previous flights are excluded. These are dots, not a connected route line. The other tiles show recent records, altitude, temperature, and error word. Zoom out for Pacific context as needed.
4. A flight runs for 15 minutes and stops automatically. Change `ACTION` to `status` or `stop` and rerun the cell to inspect or stop it. Restore `start` for the next flight. The active-execution check avoids ordinary repeated clicks, but is not an atomic multi-user lock.

The dashboard requests live updates with a 10-second minimum and a 30-second fallback.
This is refreshed telemetry, not frame-by-frame animation. `LIVE` means sample age under
30 seconds; `STALE` retains the last point after a flight stops; `NO DATA` means no sample
in the last day. Receipt lag is approximate and depends on clock alignment. These are
synthetic visualization trajectories, not validated flight dynamics or operational readiness decisions.

The manual Container Apps Job runs in East US 2 (Central US compute capacity was unavailable).
Its managed identity sends to `target-vehicle-telemetry` in the existing Event Hubs namespace.
`live_target_telemetry` consumes through `fabric-live-test`, using workspace identity, and writes
`RawTargetVehicleEvents` in the existing Eventhouse. The original `mda-test-events`,
`RawIntegratedTestEvents`, capacity, and evidence dashboards are unchanged.

Deployment source: [live-test.bicep](infrastructure/live-test.bicep),
[LiveTest.kql](fabric-items/kqldb_mda_test.KQLDatabase/LiveTest.kql), and
[publish_live_test.py](scripts/publish_live_test.py). Deploy infrastructure with `deployJob=false`,
build the image in ACR, then redeploy with `deployJob=true`:

```bash
az cloud set --name AzureCloud
az account set --subscription a679b60b-99ab-4a54-ac23-2523c39342de
az deployment group create -g fabric-mda-demo -n demo04-live-test --template-file fabric-demos/04-real-time-ingestion/infrastructure/live-test.bicep
az acr build --registry mdalive4u6mawdzlpyh4 --image target-vehicle:live-test-v1 --file shared/integrated-test-data/02-emulators/Dockerfile.target-vehicle shared/integrated-test-data/02-emulators
az deployment group create -g fabric-mda-demo -n demo04-live-test --template-file fabric-demos/04-real-time-ingestion/infrastructure/live-test.bicep --parameters deployJob=true
uv run --no-project python fabric-demos/04-real-time-ingestion/scripts/publish_live_test.py dashboard
uv run --no-project python fabric-demos/04-real-time-ingestion/scripts/publish_live_test.py notebook
```

Execute the additive KQL setup script against the existing database using the Kusto management
endpoint, not the database item-definition importer. The publisher targets this deployment's
workspace, folder, and database IDs; it does not provision a new Fabric workspace.
The Eventstream connection was configured in Fabric UI: Azure Event Hubs, workspace identity,
consumer group `fabric-live-test`, JSON, then connect the default stream to the Eventhouse
destination and Publish. Its exported definition is a record of the working connection,
not a portable credential or standalone connection provisioning template.

NotebookUtils does not support the ARM token audience. A Key Vault-backed launcher was tested
but blocked by enforced private-network policy; its unused resources were removed without a
policy exception. The selected launcher instead uses interactive MSAL device-code authentication.
Spark startup and Container Apps cold starts add launch delay. Stop the Spark session after use.
The producer has no always-running replica; ACR storage, Event Hubs, Fabric capacity, and related
retention still incur costs while no flight is active.

Verification on 2026-09-15: a full bounded job succeeded; live records, a map marker, and all
three channel charts were observed in Fabric. The exact launcher control function started a
second Azure execution using CLI authentication. That complete flight retained exactly 18,000
TSPI, 1,800 temperature, and 900 error-word events; both jobs ended `Succeeded`.
Notebook export confirms device-code authentication. All six focused tests pass:
`uv run --no-project --with msal --with requests python -m unittest discover -s tests -p test_live_test.py -v`.
The revised notebook's interactive user sign-in still requires an end-user check.

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
