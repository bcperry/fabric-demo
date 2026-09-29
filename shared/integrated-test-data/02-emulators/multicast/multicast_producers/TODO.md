# Multicast Producers TODO

## Agreed Scope

Planning only: this document does not implement applications or deploy resources.
Both existing generators must work over multicast. Start with the standalone
target-vehicle generator, then integrate the multi-source scenario emulator.
Neither integration is optional. Leave existing direct-to-Kafka behavior,
profiles, event schemas, and defaults unchanged.

```text
Two synthetic generators -> two UDP multicast groups -> swXtch/xNIC
  -> one active durable bridge -> one dedicated shared Event Hub (Kafka)
  -> Fabric Eventstream -> Lakehouse Delta tables
```

The initial deployment has one instance of each generator. Applications generate
the data; swXtch/xNIC supplies multicast transport. Application code may run in
the same pods as xNIC. Do not assume the vendor PERF_TYPE/PERF_PPS settings run
our generators or that installing xNIC automatically integrates arbitrary apps.

The counterpart plan is [Multicast Consumers TODO](../multicast_consumers/TODO.md).

## Approved Synthetic Profiles

All values below are configurable starting defaults, not validated physical
models. Preserve channel meanings, payload field names, units, and synthetic
markings. Do not add tactical logic or claim performance-model fidelity.

| Setting | Standalone generator | Scenario emulator |
| --- | --- | --- |
| Profile ID | `multicast-target-v1` | `multicast-scenario-v1` |
| Seed | `20260929` | `20260930` |
| Duration | 600 simulated seconds per run | Retain the existing scenario duration setting |
| Position / temperature / error rates | 10 / 1 / 0.5 Hz | Retain existing channel rates |
| Temperature baseline | 22-34 C | Retain existing scenario behavior |
| Position noise | 12 m standard deviation per axis | Retain existing scenario behavior |
| Scenario time scale | Not applicable | 5 instead of 10 |
| Clock-delay anomaly | Not applicable | Start at simulated second 60, last 15 seconds instead of 90/30 |

- [ ] Add explicitly selected alternate profiles using the defaults above. Keep
  unlisted standalone route, temperature-noise, and error-process settings at
  their existing values; keep unlisted scenario settings unchanged.
- [ ] Give both datasets multicast-specific source identities, independent seeds,
  fresh run IDs, and explicit profile IDs. Update scenario identity references
  consistently, including anomaly targets and any source/site relationships.
- [ ] Record effective configuration and seed in a startup/run manifest. Support
  explicit seed overrides for reproducible signal values without reusing run IDs
  accidentally. Deliberate replay must preserve the original identities.
- [ ] Define scenario time-scale semantics in tests: distinguish simulated time,
  wall-clock pacing, and actual send timestamps. Pace network publication in real
  time; prohibit an unbounded fast-output mode from flooding multicast.

## Shared Wire Contract

This section owns the producer/bridge contract. Finalize its schema and shared
fixtures before implementing either side; the consumer plan must use the same
version, identity rules, and size limits.

- [ ] Encode one UTF-8 JSON record per UDP datagram. Preserve the existing
  `topic`, `key`, and `event` structure. Add a versioned multicast metadata object
  outside `event`; never change the original logical topic into the physical
  Event Hub name. Do not double-encode JSON or batch records into one datagram.
- [ ] Specify metadata fields for wire version, generator kind, profile ID,
  source ID, run ID, stream ID, monotonically increasing stream sequence,
  multicast group/port, and actual `sent_time_utc`.
- [ ] Define stream sequence scope as producer instance plus run plus stream.
  Generate it at the transport boundary: filtering or generator-specific event
  numbering must not create false network-loss reports. Preserve the event's
  original ID, sequence, source time, and publication time independently.
- [ ] Define the stable deduplication identity as generator kind, source ID,
  run ID, and original event ID; document mappings from each existing event
  schema. Preserve original record keys for downstream Kafka partitioning.
