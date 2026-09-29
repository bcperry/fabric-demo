# Multicast Implementation Blueprint

This is the single code-and-packaging map for the work. All new filenames,
interfaces, and templates below are **proposed, not implemented or deployable
yet**. The [producer TODOs](multicast_producers/TODO.md) and
[consumer TODOs](multicast_consumers/TODO.md) retain the detailed requirements
and acceptance criteria. Implement both generators, starting with the standalone
target generator. Do not change the existing direct-to-Kafka defaults.

```text
Target generator   -> multicast group A --+
                                        +-> durable bridge -> Event Hubs (Kafka)
Scenario generator -> multicast group B --+   -> Eventstream -> Lakehouse Delta
```

## Files to Land

Paths in this tree are relative to this folder. Existing TODOs and swXtch
bootstrap manifests remain; the application manifests below are new.

```text
multicast_producers/
  producer.py                 CLI, generator adapters, pacing, UDP sender
  profiles.json               Approved target/scenario settings and profile IDs
  Dockerfile                  One image used by both generator deployments
  deployment.yaml             Two Deployments, one instance per generator
  tests/test_producer.py       Profile, datagram, pacing, compatibility tests
multicast_consumers/
  consumer.py                 Receive/validate loop, health, worker orchestration
  spool.py                    SQLite capture journal, replay, retention
  kafka_sink.py               Serialized-record Kafka sender and delivery callbacks
  Dockerfile                  Bridge image with Kafka and identity dependencies
  deployment.yaml             ServiceAccount, PVC, single-active Deployment
  tests/test_consumer.py       Capture/replay, failure, Kafka, duplicate tests
```

Shared changes outside those folders:

- Add `src/mda_emulators/multicast_protocol.py` to the existing Python package:
  wire version/schema, encode/decode, byte limits, stream identity, and validation.
  Both applications import it; do not maintain two copies of the wire contract.
- Extend [TargetVehicle](../src/mda_emulators/target_vehicle.py) with optional
  temperature-range and position-noise parameters whose defaults preserve current
  behavior. Keep synthetic signal generation there, not in a copied generator.
- Add narrowly scoped regression coverage in
  [test_target_vehicle.py](../tests/test_target_vehicle.py) and reuse the existing
  [engine tests](../tests/test_engine.py) for compatibility checks.
- Reuse [pyproject.toml](../pyproject.toml) and its lockfile for both images.
  Do not introduce a second package/dependency project in each folder.

## Packages to Use

| Purpose | Package/API | Use |
| --- | --- | --- |
| Signal generation | Existing `mda_emulators` package | `TargetVehicle`, `ScenarioEngine`, scenario loading |
| UDP multicast | Python `socket`, `selectors` | Outbound interface/group/TTL; join and drain both receive sockets |
| JSON, time, shutdown | Python `json`, `time`, `datetime`, `uuid`, `signal`, `threading` | Compact UTF-8 datagrams, monotonic pacing, IDs, bounded workers |
| Contract validation | `jsonschema` via existing `validation` extra | Versioned wire and original payload validation |
| Durable spool | Python `sqlite3` | Transactions, WAL, full synchronous commits, delivery state |
| Event Hubs Kafka | `confluent-kafka` via existing `kafka` extra | Producer, OAuth callback, delivery callbacks, bounded flush |
| Authentication | `azure-identity` via existing `kafka` extra | `DefaultAzureCredential`, Kubernetes workload identity |
| Health endpoint/tests | Python `http.server`, `unittest`, `unittest.mock` | No web framework required |

Use uv, not direct pip commands. The producer needs only the `validation` extra;
the consumer needs `validation` and `kafka`. swXtch/xNIC is a vendor networking
dependency, not a substitute for any of the application code above.

## Producer Code

`producer.py` exposes `--generator target|scenario`, `--profiles`, `--loop`, and
configuration for interface, group, port, TTL, maximum datagram bytes, and manifest
output. Read deployment defaults from environment variables with CLI overrides.
Both network modes are paced; no unrestricted `--fast` multicast mode.

### Target Adapter

