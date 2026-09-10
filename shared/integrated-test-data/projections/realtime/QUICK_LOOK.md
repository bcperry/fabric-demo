# Recorded Evidence Quick-Look

Status: **PENDING_HUMAN_REVIEW**. Synthetic analytical review only.

Test: `test-streaming-findings-001`. Run: `run-streaming-findings-001-replay-01`.
Mode: `RECORDED_REPLAY`. Last recorded event: `2026-09-01T14:05:05Z`.

| Reconciliation | Count |
| --- | ---: |
| raw records | 15 |
| admitted records including duplicates | 14 |
| canonical events | 13 |
| duplicate records | 1 |
| rejected records | 1 |

Raw source: [recorded_observed_events.jsonl](recorded_observed_events.jsonl). SHA-256: `c39f40626eab8114c46adde527752470e114f416b696960d8a7dd51c917136b2`.
Rules: [finding_rules.json](finding_rules.json), version `2026.09.01.1`.

## Review Observations

- Duplicate `10000000-0000-4000-8000-000000000007`: source lines 7, 8. Original records retained.
- Rejected envelope: [malformed-event-001](recorded_observed_events.jsonl#L15), `MISSING_SITE_ID`.
- Follow-on `assignment_ack_required`: **UNDETERMINED**. Due `2026-09-01T14:05:25Z`; [trigger evidence](recorded_observed_events.jsonl#L11).

## Limits and Handoff

- A checksum verifies these local bytes, not upstream capture completeness or authenticity.
- The embedded preservation marker is a source claim; its placeholder digest is not used as proof.
- No verified mapping joins this fixture to the administrative lead event or its objectives.
- No recovery, finding closure, participant failure, or execution authorization is established.
- Envelope admission is not full payload-schema or engineering validation.

Reviewer and approval time remain unset. A human reviewer must examine the cited raw evidence and record any disposition separately.
