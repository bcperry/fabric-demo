# Fabric Completion Rehearsal

Updated: 2026-09-09. Workspace: `mda-fabric-demo`
(`10327698-2b0d-446f-9b1b-beabe18a4bda`).

## Verified Capabilities

| Capability | Observed result |
| --- | --- |
| Baseline loading | Notebook `6fdb301f-9fac-4515-9f4c-5315f025405f` completed. |
| PostgreSQL mirror validation | Notebook `8a7b4945-2618-452e-ad7c-9ad190efad1d` completed after source and replication resumed. |
| Source-to-model change | Temporary owner on `action-0001-0004-1` reached the model; gold job `7dad3e1d-f733-49f1-a088-56e5fe6e6183`. |
| Source-to-model restoration | Original owner restored and verified; gold job `934dfec0-881d-4839-916f-f02e4289f838`. No status, evidence acceptance, or approval changed. |
| Stream recovery | Paused source and destination resumed using `WhenLastStopped`; previously sent replay recovered. Connections and routing preserved. |
| Fresh replay | Run `replay-4132d457-c7a5-4e6b-afc2-a9cb3e1f8824`: 15 raw, 14 admitted including one duplicate, one rejected, 13 canonical. |
| Replay provenance | All original payloads match after reversing replay metadata and comparing clock instants. Persisted in `EvidenceReplayLineage`; not a byte-identical transport claim. |
| Recorded evidence source | `EvidenceReviewPackages` contains the hash-verified package, 15 source-line-indexed raw records, and rules. Repeat publication did not duplicate the package. |
| Review journal | Verified `REQUEST_REVIEW` entry `74aba0c6-3421-45eb-9432-997a3a3e8b92`; no human decision was fabricated. |
| Streaming analytics | All four Stage 04 notebooks completed; semantic model refresh completed at `22:49:44Z`. |
| ML analytics | All six Stage 05 notebooks completed; model refresh `9cd27a60-e131-40be-a61c-ba0b26414b2b` completed at `23:02:34Z`. DAX returned 28 scored observations, 28 pending reviews, and six drift rows. |
| ML report rendering | Attention Now and Drift and Trust pages populated in the browser; seven systems, ten priority-review observations, six monitored features, five review-band features, and one watch-band feature. |
| Fresh dashboard queries | All five saved queries passed against `2026-09-08T20:00:00Z` through `2026-09-09T00:00:00Z`: 15 raw, six source-family rows, 13 timeline events, two duration rows, and one rejection. |
| BI interactions | Kadena selection/reset verified; action owner and evidence stay paired. Evidence table expanded to full width with larger wrapped text and explicit widths. |
| Data Agent item | `MDA Evidence Review Agent`, ID `6cf57c76-efc5-4f60-bdd2-8c353483b0c4`, published at the user's explicit request; Fabric success confirmed `2026-09-09T15:26:11Z`. Microsoft 365 Agent Store remains off. |
| Ontology | Item `0b149572-2340-4e6d-b36b-14330d12c132`: eight entity types, eight relationships, ten bindings. All eight instance views populated. |
| Ontology graph | Refresh `f94fca3d-1653-46ba-9247-6a4a0b7e0d03` completed at `2026-09-09T14:28:52Z`; executed graph query returns command `51000000-0000-4000-8000-000000000004` linked to system `bm-alpha-01`. |
| Ontology history | Two observation and four command records exactly match Lakehouse facts. Repeat publication inserts zero rows. Command chart shows 104,000 ms over the November 3, 2026 fixture window. |
| Ontology binding notebook | `95aea5da-2bf2-4b79-9e24-596c32410bd5` completed; validates source columns and exact history values, IDs and clocks. |
| Ontology creation notebook | `0ee7118f-8d1b-4dec-b871-ed77680cfd0d` completed after attaching the published dependency Environment. |
| Notebook dependency Environment | `580f1d0c-5d5c-4928-bc98-c5311173981d`, `MDA Ontology Dependencies`: `rdflib==7.1.4` published successfully at `14:51:58Z`; repeat setup does not republish. |
| SQL reference source | `EvidenceReferenceDocuments` contains the exact checked-in SQL seed, content-addressed separately from the immutable package and explicitly not deployed status. |