- [ ] Measure the largest records from both generators, including metadata, and
  set a shared configurable byte limit based on verified network MTU and xNIC
  overhead. Validate both profiles fit. Reject and report oversized records;
  never truncate or introduce application fragmentation without revisiting the
  contract. Detect receiver truncation as a separate error.
- [ ] Provide valid fixtures for both generators plus unsupported-version,
  malformed, oversized, repeated, out-of-order, and missing-sequence cases.

## Generator Implementation

- [ ] Reuse [target_vehicle.py](../../src/mda_emulators/target_vehicle.py) generation
  logic and [the scenario engine](../../src/mda_emulators/engine.py), avoiding
  copied implementations that drift. Introduce only the profile/transport
  extension points needed by both paths.
- [ ] Add explicit multicast output selection; retain existing file/stdout/Kafka
  modes and their defaults. Multicast producers must not also publish directly
  to Event Hubs or require Kafka credentials.
- [ ] Implement standard UDP multicast sending with configurable group, port,
  outbound interface, TTL, record limit, and pacing. Use a separate group for
  each generator; group addresses and ports are deployment configuration.
- [ ] Keep application networking separate from the documented xNIC launch
  integration so native Linux multicast tests can run without swXtch.
- [ ] Support clean shutdown, socket cleanup, structured error reporting, and
  counters for generated records, sent datagrams/bytes, oversize rejection, and
  send errors. A successful UDP send is not proof of receiver delivery.
- [ ] Persist a run summary/manifest sufficient to compare expected counts with
  bridge observations, including loss at the beginning or end of a run that
  sequence gaps alone cannot reveal. No sender-side recovery protocol is in scope.

## Kubernetes and swXtch Setup

- [ ] Establish swXtch installation, licensing, supported Kubernetes networking,
  and control-address reachability as prerequisites. Resource names, namespace,
  image registry, groups, and ports remain configurable placeholders.
- [ ] Inspect the vendor installer and supported xNIC application-launch method.
  Verify how our process is attached to xNIC and whether vendor performance
  traffic starts automatically; disable unrelated test traffic or isolate it.
- [ ] Replace the bootstrap-only behavior in
  [swXtch_producer.yaml](../swXtch_producer.yaml) with packaging that runs the
  actual generators. Use reproducible application images and explicit startup
  failures, not runtime package installation followed by an idle container.
- [ ] Document required xNIC privileges and restrict application privileges where
  supported. Verify installer provenance; avoid silently trusting an unauthenticated
  HTTP download. Coordinate control/data ports, policies, interfaces, and node
  placement with the consumer plan.
- [ ] Provide Kubernetes configuration for both generator instances and a
  receiver on a different node. Verify sufficient schedulable nodes and actual
  cross-node traffic; readiness must distinguish xNIC from application health.
- [ ] Document uv-based development, container build, local multicast smoke test,
  Kubernetes deployment, start/stop, logs, and cleanup commands. No deployment
  occurs while writing these TODOs.

## Acceptance and Handoff

- [ ] Test each alternate profile for reproducibility, distinct signal/timing
  behavior, valid original payload schemas, unique run/source identities, and
  unchanged direct-to-Kafka regression tests.
- [ ] For the standalone 600-second half-open run, verify 6,000 position, 600
  temperature, and 300 error records: 6,900 total before transport loss. Derive
  and assert scenario counts from its configured duration/time-scale semantics.
- [ ] Validate datagrams against the shared schema and size limit, and compare
  decoded payloads with the generator's pre-transport records.
- [ ] Demonstrate both profiles simultaneously through real cross-node swXtch,
  with no vendor test packets mistaken for application records.
- [ ] Hand off expected IDs/counts and manifests to the consumer acceptance tests.
  Completion requires both datasets in the dedicated Event Hub and the Fabric
  Lakehouse, not only successful local UDP sends.

## Delivery Order

1. Finalize contract, profile fixtures, and swXtch prerequisites with the consumer.
2. Prove standalone generation through multicast and the durable Kafka bridge.
3. Bring the scenario emulator through the same contract and bridge.
4. Run both together; complete outage/restart, loss, and Fabric acceptance tests.