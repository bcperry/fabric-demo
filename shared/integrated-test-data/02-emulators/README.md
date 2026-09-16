# Synthetic Emulator Runtime

This package generates the deterministic observed-test stream for the capstone:
TPY-2, Patriot, THAAD, integration, sustainment, target/interceptor telemetry,
instrumentation, optical confirmation, ground truth, environment, readiness,
network, operator, and advisory safety evidence from the versioned scenario in
`../01-contracts`.

The default transport is local JSON Lines. It performs no network operations.
Kafka mode must be selected explicitly and authenticates with Microsoft Entra
OAuth through `DefaultAzureCredential`.

## Run locally

```bash
cd shared/integrated-test-data/02-emulators
uv sync

uv run mda-emulator \
  --scenario ../01-contracts/examples/scenario.integrated-defense.json \
  --duration-seconds 180 \
  --manifest-output demo-manifest.json \
  --transport file \
  --output demo-events.jsonl
```

## Run tests

```bash
uv run python -m unittest discover -s tests -v
```

## Build containers

Both commands must run from `shared/integrated-test-data` because the image includes
`01-contracts` and `02-emulators`:

```bash
# Offline/local JSONL image
docker build -f 02-emulators/Dockerfile -t mda-demo-emulators:local .

# Kafka/OAuth image; downloads the two optional runtime packages
docker build \
  --build-arg INSTALL_KAFKA=true \
  -f 02-emulators/Dockerfile \
  -t mda-demo-emulators:0.1.0 .
```

## Kafka mode

Install optional dependencies without using the shell's configured private
index as project metadata:

```bash
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv sync --extra kafka
```

Then provide the Event Hubs Kafka endpoint and workload identity client ID:

```bash
uv run mda-emulator \
  --scenario ../01-contracts/examples/scenario.integrated-defense.json \
  --transport kafka \
  --bootstrap-servers "<namespace>.servicebus.windows.net:9093" \
  --managed-identity-client-id "<client-id>" \
  --realtime
```

Topics are mapped to the Event Hubs created by `00-infrastructure`:

- `sensor-observation`
- `system-status`
- `command-integration`
- `sustainment`
- `target-telemetry`
- `interceptor-telemetry`
- `instrumentation-observation`
- `ground-truth-observation`
- `environment-observation`
- `instrumentation-health`
- `network-health`
- `readiness-poll`
- `operator-test-event`
- `safety-status`

The `--manifest-output` file persists startup seeds, stable source identities,
site locations, roles, and the topic inventory for deterministic replay.

The runtime never accepts a connection string or shared-access key.

## Standalone stochastic target vehicle

[target_vehicle.py](src/mda_emulators/target_vehicle.py) is an independent,
single-file producer. It does not change the deterministic scenario engine or
claim conformance with its event contracts. Its default output is JSONL; Kafka
is opt-in. These are synthetic visualization signals, not validated flight
dynamics, aerodynamic predictions, or a reentry heating model.

Defaults are a 900-second, roughly 1,260-mile Pacific arc from approximately
10 N, 165 W to 18 N, 148 W. A smooth altitude curve rises from 20 km to a
randomized 90-110 km peak and returns to 20 km. This is an airborne segment,
not a launch-to-impact simulation. The curve implies high-speed motion but
does not integrate vehicle physics. `--duration` time-scales the whole curve.

Each flight draws independent uniform geographic offsets (+/- 0.5 degrees)
and peak height. Position noise is a stationary Ornstein-Uhlenbeck process
(8 m standard deviation per axis, 2 s correlation time), so adjacent samples
are correlated instead of independently jittering. This is synthetic measured
position, not a force driving the path. Separate random streams keep TSPI
unchanged when internal channel rates change.

| Channel | Default Rate | `data` Fields |
| --- | --- | --- |
| `tspi` | 20 Hz | `latitude_deg`, `longitude_deg`, `altitude_m` |
| `temperature` | 2 Hz | `temperature_c` |
| `error` | 1 Hz | `error_word` |

