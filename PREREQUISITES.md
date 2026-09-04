# Prerequisites

## Required

- A Microsoft Fabric workspace on active F or trial capacity.
- Workspace Contributor or higher permission.
- Permission to create Lakehouse, Notebook, Semantic Model, Report, Mirrored Database, Eventstream, Eventhouse, and ontology items used by the selected stages.
- `uv`, `jq`, WSL, and the official Fabric CLI (`fab.exe` is supported).
- A browser session authenticated to the same tenant as the CLI.

Install and authenticate:

```bash
shared/setup-scripts/fabric_demo_cli.sh install
shared/setup-scripts/fabric_demo_cli.sh auth
shared/setup-scripts/fabric_demo_cli.sh status
```

## Feature-Specific

- Stage 02: an external PostgreSQL endpoint reachable from Fabric and an approved Fabric connection. The CLI deploys validation only; create the mirror in Fabric using `fabric-demos/02-database-mirroring/MIRRORING_SETUP.md`.
- Stage 04: Real-Time Intelligence capacity/features are required to provision
	the repository-managed Eventhouse, KQL database, and empty Eventstream. Live
	mode additionally requires an Event Hubs Kafka endpoint and approved Fabric
	connection; those source details are bound later and are never stored here.
- Stage 05: a Fabric runtime with the notebooks' declared Python libraries and MLflow support.
- Stage 06: Fabric IQ enabled, an Eventhouse from Stage 04, and a Fabric Environment containing the checked-in ontology accelerator wheel.

## Provision and Deploy

```bash
shared/setup-scripts/fabric_demo_cli.sh provision-lakehouses
shared/setup-scripts/fabric_demo_cli.sh push-data
shared/setup-scripts/fabric_demo_cli.sh push-all
```

The default workspace is `mda-fabric-demo`; override it with `FABRIC_WORKSPACE`. Never commit credentials, connection strings, tokens, or plaintext-token fallback settings.
