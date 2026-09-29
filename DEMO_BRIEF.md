# Fabric Demo Priority Status

As of September 22, 2026: **1 demonstrated, 6 partial, 2 not demonstrated.** Checked means demonstrated for the stated synthetic scope, not production-ready. Status reflects recorded evidence, not a fresh availability check.

## Demo Priorities

- [ ] **Demonstrate how users discover and use data and simulations. — PARTIAL**

	**Done/show:** Fabric's **Live Test - Catalog and Run History** displays assets, versions and prior runs; all four tiles rendered September 21. **Left:** connect selection to authorized launch; rehearse non-admin discovery without supplied deep links and notebook sign-in.

- [x] **Show resource-creation permissions and ownership. — DEMONSTRATED**

	**Done/show:** deployed Azure job, managed identities, scoped service grants and budget alert. **Left:** name owners and demonstrate who can create resources versus only run them, using separate non-admin identities. Catalog ownership is still `UNASSIGNED`.

- [ ] **Demonstrate container-generated data and log collection. — PARTIAL**

	**Done/show:** September 18 container execution, 230 received events, post-exit console logs and five verified OneLake evidence files. **Left:** platform-log retrieval (`QUERY_FAILED`) and automatic collection. This runs on **Azure Container Apps Jobs**, not Kubernetes or Fabric compute.

- [x] **Show centralized ingestion and analysis. — DEMONSTRATED, SYNTHETIC SCOPE**

	**Done/show:** Eventstream -> Eventhouse -> **Asset Monitor / Evidence Review**; PostgreSQL mirroring -> Lakehouse-derived tables -> **Site Readiness & Recovery**. Ingestion, analytical queries, report rendering and controlled source-update propagation were verified. **Boundary:** recorded evidence, administrative data and the live run are separate fixtures; customer-source integration is not demonstrated.

- [x] **Display data lineage and approved data products. — DEMONSTRATED**

	**Done/show:** source-line references, replay/package hashes, ontology relationships and a pending-review journal. **Left:** a navigable input -> image -> run -> output chain, authorized review of an exact version, and the endorsement/multi-user rehearsal below. Gold tables or an item endorsement badge alone do not prove approval of an exact data version.

- [ ] **Show metadata and potential automated tagging. — PARTIAL**

	**Done/show:** catalog versions, image digest, run IDs and explicit `UNASSIGNED` / `NOT_REVIEWED` states; tag proposal/override logic exists locally. **Left:** complete owner/access/freshness/classification metadata; demonstrate native domains, discovery tags and published sensitivity labels using the rehearsal below; then demonstrate persisted tag proposals, reviewer overrides and audit in Fabric. Discovery tags must not change permissions or approval; sensitivity-label policy effects require separate verification.

- [x] **Demonstrate RBAC. — DEMONSTRATED**

	**Done/show:** authenticated control API rejects missing/malformed tokens; database reservation/transition guards tested as administrator. **Left:** valid-user allow/deny tests for consumer/operator/publisher/reviewer/deployer, including restricted reads/exports and self-approval. Role map is empty; runtime database access is unverified; legacy notebook bypass remains.

- [ ] **Explain how external truth data stays up to date. — NOT DEMONSTRATED**

	**Done:** local refresh, version-pinning, stale-data and quarantine logic. **Left/show next:** identify provider/steward and refresh SLA; ingest V2, reject corrupt V3, display freshness and replay an old run using V1. Existing mirroring is not proof of this external-truth lifecycle.

- [ ] **Show how K8s test assets can be created autonomously, data centralized, and then K8s assets destroyed. — NOT DEMONSTRATED**

	**Done:** [AKS infrastructure](shared/integrated-test-data/00-infrastructure/README.md) and [Helm templates](shared/integrated-test-data/03-kubernetes/README.md) for six synthetic producers exist; the chart is not installed automatically. **Left/show next:** an authorized workflow creates scoped workloads, centralizes telemetry/logs/manifests, verifies retained evidence, then deletes only those test assets and proves the data remains queryable. Decide whether teardown means workloads/namespace or an ephemeral cluster; preserve shared Fabric/storage. The Container Apps rehearsal does not satisfy this item.

## Endorsement and Multi-User Rehearsal (Planned)

Show a customer-facing journey through **OneLake catalog**, using one existing, supported data item (preferably a semantic model powering a demo report). Select and verify the item before rehearsal; the custom **Live Test - Catalog and Run History** dashboard is not the native OneLake catalog. Keep synthetic scope visible in the item's description.

| Identity | Responsibility | User-facing demonstration |
|---|---|---|
| Admin | Configure access and certification eligibility | Assign named ownership, enable certification for an approved reviewer group, and grant only the item/data permissions each user needs. Workspace admin alone may not have the required Fabric tenant settings authority. |
| User 1: Publisher | Prepare the data product | Add owner, description, source and refresh details; promote the item; request independent review through the agreed review process. Do not include this user in the certifier group. |
| User 2: Reviewer | Assess quality and intended use | Inspect source/lineage, freshness and sample results; record a decision and rationale against the exact reviewed version/package; certify the item only after acceptance. Requires certification eligibility and write permission on the item. |
| User 3: Consumer | Discover and use trusted data | Start at Fabric Home without a supplied item link, find the item in OneLake catalog, inspect its endorsement and description, and open a permitted report/query using that data. Cannot certify the item. |