Use [TargetVehicle.events()](../src/mda_emulators/target_vehicle.py), which already
yields `(elapsed_seconds, event)`. Follow that file's `main()` for run IDs,
monotonic scheduling, stop signals, and the `{topic, key, event}` wrapper.

1. Read `multicast-target-v1` from `profiles.json`: seed `20260929`, duration 600
   seconds, rates `{tspi: 10, temperature: 1, error: 0.5}`, temperature baseline
   22-34 C, and position-noise standard deviation 12 m.
2. Construct the existing generator using its proposed optional profile
   parameters. Today temperature and position noise are hardcoded, so changing
   CLI rates alone does **not** implement this profile.
3. Create a fresh run UUID and multicast-specific vehicle ID. For each event,
   wait until its monotonic deadline, wrap it, add transport metadata, and send
   one datagram. Keep existing route and other unlisted model settings unchanged.
4. Emit startup and completion manifests. A complete half-open 600-second run
   contains 6,900 records before transport loss. Looping starts a fresh run;
   record any seed progression explicitly, as the existing standalone CLI does.

### Scenario Adapter

Use [load_scenario()](../src/mda_emulators/scenario.py),
[ScenarioEngine](../src/mda_emulators/engine.py), and the generator iteration in
[cli.py](../src/mda_emulators/cli.py). Use
[scenario.integrated-defense.json](../../01-contracts/examples/scenario.integrated-defense.json)
as the base, without modifying it.

1. Load `multicast-scenario-v1` overrides from `profiles.json`: seed `20260930`,
   time scale 5, clock-delay anomaly at second 60 for 15 seconds. Retain the
   existing configurable 180-second scenario duration default.
2. Apply overrides to a separate in-memory configuration **before** fictional
   locations are assigned. The existing loader assigns locations immediately;
   add an optional overrides argument with backward-compatible defaults so seed
   changes affect those locations. Validate the resulting scenario normally.
3. Assign multicast-specific scenario/source IDs and update all references,
   including anomaly targets. Supply a fresh run ID to `ScenarioEngine`.
4. Iterate `engine.generate(duration_seconds)`. Preserve the event and
   `ordering_key` as the record key; stamp actual source publication time once.
   Use monotonic deadlines respecting scenario time scale, not a Kafka loop or
   unpaced generation. Document simulated versus wall-clock duration.

### Example Datagram

Illustrative target position record, with a sample UUID/value set. The shared
protocol module will validate this format. A scenario record uses its own
original event schema inside the same wrapper.

```json
{
  "topic": "target-vehicle-telemetry",
  "key": "mc-target-01",
  "event": {
    "schema_version": "target-vehicle.v1",
    "synthetic": true,
    "run_id": "11111111-1111-4111-8111-111111111111",
    "vehicle_id": "mc-target-01",
    "event_id": "11111111-1111-4111-8111-111111111111:1",
    "sequence_number": 1,
    "channel": "tspi",
    "event_time_utc": "2026-09-29T12:00:00Z",
    "elapsed_seconds": 0.0,
    "startup_seed": 20260929,
    "data": {"latitude_deg": 10.2, "longitude_deg": -164.8, "altitude_m": 20001.0}
  },
  "multicast": {
    "wire_version": "multicast.v1",
    "generator_kind": "target",
    "profile_id": "multicast-target-v1",
    "source_id": "mc-target-01",
    "run_id": "11111111-1111-4111-8111-111111111111",
    "stream_id": "mc-target-01",
    "sequence_number": 1,
    "group": "239.0.0.10",
    "port": 8410,
    "sent_time_utc": "2026-09-29T12:00:00.001Z"
  }
}
```

The displayed group is an example, not a reserved deployment assignment. Use a
different group for scenario data. Sequence numbers belong to a producer/run/
stream and are independent of original event numbering. Measure both generators'
largest records and validate MTU limits before choosing `MC_MAX_DATAGRAM_BYTES`.

## Consumer Code

`consumer.py` joins the configured groups and coordinates two bounded stages:
receive/commit and pending-record publication. It serves `/live` and `/ready` on
port 8080 and reports receive, spool, and Kafka health separately.