The successful creation notebook triggered graph refresh
`67a4462b-e171-4a0b-ae5e-fb467539093c` at `14:53:46Z`. It completed at
`14:58:47Z` without a failure reason. The repeat notebook update has therefore
materialized successfully as well.

Source update at `22:24:41Z` was verified in the model at `22:29:20Z`.
Restoration at `22:29:21Z` was verified at `22:34:30Z`. These measured intervals
include notebook execution and model refresh, not a mirroring latency guarantee.
Recovered replay receipt window: `22:08:05.139214Z` to `22:08:05.9213449Z`.

The ML refresh initially failed because both Direct Lake partitions specified
`schemaName: dbo` against schema-less OneLake table paths. Removing the qualifier
matched the working models and resolved the live refresh failure. Rebinding and
SQL metadata refresh alone did not resolve it.

Current local gates: 41 root tests (including two Spark tests) passed. The
previously passing 16 emulator tests are unchanged.

Stage 04 job IDs: `b630fde7-e553-4938-9745-f3d72b756112`,
`ee09d5c7-a65c-4545-af59-6a47f9345396`,
`a14c2fa4-7bde-414f-b440-0446e50d2ef1`,
`811092cb-b3b7-4c56-91e4-96b189865e03`.

Stage 05 job IDs: `fc8be50d-d210-4e33-8303-6308d37fbb5b`,
`40e77ff9-1dbf-437b-8048-18f7b1d60097`,
`c46d5e73-71b2-443d-b616-de4ca9dd1ba2`,
`685fc91c-7f79-43ac-bf84-f870a22c4314`,
`0cc2572b-6292-4eed-89cf-fdbe006ae28a`,
`a460ce98-1e9f-47f7-9a95-91d12947e177`.

## Acceptance Status

For exact administrator steps and service diagnostics, use the
[admin/support handoff](fabric-demos/06-ai-data-agent/ADMIN_SUPPORT_HANDOFF.md).
No support case has been submitted. After PIM activation and a fresh admin
sign-in, the user approved a capacity-only ontology override on `mdademo`.
The override saved as enabled for all users in capacity; the tenant-wide
ontology default remains disabled. AI safety and cross-geography settings
were not changed.

1. **Ontology resolved:** capacity-scoped enablement propagated and creation
   succeeded at `2026-09-09T14:03:10Z`. Static identity bindings now use existing
   lakehouse facts. Isolated Eventhouse history preserves those same identities
   and recorded clocks; replay tables are not substituted. Graph refresh initially
   failed because `dbo` was treated as a OneLake storage path. Omitting the schema
   fixed materialization. Counts: Scenario 2, TestEvent 2, SystemInstance 7,
   TestObjective 5, Finding 4, CorrectiveAction 4, Observation 2, CommandEvent 4.
   Scenario and TestEvent counts include the explicit unknown dimension member.
2. **Agent technical verification passed:** deployment
   `06395e9a-feee-43cb-bad1-f6477aabd403` succeeded at `15:07:27Z`.
   `EvidenceReviewContext` is the sole selected table, confirmed by service
   definition export. It provides independently identified package and SQL
   reference sources side by side without asserting an event relationship.
   Six example queries execute directly. All five unchanged acceptance questions
   then completed in order in one verified fresh chat (59/24/9/14/17 seconds).
   The first two executed queries returned the complete row; later answers reused
   conversation evidence. Required assertions include the exact 20-second gap,
   raw-line preservation, distinct event identities, seed-versus-deployed limits,
   and pending human review. Source/field references were checked against query
   output and verified originals. A separate fresh-chat cross-event check also
   passed. This is not five independent fresh-chat trials or human acceptance.
   [Captured answers](fabric-demos/06-ai-data-agent/ANSWER_ACCEPTANCE_RESPONSES.json)
   and the [acceptance record](fabric-demos/06-ai-data-agent/ANSWER_ACCEPTANCE.json)
   retain scope and historical failures. The user subsequently authorized
   publication; Fabric confirmed success at `15:26:11Z`. Microsoft 365 Agent Store
   publishing remains off. Publication does not assert human evidence acceptance;
   no safety policy was bypassed.
