# Lakehouse Mapping

The local capstone assets define the expected Lakehouse landing and curation
model without creating notebook or pipeline items automatically.

## Bronze

- `bronze_observed_eventstream` from `../data/observed_eventstream.jsonl`
- `bronze_postgres_*` from `../data/postgres_*.csv`
- `bronze_baseline_*` from `../data/baseline/**`

## Silver

- `silver_track_timeline`
- `silver_range_evidence`
- `silver_readiness_history`
- `silver_observed_vs_predicted`
- `silver_findings_lineage`

## Gold

- `gold_quicklook_summary`
- `gold_test_objective_status`
- `gold_next_event_readiness`
- `gold_anomaly_evidence_package`
- `gold_data_trust_summary`

The seeded anomaly should resolve to one delayed assignment acknowledgement with
supporting instrumentation, network, readiness, operator, and advisory safety
evidence.