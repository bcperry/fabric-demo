# Agent Plan - Fabric Pipelines

## Mission

Define orchestration for incremental SQL ingestion, ADLS baseline discovery,
Lakehouse transformations, quality gates, reconciliation, and report readiness.

## Deliverables

- Parameterized pipeline definition or reproducible creation guide.
- SQL watermark extraction using `UpdatedAtUtc`.
- ADLS manifest-driven ingestion.
- Notebook execution order and explicit dependencies.
- Retry policy limited to transient failures.
- Run-log records for start, end, rows, watermarks, status, and error details.
- Quality/reconciliation gates that fail the pipeline visibly.
- Development and demo trigger strategy.

## Acceptance

- Same source batch can be retried safely.
- Watermark advances only after successful downstream commit.
- Poison records quarantine without reporting overall success silently.
- Pipeline can rebuild one run without deleting other runs.
- Demo preflight can determine whether all required stages are current.

