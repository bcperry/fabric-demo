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
