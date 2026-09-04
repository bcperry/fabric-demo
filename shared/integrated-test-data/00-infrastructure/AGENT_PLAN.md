# Agent Plan - Infrastructure

## Mission

Finish a local-only, deployable-on-approval Bicep composition for ACR, AKS,
Event Hubs/Kafka, managed PostgreSQL, ADLS Gen2, Key Vault, workload identity,
and an existing Fabric capacity reference.

## Inputs

- `main.bicep`, `modules/*.bicep`, `deploy.ps1`
- `shared/infrastructure/modules`
- Kubernetes namespace and service-account values in `../03-kubernetes`

## Deliverables

- Development, rehearsal, and demo parameter examples with placeholders only.
- Explicit resource-provider, quota, region, and permission preflight.
- Workload identities and least-privilege roles for Event Hubs and ADLS.
- A PostgreSQL identity design that removes bootstrap password use after schema setup.
- Safe teardown script limited to the named Demo 07 resource group.
- Machine-readable deployment outputs consumed by later setup scripts.
- Cost tags and documented pause/scale-down controls.

## Required interfaces

- Event Hubs names must match `05-fabric/README.md`.
- Federated identity subject must match Helm namespace/service account.
- ADLS containers must include baseline, replay, fallback, Bronze, Silver, and Gold.
- Existing Fabric capacity must never be deleted by teardown.
- PostgreSQL outputs must support Fabric mirroring validation and incremental fallback.

## Non-goals

- Do not deploy anything.
- Do not create Fabric workspace items.
- Do not commit real subscription, tenant, principal, capacity, or password values.

## Acceptance

- `az bicep build --file main.bicep --stdout` succeeds.
- PowerShell parser accepts every `.ps1`.
- Preview mode cannot create or update a resource group.
- Teardown requires explicit confirmation and verifies tags/ownership.
- Documentation distinguishes offline validation, Azure what-if, and deployment.

