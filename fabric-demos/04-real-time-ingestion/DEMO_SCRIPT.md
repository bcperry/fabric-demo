# Demo 04 Script

1. Name `test-streaming-findings-001` and its recorded replay run. This is not the
	mirrored administrative lead event. Run the notebooks before the audience session.
2. Show the 15 raw records and reconcile 13 canonical events, one duplicate,
	and one rejected envelope. Keep original evidence visible.
3. Trace duplicate source lines 7/8 and the malformed record at line 15. A rejected
	record's reported participant state must not become accepted state evidence.
4. Explain event time, recorded synthetic ingest time, producer publication time,
	and Eventhouse receipt time separately. Accelerated replay is not a latency test.
5. In Eventhouse, select the run's UTC window. Demonstrate disjoint windows,
	declared source families, unobserved families, and undeclared sources. A family
	declaration does not establish a complete inventory of source instances.
6. Show the follow-on deadline `14:05:25Z` versus the last recorded event
	`14:05:05Z`: the result is **UNDETERMINED**, not overdue or failed.
7. Open the [recorded quick-look](../../shared/integrated-test-data/projections/realtime/QUICK_LOOK.md).
	Verify its SHA-256 against the actual raw file. The embedded preservation
	marker is a source claim, not proof. Human review remains pending.

Before using Eventhouse, execute [AcceptanceChecks.kql](fabric-items/kqldb_mda_test.KQLDatabase/AcceptanceChecks.kql)
after deploying the schema; require `Cases=6`, `Failures=0`, `Passed=true`.
Reingest the fixture in a new rehearsal run for receiver-time checks. Existing
raw rows may not have ingestion timestamps, and old typed rows are not rewritten.

Fallback: show the recorded notebook products and generated quick-look; label
Eventhouse delivery and live currency as not demonstrated.

Expected time: 15 minutes.