Coordinates use geodetic degrees and synthetic ellipsoidal height in metres.
Temperature is an internal sensor with a smooth 30-48 C baseline and correlated
Gaussian noise (0.6 C standard deviation, 8 s correlation time). The unsigned
16-bit error word uses only bits 0-3 as generic diagnostic flags; bits 4-15 are
reserved and zero. Each flag follows an independent continuous-time two-state
Markov chain, sampled with the exact transition probability: clear-to-set rate
0.002/s, set-to-clear rate 0.2/s. Stationary occupancy is about 0.99% per bit;
mean continuous fault duration is 5 s. Sampling can miss brief transitions.
These distributions are intentional demo assumptions, not empirical vehicle statistics.

Records retain the local `{topic, key, event}` wrapper. Kafka keys are vehicle
IDs, preserving per-vehicle order within a topic. The event envelope identifies
`target-vehicle.v1`, channel, UTC sample time, elapsed seconds, run/vehicle IDs,
global sequence number, startup seed, and synthetic status. TSPI `data` contains
position only; the envelope carries time. The dedicated default topic is
`target-vehicle-telemetry`; provision it and configure downstream ingestion
separately. There is no automatic binding to the existing Fabric demo tables.

```bash
cd shared/integrated-test-data/02-emulators

# No third-party dependencies; omit --fast for real-time output.
uv run --no-project python src/mda_emulators/target_vehicle.py --fast --duration 900 > target.jsonl

# Replay signal values (run IDs and UTC start times remain fresh).
uv run --no-project python src/mda_emulators/target_vehicle.py --fast --seed 42 > replay.jsonl

env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv sync --extra kafka
uv run --frozen --extra kafka python src/mda_emulators/target_vehicle.py \
  --transport kafka --bootstrap-servers localhost:9092 --loop

docker build -f Dockerfile.target-vehicle -t target-vehicle:local .
docker run --rm target-vehicle:local --fast --duration 1
```

Unseeded flights use OS entropy. `--loop` starts a new run after each arc;
positions reset between runs, so consumers must group trajectories by `run_id`.
With `--seed`, subsequent flights use seed + flight index. Samples use the
half-open interval `[0, duration)`. Internal rates must stay below the TSPI rate.
`--fast` is limited to stdout to prevent accidental Kafka floods.

For secured Kafka, mount a librdkafka JSON configuration as a Kubernetes Secret
and set `KAFKA_CONFIG_FILE` to its path. For Event Hubs, add `--event-hubs`, use
the namespace endpoint on port 9093, assign Azure Event Hubs Data Sender, and
configure the pod's service account for Azure workload identity. Credentials
are obtained through `DefaultAzureCredential`; no shared-access key is needed.

Example for an existing in-cluster Kafka broker (replace image and broker):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: target-vehicle
spec:
  replicas: 1
  selector:
    matchLabels: {app: target-vehicle}
  template:
    metadata:
      labels: {app: target-vehicle}
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - name: producer
          image: your-registry/target-vehicle:0.1.0
          args: ["--transport", "kafka", "--loop"]
          env:
            - name: KAFKA_BOOTSTRAP_SERVERS
              value: kafka:9092
            - name: VEHICLE_ID
              valueFrom:
                fieldRef: {fieldPath: metadata.name}
          resources:
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: 500m, memory: 256Mi}
          securityContext:
            runAsNonRoot: true
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
```

The producer paces against a monotonic clock, flushes on SIGTERM/SIGINT, and
exits with an error on failed delivery or exhausted queue wait. Kafka uses
idempotence and all-replica acknowledgements, but has no durable local spool
or restart checkpoint. A restarted pod begins a new flight; it does not promise
end-to-end exactly-once delivery. Startup IDs/seeds go to stderr; stdout stays
JSONL. No HTTP service or inbound port is required.
