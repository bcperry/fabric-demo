# Multicast Consumers TODO

## Agreed Scope

Planning only: this document does not implement applications or deploy resources.
Build one active multicast receiver/bridge that accepts both generator streams,
durably captures received data, and publishes directly to Event Hubs using its
Kafka endpoint. There is no intermediate Kafka broker in the deployed design.

Use one new dedicated Event Hub shared by the two multicast datasets, separate
from existing direct-to-Kafka destinations. Complete the path through Fabric
Eventstream into Lakehouse Delta tables, retaining raw records and exposing
deduplicated results. Eventhouse/KQL is not the selected destination.

The [Multicast Producers TODO](../multicast_producers/TODO.md) owns the approved
profiles and shared wire contract. Both the standalone target-vehicle generator
and the scenario emulator are required; implement the standalone path first.

## Receive and Validate

- [ ] Join two configurable UDP multicast groups, one per generator, using the
  correct interface and vendor-supported xNIC process integration. Support native
  Linux multicast for local tests without assuming that proves swXtch operation.
- [ ] Capture original datagram bytes and receipt metadata before transformation.
  Preserve the producer's `topic`, `key`, `event`, original IDs/timestamps, and
  multicast provenance. Validate the agreed wire version and generator schema.
- [ ] Record a unique capture ID, bridge instance ID, group/port, and
  `received_time_utc` outside the original event. A repeated UDP datagram is a
  distinct capture with the same original event identity.
- [ ] Separate receive/spool work from Kafka publication with bounded resources.
  Specify socket buffer sizing, queue limits, and measurable overflow behavior;
  a Kafka outage must not block reception while spool capacity remains available.
- [ ] Detect malformed records, unsupported versions, oversized/truncated
  datagrams, unexpected sources, and invalid keys. Persist bounded quarantine
  evidence within the storage budget; do not send invalid records to the main hub.
- [ ] Track sequence gaps, duplicates, and out-of-order arrival per producer/run/
  stream. Use a bounded reordering window before declaring gaps and reconcile
  against producer manifests for head/tail loss. Do not claim missing packets
  were recovered or invent replacement events.

## Durable Capture and Retry

Approved initial policy: a configurable **10 GiB** persistent spool; retain
Kafka-acknowledged captures for **24 hours after acknowledgment**. Never
automatically delete unacknowledged captures. This is a storage budget, not a
guaranteed outage-duration commitment.

- [ ] Implement a persistent journal with atomic capture and delivery-state
  updates, using an established durable storage mechanism. Define flush/fsync,
  crash recovery, record checksums, disk overhead, and compaction behavior.
- [ ] Make durable commit the capture guarantee boundary: datagrams in the kernel
  or process memory can still be lost on a crash. Never advertise exactly-once
  capture or lossless UDP delivery.
- [ ] Use a Kubernetes persistent volume that survives bridge pod replacement.
  Confirm the storage class, capacity, permissions, reclaim policy, and restart
  recovery before claiming durability. Include journal/quarantine/temporary
  storage in the capacity budget.
- [ ] Recover pending records on startup and retry after Kafka failures with
  bounded per-attempt timeouts and capped exponential backoff with jitter.
  Retain pending records for subsequent attempts; retry exhaustion must never
  mark a record delivered or silently discard it.
- [ ] Advance a record to acknowledged only after its Kafka delivery callback
  confirms success. A successful enqueue or poll is not an acknowledgment.
- [ ] Preserve event identity on replay and persist outgoing record metadata so
  retries of a capture are traceable. Track attempt times/counts and broker
  acknowledgment time in the journal. A crash after broker acceptance but before
  local acknowledgment can create duplicates; this is expected.
- [ ] Add a distinct `first_forward_attempt_time_utc` outside the original event;
  never relabel source publication time as bridge receipt or forwarding time.
  Keep subsequent attempt history in the journal, not by mutating source data.
- [ ] Enforce the 24-hour acknowledged-record retention policy and expose disk
  high-water alerts. On exhaustion, stop accepting traffic, fail readiness, and
  alert; do not evict pending data or younger acknowledged captures to hide the
  problem. Document that multicast packets sent during this stop can be lost.
- [ ] Provide capture inspection, pending/acknowledged/quarantine counts, controlled
  pending replay, and documented storage recovery operations. Do not log secrets.

## Event Hubs Kafka Publication

- [ ] Reuse compatible behavior from
  [KafkaSink](../../src/mda_emulators/target_vehicle.py) and
  [KafkaTransport](../../src/mda_emulators/transports.py), using a small shared
  adapter only where needed. Preserve existing direct-publisher behavior.
- [ ] Resolve the two existing Kafka call contracts explicitly: the standalone
  sink accepts an already serialized record, while KafkaTransport builds a
  wrapper and stamps publication time. The bridge must not double-wrap records
  or replace the source's original publication timestamp.
- [ ] Send both datasets to a single configurable physical Event Hub/topic.
  Keep each original logical topic in the JSON record and preserve the original
  Kafka key. Do not use untrusted incoming topics to choose arbitrary destinations.
- [ ] Use Entra workload identity/DefaultAzureCredential, TLS, the namespace token
  scope, and least-privilege Azure Event Hubs Data Sender access. Do not introduce
  shared-access keys or connection strings. Validate token renewal and permissions.
