# Microsoft Fabric Integrated Test Demo

This repository demonstrates how Microsoft Fabric turns synthetic test records
into traceable analytical evidence. Start the audience experience with
[From Data Discrepancy to Reviewable Evidence](DEMO_WALKTHROUGH.md). Use the six
technical modules below as supporting deep dives.

The [implementation plan](DEMO_BUILD_PLAN.md) separates local checks from the
Fabric deployment gates. The [recorded quick-look](shared/integrated-test-data/projections/realtime/QUICK_LOOK.md)
is a reproducible evidence package, not a human approval or live operational view.

## Simulated Data

Yes, the repository contains the required demo data. Release `2026.11.03` is
`SYNTHETIC_UNCLASS` and includes:

- CSV planning, system, readiness, maintenance, finding, and review records
- 405 deterministic simulated telemetry and operational events
- predicted baseline tracks, events, measures, and environmental assumptions
- one intentional delayed command event for investigation
- manifests, checksums, schemas, seeds, and stable cross-source identifiers

The canonical source is [shared/integrated-test-data](./shared/integrated-test-data/README.md).
Regenerating it produces the same 405-event release. The focused streaming lesson
uses a separate 15-record fixture with a different event identity; do not present
it as evidence that closes an administrative lead-event finding.

## Progressive Demo

| Step | Build | Leadership hook | Data-professional hook |
|---|---|---|---|
| [01 - Data Lake Basics](./fabric-demos/01-data-lake-basics/README.md) | Upload CSV files and publish Delta tables in a Lakehouse. | Is the planned test data complete and ready? | Files, schemas, Delta, provenance, and quality checks. |
| [02 - Database Mirroring](./fabric-demos/02-database-mirroring/README.md) | Mirror an external PostgreSQL operations database into Fabric. | Is operational readiness current without manual extracts? | External source setup, CDC/mirroring, latency, and lineage. |
| [03 - Star Schema and BI](./fabric-demos/03-star-schema-bi/README.md) | Conform Lakehouse and mirrored data into dimensions, facts, and a Direct Lake report. | Which systems, objectives, and findings need attention? | Grain, surrogate keys, relationships, measures, and semantic modeling. |
| [04 - Real-Time Ingestion](./fabric-demos/04-real-time-ingestion/README.md) | Replay or stream the same scenario through Eventstream and Eventhouse. | What is happening now and what requires intervention? | Event contracts, ordering, KQL, stream quality, and deterministic findings. |
| [05 - ML Models](./fabric-demos/05-ml-models/README.md) | Train, compare, explain, score, and monitor readiness models. | Why was this system prioritized and can the score be trusted? | Feature engineering, MLflow, explainability, drift, and model lineage. |
| [06 - AI Data Agent](./fabric-demos/06-ai-data-agent/README.md) | Ask grounded questions across governed Lakehouse and Eventhouse products. | What happened, why, and what evidence supports the answer? | Ontology bindings, semantic grounding, source citations, and evaluation. |

The sequence covers planning, setup, execution, analysis, and post-test reporting
from [MDA_test_lifecycle.md](./MDA_test_lifecycle.md). Each stage leaves a usable
Fabric artifact. Cross-source identity must be verified before relating findings
across modules; shared storage alone does not prove that relationship.

Start with [PREREQUISITES.md](./PREREQUISITES.md) and the
[Fabric CLI workflow](./shared/setup-scripts/FABRIC_CLI.md).
