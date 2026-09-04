# Agent Plan - Kubernetes Packaging

## Mission

Make the Helm chart a repeatable deployment package for coordinated Simulation,
Observed/Real, and projection workloads without embedding environment-specific values.

## Deliverables

- Helm schema (`values.schema.json`) validating all values.
- Deployments for scenario controller; Simulation and Observed/Real TPY-2 radar,
    Patriot radar, Patriot launcher, and THAAD launcher profiles; battle-management,
    Army-integration, sustainment, PostgreSQL projector, and baseline writer.
- Replica-safe Faker startup seeds and persisted identity manifests. Five scaled
    pods must yield five distinct streams, and supplied manifests must replay them.
- Shared rollout start and run identity.
- Workload identity, ConfigMaps, resource limits, probes, security contexts,
  disruption budgets, and network policies.
- Local, development, rehearsal, and demo values examples.
- Image digest support and documented ACR build/push commands that are never run automatically.
- Helm test or smoke Job that validates imports and scenario configuration.

## Interfaces

- Namespace/service account must match `00-infrastructure`.
- Image entrypoint and arguments must match `02-emulators`.
- Event Hub names and ADLS/PostgreSQL settings must match infrastructure outputs.

## Non-goals

- Do not install the chart or contact a cluster.
- Do not include credentials or connection strings.

## Acceptance

- `helm lint` passes for every values profile.
- Every profile renders expected workload counts and transport modes.
- `kubectl apply --dry-run=client` accepts rendered YAML when supported.
- Pods run non-root with dropped capabilities and read-only root filesystems.
- A restart preserves the persisted run/instance identity; scaling creates one
    identity manifest per new instance ordinal.

