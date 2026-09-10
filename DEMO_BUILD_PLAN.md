# Evidence-First Demo Build Plan

## Outcome

Demonstrate how a team moves from fragmented synthetic test records to a
traceable, reviewable conclusion. Fabric manages data and analytical evidence;
it neither authorizes test execution nor substitutes for certified systems.

The audience contract comes from [the lifecycle](MDA_test_lifecycle.md), the
[director role](.github/agents/Missile-Test-Director.agent.md), and the
[engineer role](.github/agents/Missile-Test-Engineer.agent.md).

## Implementation Order

| Step | Deliverable | Acceptance gate |
| --- | --- | --- |
| 1 | Honest report authority and scope | No calculated approval or static authoritative-evidence claim; selected-site scope is distinguishable from event-wide scope. |
| 2 | Consistent streaming admission | Accepted and rejected records use the same validation rule; malformed and duplicate records remain available as raw evidence. |
| 3 | Window-aware streaming views | Every query consumes the selected window; event time and receipt time are labeled separately; the view does not claim live status from historical rows. |
| 4 | Repeatable evidence-review walkthrough | Presenter follows a named issue through observations, limitations, accountable follow-up, and pending human review. Separate fixtures are disclosed rather than joined narratively. |
| 5 | AI answer acceptance suite | Questions have required evidence, expected limitations, and fail conditions; bindings alone do not count as answer validation. |
| 6 | Regression and deployment gates | Local tests pass; Fabric query execution, model refresh, filters, rendering, and grounded answers are separately verified before presenting. |

## Keep

- Deterministic canonical release, stable identifiers, schemas, and emulator tests.
- PostgreSQL mirroring and existing Fabric item definitions.
- Explicit synthetic thresholds and incomplete-window `UNDETERMINED` outcomes.
- Named recovery organizations and human-review boundaries.
- ML governance as an optional extension, not a prerequisite for the main story.

## Presentation Structure

1. **The review:** one fictional event, explicit evidence cutoff, unresolved issues.
2. **The investigation:** expected versus observed evidence, with data-feed state
   distinct from participant state.
3. **The update:** an attributable administrative change, visible propagation,
   and an explicit remaining review requirement.
4. **The conclusion:** a quick-look with citations, limitations, and approval state.

Target duration: 25 minutes. Retain the six technology demos as technical
deep dives. Do not claim one end-to-end incident until cross-source identity and
evidence mappings are verified.

## Deployment Boundary

Local tests do not deploy resources. The scoped deployments below were also
performed in `mda-fabric-demo`. Before presenting:

- Deploy through the existing Fabric workflow after reviewing the local diff.
- Refresh the semantic model and verify site selections and reset behavior.
- Execute KQL against a clean synthetic rehearsal and reconcile admitted records.
- Select disjoint windows and confirm that every visual changes consistently.
- Confirm actual receipt timestamps and explicitly identify recorded replay.
- Exercise each AI acceptance question against deployed sources.
- Rehearse the primary path and the documented unavailable-source fallback.

Passing local syntax or contract tests is not proof of deployed behavior.

## Build Status: 2026-09-08

The following local changes are implemented; the full end-to-end capability
still has the explicit gaps listed in the completion record:

- Removed calculated execution approval and static authoritative-evidence claims.
- Connected mirrored site filtering to casework and separated analytical scope.
- Kept action/owner/deadline and attached evidence fields on the same source record.
- Unified Eventhouse envelope admission/rejection, introduced windowed canonical
   queries, and bounded source declarations to overlapping recorded runs.
- Separated replay, publication, and receiver clocks and isolated replay run IDs.
- Generated a reproducible [quick-look](shared/integrated-test-data/projections/realtime/QUICK_LOOK.md)
   with real source/rules digests and content-bound package identity.
- Added the [audience walkthrough](DEMO_WALKTHROUGH.md) and
   [AI acceptance suite](fabric-demos/06-ai-data-agent/ANSWER_ACCEPTANCE.json).

Verified locally before the completion pass: 18 new tests including two actual Spark aggregation tests;
16 emulator/replay tests; canonical 405-event release and schema validation;
review-package reproducibility; 66 Python cells across 21 notebooks (two magic
cells excluded); edited-file diagnostics; whitespace with existing CRLF handling.

