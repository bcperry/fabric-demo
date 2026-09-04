# Kubernetes Runtime Assets

This Helm chart is a deployment-ready template but is not installed
automatically.

The base defines:

- Namespace `mda-demo`
- Workload-identity service account
- Six producer deployments
- ConfigMap with broker, scenario, duration, and time-scale settings
- Writable manifest cache so each producer persists a deterministic run manifest
- Startup, readiness, and liveness probes
- Resource requests and limits

## Producers

| Deployment | Events |
| --- | --- |
| `tpy2-producer` | TPY-2 observations and status |
| `patriot-producer` | Three configured Patriot instances |
| `thaad-producer` | THAAD status and participation |
| `battle-management-producer` | Shared-track correlation and publication |
| `army-integration-producer` | Cueing, assignment, and acknowledgement |
| `operations-support-producer` | Sustainment plus target/interceptor, instrumentation, ground truth, environment, network, readiness, operator, and advisory safety evidence |

## Render locally

Rendering does not contact a cluster:

```bash
helm template mda-demo 03-kubernetes -f 03-kubernetes/values-local.yaml
helm template mda-demo 03-kubernetes -f 03-kubernetes/values-azure.yaml
```

The local values write JSON Lines to pod logs and need no Azure resources.
The Azure values use Kafka mode and contain replacement placeholders for the
container image, Event Hubs endpoint, and managed identity client ID.

At render time, Helm creates one shared run start and unique run ID for all six
producers. Pod restarts retain that identity and replay deterministic event IDs,
and each producer writes a JSON run manifest into the mounted manifest cache.
A new demo execution requires a fresh `helm upgrade` render or explicit new
`runtime.startTimeUtc` and `runtime.runId` values.

Do not apply the Azure overlay until those placeholders have been replaced and
the user explicitly authorizes deployment.