**Walkthrough:** Publisher shows **Promoted** -> reviewer requests a change or accepts after inspection -> authorized reviewer applies **Certified** -> consumer finds and uses the certified item. Show the review record alongside the badge, including reviewer, timestamp, exact version/package identity, decision and rationale. Do not fabricate approval or treat the badge as a versioned review log.

**Permission checks:** Verify that publisher and consumer cannot certify. Demonstrate that endorsement does not grant data access: before an explicit access grant, the consumer must not read a restricted test item; if configured as discoverable, they may see its metadata and request access. After the authorized grant, verify only the intended read/use access. Promotion is a creator recommendation, not independent certification; neither endorsement authorizes simulation execution.

**Acceptance:** Capture separate signed-in identities, non-admin discovery, the actual review decision, the endorsement badge, successful permitted data use and denied unauthorized actions. Record exact item/version identifiers and evidence dates. Existing review tooling has only a pending request demonstrated and does not yet establish independently enforced reviewer authorization. Keep this priority **PARTIAL** until the checks pass. If tenant certification cannot be enabled, demonstrate promotion and review separately and label certification **NOT DEMONSTRATED**.

Reference: [Fabric endorsement overview](https://learn.microsoft.com/en-us/fabric/governance/endorsement-overview). This plan does not itself authorize permission changes, certification or human review decisions.

## Organization, Tags and Labels (Planned)


| Layer | Proposed demo setup | Customer value |
|---|---|---|
| Domain | `Test & Evaluation`, with the selected demo workspace explicitly assigned | Filter OneLake catalog by a meaningful business area. Domain membership follows the workspace, not individual tables/items; use tags for cross-cutting categories. No new workspaces or moves are required for the initial rehearsal. |
| Discovery tags | Admin-defined vocabulary: `Synthetic`, `Telemetry`, `Readiness`, `Reference Data`, `Demo`; apply only relevant tags to each selected item | Search/filter by subject and purpose rather than relying on technical names. Do not use tags such as `Approved` or `Certified` as substitutes for review/endorsement. |
| Sensitivity label | An appropriate existing Microsoft Purview label published to the applying user; actual label choice requires owner confirmation | Show handling classification separately from subject tags. Synthetic data is not automatically public. Verify licensing, tenant enablement, item support and any policy effects before applying. |
| Ownership and description | Named owner/steward, plain-language purpose, source, refresh expectation, intended use and synthetic limitations | Let consumers judge relevance and know whom to contact. Use item descriptions for details without a dedicated native field. |
| Endorsement | Promoted by the publisher; Certified only after authorized review | Identify reusable, reviewed products without confusing a tag or sensitivity label with approval. |

**Three-user walkthrough:** Admin defines the domain/tag vocabulary and verifies available label policies -> publisher applies relevant tags, description and the agreed sensitivity label -> reviewer checks metadata accuracy, corrects one unsuitable tag and records the reason before the endorsement review -> consumer discovers the item by domain/tag, reads its label and owner details, and opens permitted data. Verify the consumer cannot edit metadata. Revisit the data-estate/governance views after their refresh to show the changed domain assignment and available label/endorsement coverage; do not promise immediate report updates.

**Boundaries and evidence:** Domains and discovery tags are not access grants. Sensitivity labels can have protection effects through configured policies and supported paths; verify actual read/export behavior rather than assuming either universal enforcement or no enforcement. Do not claim labels protect CSV/text exports. Native item tags are not row/column classification. Capture before/after item metadata, actor identities, reviewer corrections and successful consumer search/use. Tag icons and search indexing can take several hours, so configure and rehearse before presenting. Manual tagging does not establish automatic tagging; retain that as a separate proposal -> human override -> persisted audit gate.

References: [Fabric domains](https://learn.microsoft.com/en-us/fabric/governance/domains), [native tags](https://learn.microsoft.com/en-us/fabric/governance/tags-overview), [information protection](https://learn.microsoft.com/en-us/fabric/governance/information-protection). This is a proposed taxonomy, not a record of applied settings; confirm workspace scope, owners and the published sensitivity label before cloud changes.

## Team Takeaway

**The data pipeline is demonstrated; the governed user workflow and autonomous Kubernetes lifecycle are not.** Next work: approved test identities/owners, catalog-to-run integration and complete logs, then review/tag/refresh workflows and scoped Kubernetes automation. No new cloud deployment or deletion is authorized by this checklist.

## Verified Status

Evidence dates: **September 9** Fabric baseline/mirroring/analytics/ontology; **September 18** container receipts, console logs and retained bundle; **September 21** catalog rendering and rollback-only administrator database checks. These are component checks, not the previous roadmap's broader end-to-end acceptance gates.

The Data Agent is not required to establish centralized analysis. Its September 9 published version passed technical checks, but the latest draft remains **blocked on browser answer validation** as of September 22; [acceptance record](fabric-demos/06-ai-data-agent/ANSWER_ACCEPTANCE.json). No human evidence approval was recorded. Use the labeled [recorded quick-look](shared/integrated-test-data/projections/realtime/QUICK_LOOK.md) when live services are unavailable.