- [ ] Enable supported Kafka idempotent-producer settings and delivery callbacks.
  Handle queue saturation, disconnects, authentication failures, and shutdown
  without losing pending journal state. Idempotence does not remove duplicate
  captures or guarantee duplicate-free replay across restarts.
- [ ] Forward repeated valid events with their original stable identities. Do
  not suppress duplicates in the bridge. Best-effort arrival/replay order is not
  source event-time order; downstream consumers must use IDs and timestamps.
- [ ] Measure input/output rate, datagram size, and spool growth for both profiles;
  size Event Hub partitions/capacity and storage headroom from measurements.
  Document drain behavior while new live traffic is arriving.

## Kubernetes and swXtch Setup

- [ ] Coordinate swXtch installation/licensing, supported networking, xNIC launch
  integration, group/interface configuration, and cross-node checks with the
  producer plan. Do not treat the existing installer-only manifest as a bridge.
- [ ] Evolve [swXtch_consumer.yaml](../swXtch_consumer.yaml) into a reproducible
  receiver deployment with explicit application startup, persistent storage,
  configuration, workload identity, and health endpoints. Verify the vendor
  installer does not occupy the application receive ports with a test consumer.
- [ ] Enforce one active forwarder, including during rollout; replicas=1 alone
  does not prevent rolling-update overlap. Use an appropriate non-overlapping
  rollout strategy and persistent-volume ownership. Redundant active bridges
  are outside the initial scope.
- [ ] Verify required privileges, node placement, receive-buffer limits, control/
  data network policies, DNS, and outbound access to identity and Event Hubs.
- [ ] Distinguish liveness from readiness so a broker outage does not cause a
  restart loop or erase capture state. Report multicast, spool, and Kafka health
  separately; alert on silent streams and growing delivery backlog.
- [ ] Document uv-based local development and tests, image build/deploy commands,
  swXtch verification, operational logs, restart recovery, and cleanup. Use
  configurable placeholders for cluster, namespace, resource, and image names.

## Fabric Lakehouse Integration

- [ ] Provision/configure the dedicated shared Event Hub and a Fabric consumer
  group/checkpoint path isolated from the existing direct-producer demo.
- [ ] Create or configure Fabric Eventstream to ingest that hub into raw Lakehouse
  Delta storage. Verify supported connector authentication and permissions;
  use Entra authentication without silently substituting shared keys. If the
  selected connector cannot support it, treat that as an explicit design blocker.
- [ ] Preserve raw repeated records, original event payloads, logical topic/key,
  generator/profile/source/run identity, capture ID, and transport timestamps.
  Configure explicit mappings so the two payload schemas can coexist without
  dropping fields or confusing physical and logical topic names.
- [ ] Create separate curated Delta tables or query views for the target and
  scenario datasets, deduplicating by generator kind, source ID, run ID, and
  original event ID. Keep the raw table append-only for inspection.
- [ ] Make deduplication deterministic and idempotent under replay, late arrival,
  repeated Eventstream ingestion, and repeated curation runs. Preserve valid
  events whose IDs differ, even when payloads or timestamps match.
- [ ] Supply queries comparing raw and unique counts, source sequence gaps,
  profile/channel distribution, and send-to-receive/receive-to-forward/Fabric
  arrival latency. Check clock synchronization before interpreting latency.
- [ ] Demonstrate distinct approved signal profiles and multicast provenance in
  both datasets without mixing them with the original direct-to-Kafka stream.

## Acceptance Tests

- [ ] Unit-test both wire schemas, exact source payload/ID preservation, topic/key
  mapping, byte limits, malformed quarantine, gap/reordering logic, and forwarding
  of duplicates with separate capture IDs and stable original event IDs.
- [ ] Test durable capture and pending replay across process crashes, pod
  replacement, queue saturation, disk exhaustion, and the crash window between
  Kafka acceptance and local acknowledgment. Assert no premature acknowledgment.
- [ ] Block Event Hubs temporarily while both producers run. Confirm committed
  captures persist, backlog grows within the budget, and all valid committed
  records are acknowledged after recovery; distinguish UDP loss before commit.
- [ ] Inject multicast loss, duplicate packets, and reordering in an isolated
  test. Verify diagnostics, no claimed recovery, raw duplicate retention, and
  correct deduplicated Lakehouse results.
- [ ] Test pending-record protection and 24-hour acknowledged retention, including
  quarantine/storage overhead and recovery from a full volume. Do not delete
  existing application evidence merely to make a test pass.
- [ ] Run both real generators concurrently across Kubernetes nodes through
  swXtch, the bridge, the dedicated shared Event Hub, Eventstream, and Lakehouse.
  Use manifests to reconcile generated, received, committed, acknowledged, raw,
  and unique counts. Require complete agreement for a controlled no-loss run;
  explicitly account for injected losses/duplicates in fault runs.
- [ ] Verify no duplicate capture is suppressed at the bridge and no original
  event is duplicated in the curated result. Repeat replay/curation to prove
  stable results rather than assuming Kafka idempotence is sufficient.
- [ ] Retain test commands, manifests, capture IDs, metrics, queries, and evidence
  of both profiles in Fabric. Mark local/native multicast, swXtch, Event Hubs,
  and Fabric checks independently; do not label unexecuted cloud tests as passed.