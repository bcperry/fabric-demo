# Integrated Test Data Product

This directory is the only data authority for the portfolio. Release
`2026.11.03` deterministically describes one fictional integrated-defense test
from planning through observation, ground truth, readiness, findings, review,
and corrective action.

## Release Contract

- `01-contracts/` defines the scenario and event schemas.
- `02-emulators/` generates the live source behavior.
- `data/` is the immutable generated release: 405 observed events, predicted
  baseline products, 13 administrative batches, manifests, and checksums.
- `projections/` contains deterministic tabular, rule, and feature views used
  by Fabric notebooks. A projection is not a second source of truth.
- `PORTFOLIO_CONTRACT.json` maps every shared asset to its consumers.

Regenerate and validate from the repository root:

```bash
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv run --with jsonschema \
  python shared/integrated-test-data/generate.py write-assets
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv run --with jsonschema \
  python shared/integrated-test-data/generate.py validate
```

Fabric deployment uploads this directory once to
`Files/shared/integrated-test-data`. Demo notebooks read from that location and
publish derived Delta tables, models, reports, Eventhouse tables, or ontology
bindings.