`spool.py` stores raw bytes and receipt information in a SQLite database on the
PVC. Enable WAL and `synchronous=FULL`; verify filesystem support and crash
behavior. Persist capture ID, source identity, receipt time, validation state,
outgoing JSON, attempt history, and acknowledgment time. Keep the schema and
transactions small; use worker-owned connections and bounded lock waits.

```text
Receive bytes -> commit raw capture -> validate/version check
  -> quarantine invalid capture, or prepare outgoing record
  -> persist bridge metadata and serialized outgoing bytes
  -> Kafka produce -> delivery callback -> commit acknowledgment
```

`kafka_sink.py` follows
[KafkaSink](../src/mda_emulators/target_vehicle.py) for `confluent_kafka.Producer`,
OAuth, and delivery callbacks. Also reference
[KafkaTransport](../src/mda_emulators/transports.py) for the Event Hubs token scope.
Neither current interface is a drop-in durable bridge: expose a callback tied
to a capture ID. Do not call a wrapper that restamps the source event.

- Send the record to the configured physical `EVENTHUB_NAME`; keep the logical
  `topic` in JSON and the original key as the Kafka partition key.
- Add `bridge` metadata outside `event`: capture ID, bridge ID, receipt time,
  first-forward-attempt time. Preserve these on retries of the same capture.
- Forward repeated events; different captures can have the same event ID.
  Kafka enqueue is not acknowledgment. Replay unacknowledged records after
  crashes, including the ambiguous broker-accepted/local-uncommitted window.
- Enforce the approved 10 GiB budget, 24-hour acknowledged retention, and no
  automatic deletion of pending captures. Account for WAL/compaction overhead.
  Full storage stops acceptance, fails readiness, and alerts; UDP can then drop.
- Report gaps/duplicates/reordering without claiming packet recovery. A Kafka
  outage leaves the live capture process running while durable capacity remains.

## Dockerfiles

Use `shared/integrated-test-data` as the build context, as required by the
[existing emulator Dockerfile](../Dockerfile). Use the uv approach from
[Dockerfile.target-vehicle](../Dockerfile.target-vehicle), but install from the
shared lockfile instead of independently resolving dependency versions.

Proposed **producer Dockerfile**:

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/emulators
COPY 02-emulators/pyproject.toml 02-emulators/uv.lock ./
COPY 02-emulators/src ./src
COPY 02-emulators/multicast ./multicast
COPY 01-contracts /app/contracts
RUN uv sync --frozen --no-dev --extra validation --no-editable
USER 65532:65532
ENTRYPOINT ["/app/emulators/.venv/bin/python", "multicast/multicast_producers/producer.py"]
CMD ["--generator", "target", "--profiles", "multicast/multicast_producers/profiles.json", "--loop"]
```

For the **consumer Dockerfile**, use the same base/copy structure, add
`--extra kafka` to `uv sync`, replace the entrypoint script with
`multicast/multicast_consumers/consumer.py`, and set `CMD []`. Keep approved
dependency versions in the shared lockfile. Pin final image digests when building
the deployable images; validate the base image against xNIC compatibility.

These templates cover application images/native multicast only. Verify and
incorporate the vendor-supported xNIC installation and process-launch method
before deploying on swXtch. Do not invent a preload path or assume a sidecar
automatically intercepts another container's sockets. Configure writable run
manifest storage for producers and writable PVC access for the consumer.

After implementation, build from `shared/integrated-test-data`:

```bash
docker build -f 02-emulators/multicast/multicast_producers/Dockerfile -t multicast-producer:dev .
docker build -f 02-emulators/multicast/multicast_consumers/Dockerfile -t multicast-bridge:dev .
```

## Kubernetes Manifests

`multicast_producers/deployment.yaml` contains **two Deployments** using the same
producer image. Configure `--generator target` versus `--generator scenario`,
distinct multicast groups/source IDs, profiles path, and a writable manifest
volume. Both run one replica and use a non-overlapping rollout strategy.

Proposed application-container fragment for the target Deployment; these env
names are interfaces to implement, not settings already consumed by Python:

```yaml
containers:
  - name: producer
    image: <registry>/multicast-producer:<version>
    args: ["--generator", "target", "--profiles", "/app/emulators/multicast/multicast_producers/profiles.json", "--loop"]
    env:
      - {name: MC_GROUP, value: "239.0.0.10"}
      - {name: MC_PORT, value: "8410"}
      - {name: MC_INTERFACE, value: "eth0"}
      - {name: MC_TTL, value: "1"}
      - {name: SOURCE_ID, value: "mc-target-01"}
      - {name: SCENARIO_PATH, value: "/app/contracts/examples/scenario.integrated-defense.json"}
      - {name: MANIFEST_DIRECTORY, value: "/var/run/multicast"}
    volumeMounts:
      - {name: manifests, mountPath: /var/run/multicast}
