# Pipeline Guidance

The preferred administrative source path is native Fabric PostgreSQL mirroring
when the selected capacity and region support it. The checked-in fallback path
for this capstone is:

1. Load `../data/postgres_batch_manifest.json`.
2. Ingest each `../data/postgres_*.csv` file in `load_order` sequence.
3. Advance the per-table watermark only after the write and reconciliation succeed.
4. Land `../data/observed_eventstream.jsonl` into Bronze event tables.
5. Shortcut or copy `../data/baseline/**` into the baseline Bronze zone.

Failures should quarantine records rather than silently dropping them.