# From Data Discrepancy to Reviewable Evidence

## Audience and Promise

In 25 minutes, show a director what needs review and show an engineer why the
evidence supports that conclusion. The demonstration does not authorize a test,
certify a participant, or infer an operational outcome.

Opening line: "Can we explain what the data establishes, what it does not,
and who needs to review it without rebuilding the evidence by hand?"

## Before the Room

Run from the repository root:

```bash
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL SPARK_LOCAL_IP=127.0.0.1 uv run --with 'pyspark==3.5.7' --with requests python -m unittest discover -s tests -v
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv run python shared/integrated-test-data/scripts/build_review_package.py check
```

Complete the [deployment gates](DEMO_BUILD_PLAN.md#deployment-boundary) before
presenting a Fabric interaction. Notebook syntax checks do not establish service
readiness. Keep the [recorded quick-look](shared/integrated-test-data/projections/realtime/QUICK_LOOK.md)
open as an explicitly local fallback, not as a screenshot of live state.

There are two scopes. Name the switch aloud and keep their IDs visible:

| Scope | Purpose | Boundary |
| --- | --- | --- |
| `test-integrated-defense-001` | Administrative ownership and review | Mirrored synthetic lead event; seeded names and dates must match the deployed source. |
| `test-streaming-findings-001` | Recorded data discrepancy and preservation | Small, independent replay fixture; not evidence of the administrative event's outcome. |

## Act 1: The Review (0-5 Minutes)

Open **Site Readiness & Recovery**. Start with an unresolved issue, its owner,
and its attached evidence, not the map or row count.

Use `finding-0001-0004`, the seeded Kadena evidence-package issue, only after
confirming it exists in the deployed source. The seeded accountable organization
is **Kadena Range Evidence Lead** and the action is **Complete Kadena evidence
validation**. Read the actual deployed status and due date; do not assume that
the checked-in seed is the current database state.

Select the affected site. Confirm casework narrows and reset the selection.
Explain that analytical readiness on the other pages has separate scope.
An empty selection is not approval. A normal synthetic profile is not a
readiness certification.

Director takeaway: "I can identify the issue, ownership, and evidence gap.
Approval is not implied by the dashboard."

## Act 2: The Investigation (5-13 Minutes)

Switch explicitly to the **recorded streaming fixture**, a separate engineering
example. Run the four Demo 04 notebooks before the presentation; open their
published report rather than waiting for Spark during the audience session.

1. Show the 15 original records, including the duplicate and malformed envelope.
2. Reconcile 13 canonical events + 1 duplicate + 1 rejected envelope = 15 raw
   records. Admission does not certify the remaining payloads as technically valid.
3. Follow the repeated ID to source lines 7 and 8; both remain preserved.
4. Show the malformed envelope at line 15 without treating its reported state
   as valid participant evidence.
5. Show the follow-on deadline of `14:05:25Z` and latest recorded event time of
   `14:05:05Z`. Neither establishes an independently verified capture cutoff.
   Ask the audience whether the follow-on is overdue. The correct conclusion
   is **undetermined**, not missing or failed.

When Eventhouse is available, open **Evidence Review**, select the applicable
UTC window, and compare disjoint windows. Receipt-window tiles will differ from
event-window tiles when historical events are ingested today. Show the run ID.
Only discuss source-family coverage where a declaration exists; it is not an
instance-level inventory. The 405-event stream needs a different coverage contract.

Engineer takeaway: "We can account for the raw data and state the limits of the
observation window without mistaking a data anomaly for participant failure."

## Act 3: The Accountable Update (13-18 Minutes)

Stay on `test-streaming-findings-001` for the verified same-event path:

1. Open administrative finding `finding-streaming-envelope-quarantine-001`.
   It is a data-quality disposition review for the rejected source record, not
   a finding about participant performance.
2. Inspect its mirrored evidence reference: package identity, source line 15,
   and `malformed-event-001`. Run the read-only linkage verifier below to check
   both the Fabric SQL attachment and the Eventhouse replay against the same
   hash-verified recorded package.
3. Show the actual finding remains OPEN. Explain that the live PostgreSQL
   rehearsal exercised requested changes, acceptance, closure, and audit, then
   rolled back all test decisions. No real approval was recorded.
4. An actual reviewer can accept this specific quarantine disposition and then
   close the finding using the [closure workflow](fabric-demos/06-ai-data-agent/README.md#linked-finding-closure).
   Closure means the rejected record's retention was reviewed; it does not mean
   the source was repaired, capture was complete, or execution was authorized.

```bash
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv run fabric-demos/06-ai-data-agent/verify_finding_linkage.py replay-4132d457-c7a5-4e6b-afc2-a9cb3e1f8824
```

### Separate Administrative Propagation Rehearsal

Return explicitly to the administrative lead event. In a disposable rehearsal,
the presenter may change a single action's descriptive status or owner after
capturing its original values and agreeing on the synthetic change. Do not run
the director seed as a reset: it closes all lead-event findings before reseeding.

Observe the source update in the mirrored table. Then rebuild the Demo 03 gold
products and refresh the semantic model: this report uses derived Delta tables,
so mirroring alone does not update its casework. Verify exact finding/action IDs
and timestamps in the source table, then compare the paired owner/deadline in
the report. Its summary does not expose every identifier. Record the observed
propagation interval rather than promising a fixed latency. Restore the captured
values after the rehearsal and verify the restoration through the same path.

If a controlled update was not rehearsed, inspect existing source-to-report
lineage instead and say that update propagation has not been demonstrated.
Changing administrative status does not prove the missing evidence was supplied.

Read-only source check for the seeded example:

```sql
SELECT corrective_action_id, finding_id, action_title, action_status,
       owner_role, due_time_utc, recorded_at_utc
FROM mda_ops.corrective_action
WHERE finding_id = 'finding-0001-0004'
ORDER BY due_time_utc NULLS LAST, corrective_action_id;
```

## Act 4: The Reviewable Conclusion (18-25 Minutes)

Return to the recorded fixture and open its generated **Recorded Evidence
Quick-Look**. It includes source-line references, ruleset version, exact raw-file
checksum, reconciled counts, and explicit limitations. Human approval is pending.

Use the [AI acceptance questions](fabric-demos/06-ai-data-agent/ANSWER_ACCEPTANCE.json)
only after their source artifacts are explicitly available to the agent. Ask:

- "Why are there 15 raw records but only 13 canonical events?"
- "Was the expected follow-on overdue when this recording ended?"
- "Does this prove the administrative lead event's issue is resolved?"
- "Is this evidence package approved?"

Inspect the citation, not just the prose. The last two answers must not invent
a cross-event relationship or approval. If the agent or binding is unavailable,
show the expected answer and cited file as a scripted acceptance example, not a
successful AI interaction.

The deployed draft selects `EvidenceReviewContext`: the recorded package, raw
records and an exact, separately identified SQL seed are retrieved side by side,
not joined as related events. The seed is not proof of current deployed status.
All five unchanged questions passed technical checks in one fresh-thread run;
inspect the captured answers and cited fields during the demonstration. Agent
publication was authorized and confirmed on 2026-09-09; human evaluation remains
pending. The original content rejection
no longer reproduces; its cause is not established.

The ontology now has eight populated entity views and a materialized relationship
graph. Open CommandEvent `51000000-0000-4000-8000-000000000004` to inspect its
SystemInstance relationship. Set the custom chart range to November 3-4, 2026
to see the recorded 104,000 ms value. These history rows preserve the Lakehouse
fact identities; they are separate from the recorded streaming replay package.

Closing line: "The useful result is a conclusion we can trace and challenge,
with uncertainty and human review still visible."

## Optional Engineering Extension

Use Demo 05 to explain synthetic prioritization, held-out runs, comparison with
a deterministic baseline, drift, and human review. Do not present model scores
as probabilities of real-world readiness or success.

## Rehearsal Record

Record the deployed workspace/item IDs, refresh times, source and receipt windows,
selected run, screenshot of the scoped report, KQL acceptance results, and AI
case results. Mark unexecuted gates **NOT RUN**, never passed by inference.