3. **Human acceptance:** the journal supports evidence acceptance or requested
   changes, but an actual reviewer must inspect sources and record a decision.
   Application-level confirmation is not server-enforced separation of duties.
The previous dashboard browser gate is resolved. On 2026-09-09, the signed-in
browser rendered all five tiles for the last-24-hours replay window, including
15 raw envelopes, six source families, the timeline, 48/125-second duration bars,
and the exact rejected record. Switching to last three hours cleared all five
tiles. The off-screen rejection tile requires scrolling to load. No dashboard
definition change was needed for the transient embedded-frame error.

## Linked Finding Closure: 2026-09-09

The new `finding-streaming-envelope-quarantine-001` administrative finding uses
`test-streaming-findings-001`, the package hash, source line 15, and
`malformed-event-001`. It reviews retention of a rejected envelope in quarantine;
it does not claim source repair, test success, or resolution of the independent
Kadena fixture.

[finding_closure.py](fabric-demos/06-ai-data-agent/finding_closure.py) provisions
the event, finding, exact evidence attachment, disposition state, and relational
audit. It locks finding/state rows and commits each transition with its audit
entry atomically. Closure requires prior acceptance of this specific disposition,
matching source identity, rationale, and actual human review confirmation.

The live PostgreSQL rehearsal exercised REQUEST_CHANGES -> ACCEPT_EVIDENCE ->
CLOSE_FINDING, verified the administrative CLOSED status and three audit entries,
then rolled back every rehearsal write. Subsequent provisioning left the actual
finding OPEN with zero review decisions. No approval was attributed to the user.

PostgreSQL and its mirror had been independently stopped/paused and were resumed.
Replication processed the finding and evidence at approximately `13:22:20Z`.
SQL initially returned no rows until metadata refresh completed at `13:24:09Z`.
The joined finding/evidence query then returned the exact OPEN finding and
package/source-line reference. At `13:26:47Z`, the repeatable
[linkage verifier](fabric-demos/06-ai-data-agent/verify_finding_linkage.py) passed
against both Fabric SQL and the 15-record/13-canonical Eventhouse replay.

The two new disposition/audit tables are PostgreSQL workflow state; the existing
mirror selection carries the event, finding, and evidence tables, not these new
workflow tables. Server-enforced reviewer separation and tamper-resistant audit
remain production-hardening boundaries, not claims of this demo. The audit uses
database session identity, and database administrators can modify demo tables.

Current root test suite: 41 passing tests, including six closure tests, four
Environment setup tests, and two Spark aggregation tests. The previously passing
16 emulator tests were unchanged.

## Repeatable Commands

```bash
shared/setup-scripts/fabric_demo_cli.sh provision-demo-06-agent
shared/setup-scripts/fabric_demo_cli.sh provision-demo-06-ontology
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv run fabric-demos/02-database-mirroring/rehearse_update.py --execute
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv run python fabric-demos/06-ai-data-agent/verify_replay_lineage.py replay-4132d457-c7a5-4e6b-afc2-a9cb3e1f8824
```

Ontology provisioning now verifies history before updating the definition. Agent
deployment returning 202 means accepted, not answer-ready. The rehearsal refuses
to modify a source while mirroring is paused and restores its captured known
owner in a `finally` block; `--restore` is available after a process interruption.

Fabric capacity, PostgreSQL, mirror, and Eventstream were resumed for this work
and left running. Normal service charges apply. No resources were replaced or
destructively reseeded; no tenant safety settings were changed.