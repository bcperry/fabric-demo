# Agent Plan - Fabric Integration

## Mission

Implement the Fabric-native hot path, medallion model, orchestration, semantic
model, reports, and optional ontology using source-controlled definitions.

## Subsegments

- `eventhouse/AGENT_PLAN.md`: real-time tables, mappings, functions, and queries.
- `lakehouse/AGENT_PLAN.md`: Bronze/Silver/Gold notebooks and reconciliation.
- `pipelines/AGENT_PLAN.md`: SQL/ADLS ingestion and orchestration.
- `semantic-model/AGENT_PLAN.md`: Direct Lake model and report contract.
- `ontology/AGENT_PLAN.md`: optional Fabric IQ package after Silver/Gold freeze.

## Global Fabric rules

- Do not create or modify Fabric items without explicit authorization.
- Definitions must be source-controlled and parameterized.
- Bronze preserves complete source envelopes and payloads.
- Invalid data goes to a visible quarantine path.
- Gold names and measures become contracts for reports and ontology.
- The core story must work without preview or AI features.

## Acceptance

- Every physical table maps to a contract and documented source.
- Source-to-Bronze-to-Silver-to-Gold counts reconcile.
- The scripted anomaly is detected from data rather than hard-coded report state.
- Observed-versus-predicted, readiness, lineage, and quick-look outputs are reproducible.
- All deployment/import instructions support an offline dry-run.

