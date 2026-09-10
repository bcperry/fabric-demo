# Demo 06 Script

1. Validate the required Lakehouse facts and dimensions and actually query the
	Eventhouse bindings. A printed table-name checklist is not a connectivity test.
2. Create/update ontology bindings. Separately confirm that a usable Data Agent
	exists and has access to the sources required by [ANSWER_ACCEPTANCE.json](ANSWER_ACCEPTANCE.json).
	The current notebooks create ontology bindings, not a complete agent or evaluation run.
3. Make the recorded review package and its raw/rule sources explicitly available
	through an approved grounding path. A repository file is not automatically an
	agent source. Mark affected cases **NOT READY** until their sources are bound.
4. Ask the acceptance questions verbatim. Inspect the cited record IDs, source
	window, counts, and limitations. Do not accept a plausible uncited paraphrase.
5. Require the incomplete-window answer to remain undetermined, reject an inferred
	relationship to the administrative lead event, and reject invented approval.
6. Record question, full answer, resolved citations, reviewer, and pass/fail for
	every required assertion. Any fabricated evidence or approval fails the demo.

Fallback: show the expected answer and source as a scripted example; never label
it a successful agent run. The closing deliverable is the evidence-backed
quick-look with human review pending, not an unsupported readiness verdict.

Expected time: 15 minutes.
