# Stage 03 Data Model

## Source mapping

| Source file | Row grain | Primary identifiers | Downstream coverage |
| --- | --- | --- | --- |
| `data/scenario_topology.csv` | One component mapped to one system instance at one site for one test event | `scenario_id`, `test_event_id`, `site_id`, `asset_id`, `system_instance_id`, `component_id` | `dim_site`, `dim_asset`, `dim_system_family`, `dim_system_instance`, `dim_component` |
| `data/planned_test_baseline.csv` | One predicted event or target checkpoint | `planned_record_id`, `track_id`, `test_objective_id`, `requirement_id`, `model_version_id` | `dim_track`, `dim_model_version`, baseline-driven reconciliation inputs, expected event times |
| `data/observed_test_events.jsonl` | One observed event envelope | `event_id`, `track_id`, `source_instance_id`, `event_time_utc` | `fact_sensor_observation`, `fact_system_status`, `fact_command_event`, timeline evidence |
| `data/operations_snapshot.csv` | One readiness, feed-health, or configuration snapshot | `snapshot_record_id`, `system_instance_id`, `reported_time_utc` | `fact_readiness_snapshot`, readiness rollups, feed reconciliation context |
| `data/sustainment_actions.jsonl` | One sustainment or corrective action event | `event_id`, `asset_id`, `system_instance_id`, `component_id` | `fact_maintenance_action`, `fact_corrective_action`, maintenance and review workflow |
| `data/governed_measure_catalog.csv` | One governed measure definition | `governed_measure_id`, `test_objective_id`, `requirement_id` | `fact_test_measure`, `fact_finding`, objective evaluation, requirement verification, report sections |

## Dimensions

| Dimension | Natural key | Row grain | Unknown member | SCD policy |
| --- | --- | --- | --- | --- |
| `dim_site` | `site_id` | One site | `site_key = 0` | Type 1 snapshot |
| `dim_asset` | `asset_id` | One sustainment-tracked deployable unit | `asset_key = 0` | Type 1 snapshot |
| `dim_system_family` | `system_family` | One logical family | `system_family_key = 0` | Type 1 snapshot |
| `dim_system_instance` | `system_instance_id` | One participating system instance | `system_instance_key = 0` | Type 1 snapshot |
| `dim_component` | `component_id` | One component attached to one system instance | `component_key = 0` | Type 1 snapshot |
| `dim_scenario` | `scenario_id` | One scenario | `scenario_key = 0` | Type 1 snapshot |
| `dim_test_event` | `test_event_id` | One test event | `test_event_key = 0` | Type 1 snapshot |
| `dim_track` | `track_id` | One governed track identity | `track_key = 0` | Type 1 snapshot |
| `dim_model_version` | `model_version_id` | One calculation or baseline version | `model_version_key = 0` | Type 1 snapshot |
| `dim_test_objective` | `test_objective_id` | One governed objective | `test_objective_key = 0` | Type 1 snapshot |
| `dim_requirement` | `requirement_id` | One governed requirement | `requirement_key = 0` | Type 1 snapshot |
| `dim_data_source` | `data_source_id` | One logical lane or feed | `data_source_key = 0` | Type 1 snapshot |
| `dim_time` | `time_id` | One UTC timestamp at second precision | `time_key = 0` | Type 1 snapshot |

Every dimension carries `effective_from_utc`, `effective_to_utc`, and `is_current` so the compact replay can remain snapshot-oriented without changing the table shape later.

## Facts

| Fact | Row grain | Key pattern | Notes |
| --- | --- | --- | --- |
| `fact_sensor_observation` | One observed sensor event | Scenario, test event, site, asset, system instance, component, track, time | Derived from `sensor.observation` events |
| `fact_system_status` | One observed system-status event | Scenario, test event, site, asset, system instance, component, time | Derived from `system.status` events |
| `fact_command_event` | One observed command event | Scenario, test event, site, asset, system instance, component, track, time | Derived from `command.integration` events |
| `fact_system_participation` | One system instance per test event | Scenario, test event, site, asset, system instance | Rollup from observed events plus latest readiness context |
| `fact_readiness_snapshot` | One readiness snapshot row | Scenario, test event, site, asset, system instance, component, objective, requirement, time | Derived from `READINESS_SNAPSHOT` operations rows |
| `fact_maintenance_action` | One maintenance sustainment event | Scenario, test event, site, asset, system instance, component, objective, requirement, time | Uses only `record_type = MAINTENANCE_ACTION` |
| `fact_test_measure` | One governed measure result | Scenario, test event, objective, requirement, optional track, model version, data source, time | Shared measure layer for quick-look and formal reporting |
| `fact_finding` | One failed governed measure | Scenario, test event, objective, requirement, optional track, model version | Stores evidence IDs in-row as JSON text |
| `fact_objective_evaluation` | One objective per test event | Scenario, test event, objective | Aggregates governed measure status by objective |
| `fact_requirement_verification` | One requirement per test event | Scenario, test event, requirement, objective, optional track | One verification row per governed measure definition |
| `fact_corrective_action` | One corrective-action workflow row | Scenario, test event, site, asset, system instance, component, time | Uses only `record_type = CORRECTIVE_ACTION` |

## Relationship rules

- All event facts join to `dim_scenario`, `dim_test_event`, `dim_data_source`, and `dim_time`.
- Site, asset, system family, system instance, and component relationships are resolved from `scenario_topology.csv` before facts are built.
- Requirement and objective reporting rows come from `fact_test_measure`, not from direct raw-event joins.
- Model version lineage comes from the planned baseline and governed measure catalog only.

## Many-to-many controls

- Findings store `evidence_record_ids_json` in the finding row instead of exploding to an event bridge during the demo.
- `fact_objective_evaluation` groups the governed measures before report products join to findings.
- `fact_requirement_verification` remains one row per governed measure definition, so requirement counts cannot inflate when multiple evidence records are attached.
- `gold_readiness_summary` joins only latest system status and pre-aggregated open maintenance counts.
- `gold_reconciliation_summary` compares planned `comparison_key` values to a single best-match observed record per key.

## Synthetic constraints

- `asset_id` intentionally reuses the same canonical identifier as `system_instance_id` for this compact sustainment story because the shared sustainment contract keys actions by asset identity.
- All timestamps are UTC in the conformed layer even when the operations source also carries a local display time.
- Site names and coordinates use public real-world geography. Operational
	associations, interfaces, tactics, readiness, and capability claims remain
	synthetic demo data.