# Fabric Demo Priority Status

As of September 22, 2026: **1 demonstrated, 6 partial, 2 not demonstrated.** Checked means demonstrated for the stated synthetic scope, not production-ready. Status reflects recorded evidence, not a fresh availability check.

## Demo Priorities

- [ ] **Demonstrate how users discover and use data and simulations. — PARTIAL**

	**Done/show:** Fabric's **Live Test - Catalog and Run History** displays assets, versions and prior runs; all four tiles rendered September 21. **Left:** connect selection to authorized launch; rehearse non-admin discovery without supplied deep links and notebook sign-in.

- [ ] **Show resource-creation permissions and ownership. — PARTIAL**

	**Done/show:** deployed Azure job, managed identities, scoped service grants and budget alert. **Left:** name owners and demonstrate who can create resources versus only run them, using separate non-admin identities. Catalog ownership is still `UNASSIGNED`.

- [ ] **Demonstrate container-generated data and log collection. — PARTIAL**

	**Done/show:** September 18 container execution, 230 received events, post-exit console logs and five verified OneLake evidence files. **Left:** platform-log retrieval (`QUERY_FAILED`) and automatic collection. This runs on **Azure Container Apps Jobs**, not Kubernetes or Fabric compute.

- [x] **Show centralized ingestion and analysis. — DEMONSTRATED, SYNTHETIC SCOPE**

	**Done/show:** Eventstream -> Eventhouse -> **Asset Monitor / Evidence Review**; PostgreSQL mirroring -> Lakehouse-derived tables -> **Site Readiness & Recovery**. Ingestion, analytical queries, report rendering and controlled source-update propagation were verified. **Boundary:** recorded evidence, administrative data and the live run are separate fixtures; customer-source integration is not demonstrated.

- [ ] **Display data lineage and approved data products. — PARTIAL**

	**Done/show:** source-line references, replay/package hashes, ontology relationships and a pending-review journal. **Left:** a navigable input -> image -> run -> output chain and an actual authorized review of an exact version. Gold tables and Fabric endorsement do not equal human approval.

- [ ] **Show metadata and potential automated tagging. — PARTIAL**

	**Done/show:** catalog versions, image digest, run IDs and explicit `UNASSIGNED` / `NOT_REVIEWED` states; tag proposal/override logic exists locally. **Left:** complete owner/access/freshness/classification metadata and demonstrate persisted tag proposals, reviewer overrides and audit in Fabric. Tags must not change permissions or approval.

- [ ] **Demonstrate RBAC. — PARTIAL**

	**Done/show:** authenticated control API rejects missing/malformed tokens; database reservation/transition guards tested as administrator. **Left:** valid-user allow/deny tests for consumer/operator/publisher/reviewer/deployer, including restricted reads/exports and self-approval. Role map is empty; runtime database access is unverified; legacy notebook bypass remains.

- [ ] **Explain how external truth data stays up to date. — NOT DEMONSTRATED**

	**Done:** local refresh, version-pinning, stale-data and quarantine logic. **Left/show next:** identify provider/steward and refresh SLA; ingest V2, reject corrupt V3, display freshness and replay an old run using V1. Existing mirroring is not proof of this external-truth lifecycle.

- [ ] **Show how K8s test assets can be created autonomously, data centralized, and then K8s assets destroyed. — NOT DEMONSTRATED**

	**Done:** [AKS infrastructure](shared/integrated-test-data/00-infrastructure/README.md) and [Helm templates](shared/integrated-test-data/03-kubernetes/README.md) for six synthetic producers exist; the chart is not installed automatically. **Left/show next:** an authorized workflow creates scoped workloads, centralizes telemetry/logs/manifests, verifies retained evidence, then deletes only those test assets and proves the data remains queryable. Decide whether teardown means workloads/namespace or an ephemeral cluster; preserve shared Fabric/storage. The Container Apps rehearsal does not satisfy this item.

## Team Takeaway

**The data pipeline is demonstrated; the governed user workflow and autonomous Kubernetes lifecycle are not.** Next work: approved test identities/owners, catalog-to-run integration and complete logs, then review/tag/refresh workflows and scoped Kubernetes automation. No new cloud deployment or deletion is authorized by this checklist.

## Verified Status

Evidence dates: **September 9** Fabric baseline/mirroring/analytics/ontology; **September 18** container receipts, console logs and retained bundle; **September 21** catalog rendering and rollback-only administrator database checks. These are component checks, not the previous roadmap's broader end-to-end acceptance gates.

The Data Agent is not required to establish centralized analysis. Its September 9 published version passed technical checks, but the latest draft remains **blocked on browser answer validation** as of September 22; [acceptance record](fabric-demos/06-ai-data-agent/ANSWER_ACCEPTANCE.json). No human evidence approval was recorded. Use the labeled [recorded quick-look](shared/integrated-test-data/projections/realtime/QUICK_LOOK.md) when live services are unavailable.

