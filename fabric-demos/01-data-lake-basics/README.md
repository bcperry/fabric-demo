# 01 - Data Lake Basics

Start small: upload a CSV file, inspect it in OneLake, validate its columns, and
save it as a Delta table in `IntegratedTestLakehouse`.

## Demo Data

The input is the checked-in
[`emulated_test_baseline.csv`](../../shared/integrated-test-data/projections/foundation/emulated_test_baseline.csv).
It contains 12 simulated planning records for release `2026.11.03`, including
scenario, test, site, system, objective, required-feed, time, predicted value,
model version, and classification fields.

## Outcome

- **Leadership:** a simple view of whether every objective and required feed is
	represented before test execution.
- **Data professionals:** CSV landing, explicit schema validation, Delta write,
	SQL query, source labels, and repeatable overwrite behavior.

```bash
shared/setup-scripts/fabric_demo_cli.sh push-demo-01
```

Run `01_load_mission_baseline`. It publishes `mission_emulated_baseline`; every
later stage retains the same scenario, test, system, objective, and feed IDs.