Repeat the full local checks with Java available for Spark:

```bash
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL SPARK_LOCAL_IP=127.0.0.1 uv run --with 'pyspark==3.5.7' --with requests python -m unittest discover -s tests -v
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL PYTHONPATH=shared/integrated-test-data/02-emulators/src uv run --with jsonschema python -m unittest discover -s shared/integrated-test-data/02-emulators/tests -v
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv run --with jsonschema python shared/integrated-test-data/generate.py validate
env -u UV_DEFAULT_INDEX -u PIP_INDEX_URL uv run python shared/integrated-test-data/scripts/build_review_package.py check
```

### Deployed Verification: 2026-09-08

- Rebuilt Demo 03 gold tables with notebook job
   `2f824b18-df79-4d64-840e-331b989d8981` (completed), deployed the semantic model
   and report, and refreshed the model.
- Verified Kadena selection: one site, zero critical risks, one open action,
   and exactly the Kadena casework row. Reset restored six sites, two critical
   risks, and six open actions. Fixed a nonblank ranking default that had kept
   excluded sites visible, and added a regression test.
- Verified report rendering and revised authority text. The completion pass
   expanded recovery-table width and increased wrapped typography; raw column
   labels still need polish.
- Deployed the Demo 04 KQL schema and dashboard while preserving the configured
   Eventstream. Enabled raw-table receipt timestamps separately through the KQL
   management API; the Fabric definition importer does not accept that policy.
- Executed the live admission acceptance query: six cases, zero failures.
   Historical raw data contains 75 envelopes, all with receipt timestamps
   between `2026-09-04T20:23:29.9015596Z` and `2026-09-04T20:40:30.4539214Z`.
   Canonical queries return 13 events for the recorded streaming fixture.
- Coverage returns six observed families: four declared and two undeclared,
   with no unobserved declared families. A disjoint post-run window returns no
   coverage rows. These are historical-query checks, not a fresh replay test.
- The last-hour dashboard renders zero raw envelopes and empty charts. Switching
   to the last 14 days populates all five query tiles: 75 raw envelopes, six
   coverage rows, 13 timeline rows, two duration bars (48 and 125 seconds), and
   19 rejected envelopes. The last tile loads when scrolled into view. All five
   exact dashboard queries also passed direct Eventhouse execution.
- Uploaded the generated quick-look and review package to
   `IntegratedTestLakehouse/Files/shared/integrated-test-data/projections/realtime`.
   Their 15-record local fixture is distinct from the historical cloud contents;
   upload does not establish AI grounding or human approval.
- Demo 06 folder inventory contains only the two ontology notebooks, not a
   source-bound Data Agent. Answer acceptance remains `NOT_RUN`.

These initial results are superseded by the
[completion rehearsal record](FABRIC_VERIFICATION.md). Fresh replay recovery and
the controlled mirrored update now pass. The Data Agent is created and bound,
and its original content rejection no longer reproduces. Ontology creation,
all eight instance views, exact history validation, and graph refresh now pass.
The creation notebook also completed with its published dependency Environment.
The root suite now passes 41 tests. All five Agent questions meet their technical
assertions in one fresh-thread run after the join-free source repair; actual
answers and query inspection are recorded. The user authorized Agent publication,
confirmed in Fabric at `2026-09-09T15:26:11Z`. Human-reviewed acceptance remains
pending and is not implied by publication. The original administrative owner was
restored and verified in the semantic model after the rehearsal.

## Subsequent Integration Work

The following remain explicit product boundaries, not implied capabilities:

- The new quarantine-disposition scenario now links an exact streaming source
   record to an administrative finding, with transactional closure tested using
   rollback. The independent Kadena fixture remains a separate incident. See the
   [completion record](FABRIC_VERIFICATION.md) for live linkage evidence.
- An instance-level expected-source registry and independently verified clock/
   observation-window status. Family declarations are only partial coverage.
- Server-enforced reviewer roles and tamper-resistant audit beyond the demo
   review journal. The package deliberately remains pending human review;
   acceptance does not automatically close a finding.
- Human-reviewed Agent acceptance. Source binding and successful technical
   queries alone do not establish human evidence acceptance.