```

Define the referenced volume in the complete manifest; export run manifests as
acceptance evidence before pod cleanup. Give the scenario Deployment a separate
group and identity. Set a measured datagram limit explicitly in both deployments.

`multicast_consumers/deployment.yaml` contains these resources:

| Resource | Required configuration |
| --- | --- |
| ServiceAccount | Entra client-ID annotation and preconfigured federated identity |
| PVC | 10 GiB, appropriate persistent storage class, verified UID/GID access |
| Deployment | One replica, `strategy: Recreate`, workload-identity pod label, bridge image, named ServiceAccount |
| Container | PVC at `/var/lib/multicast`, `/live` and `/ready` HTTP probes on 8080, graceful termination |

Proposed bridge container environment fragment:

```yaml
env:
  - name: MC_SUBSCRIPTIONS_JSON
    value: '[{"group":"239.0.0.10","port":8410,"generator":"target"},{"group":"239.0.0.11","port":8410,"generator":"scenario"}]'
  - {name: MC_INTERFACE, value: "eth0"}
  - {name: SPOOL_PATH, value: "/var/lib/multicast/capture.sqlite3"}
  - {name: ACK_RETENTION_HOURS, value: "24"}
  - {name: KAFKA_BOOTSTRAP_SERVERS, value: "<namespace>.servicebus.windows.net:9093"}
  - {name: EVENTHUB_NAME, value: "<dedicated-shared-multicast-hub>"}
```

Specify safe journal headroom below the PVC's usable space. Explicitly validate
multiple group reception on the shared port: use per-socket membership isolation
or group-aware receive metadata, avoiding OS defaults that deliver both groups
to both sockets. Filter/verify generator identity against its subscribed group.

Use the existing [producer](swXtch_producer.yaml) and
[consumer](swXtch_consumer.yaml) manifests only as xNIC bootstrap references.
The final manifests must incorporate the verified vendor startup, control address,
required privileges, and cross-node placement, not launch an installer and sleep.
Restrict application privileges when vendor integration permits. Add workload
identity federation and Event Hubs Data Sender role assignment outside the pod
manifest; never embed credentials. Readiness must not restart the bridge simply
because Event Hubs is temporarily unavailable.

## Landing and Verification Order

1. Land shared protocol/schema fixtures, profile parameters, and target adapter;
   verify original generator tests still pass and all 6,900 target records fit
   the datagram limit. Wire manifests/CLI env names consistently.
2. Land the native UDP receiver, SQLite journal, and callback-aware Kafka sink.
   Test malformed packets, duplicates, reordering, crash/replay, and disk limits.
3. Add the scenario adapter and test both streams simultaneously, including
   multicast group isolation and unchanged direct-to-Kafka behavior.
4. Build both images; verify swXtch integration across nodes and restart with the
   same PVC. Reconcile emitted, captured, committed, and acknowledged records.
5. Configure the dedicated Event Hub and Eventstream-to-Lakehouse path. Retain
   raw duplicates and produce separate curated target/scenario tables or views,
   deduplicated by generator/source/run/original-event ID. Verify replay leaves
   unique results stable and preserve both datasets' multicast provenance.

Run the new folder tests with `uv run --extra validation --extra kafka python -m
unittest discover -s <folder>/tests -v` from the emulator project directory,
plus the existing emulator suite. Use a controlled native multicast smoke test,
then separate Kubernetes/swXtch, Event Hubs, and Fabric acceptance runs. A passed
local test is not evidence that a cloud integration works.