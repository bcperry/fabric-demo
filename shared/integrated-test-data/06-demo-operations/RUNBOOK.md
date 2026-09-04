# Shared Release Operations Runbook

## Current operating mode

Local-only development. No cloud deployment is authorized.

## Offline preflight

From `shared/integrated-test-data`:

```bash
uv run python scripts/validate_local.py
```

Expected results:

- All JSON files parse.
- Emulator Python compiles.
- Unit tests pass.
- `generate.py validate` confirms the checked-in deterministic assets.
- A deterministic 180-second stream contains 405 records and one delayed event.
- Bicep compiles locally when Azure CLI/Bicep is installed.
- Helm renders both values files when Helm is installed.
- No prohibited platform references exist.

Run the contract and example pass with `jsonschema` through `uv` when you need a
full schema check:

```bash
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv run --with jsonschema python generate.py validate
```

## Refresh the local asset package

```bash
uv run python generate.py write-assets
uv run python generate.py summary
```

## Local event generation

```bash
PYTHONPATH=02-emulators/src python3 -m mda_emulators.cli \
  --scenario 01-contracts/examples/scenario.integrated-defense.json \
  --duration-seconds 180 \
  --manifest-output /tmp/mda-demo-manifest.json \
  --transport file \
  --output /tmp/mda-demo-events.jsonl
```

The local fallback package is the checked-in `data/observed_eventstream.jsonl`
plus the PostgreSQL and baseline files listed in `RELEASE_MANIFEST.json`.

## Reset model

The emulator is reset by rerunning it with the same:

- Scenario file
- Seed
- Start time
- Duration

That produces identical locations, identifiers, events, and anomaly timing.
Cloud reset procedures will be added only after deployment is authorized and the
resource topology is confirmed.

Authoritative pause/resume decisions must still come from operator and review
records. `safety-status` events are evidence only.

## Demo-day gates

1. Fabric capacity active.
2. Workspace assigned to the capacity.
3. Eventstream sources connected.
4. Eventhouse tables receiving current data.
5. SQL incremental pipeline successful.
6. ADLS baseline visible through OneLake.
7. Gold products reconciled.
8. Live and static fallback paths tested.
9. Scripted anomaly appears exactly once.
10. Presenter completes two clean runs.

## Stop conditions

Stop rather than improvise if:

- Any data is not clearly synthetic.
- The wrong tenant or subscription is selected.
- A credential appears in output or source control.
- Event counts cannot be reconciled.
- The anomaly outcome differs from the expected evidence chain.
