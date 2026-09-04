from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd

SYNTHETIC_CLASSIFICATION = "SYNTHETIC_UNCLASS"
FICTIONAL_LABEL = "FICTIONAL / DEMO ONLY"
LOCATION_NOTICE = "SYNTHETIC / NOT FOR NAVIGATION"
SNAPSHOT_EFFECTIVE_FROM = "2026-11-03T00:00:00Z"
REPORT_TIMESTAMP_UTC = "2026-11-03T10:15:00Z"

SOURCE_FILES = {
    "scenario_topology": "scenario_topology.csv",
    "planned_test_baseline": "planned_test_baseline.csv",
    "observed_test_events": "observed_test_events.jsonl",
    "operations_snapshot": "operations_snapshot.csv",
    "sustainment_actions": "sustainment_actions.jsonl",
    "governed_measure_catalog": "governed_measure_catalog.csv",
}

EXPECTED_SOURCE_COUNTS = {
    "scenario_topology": 9,
    "planned_test_baseline": 8,
    "observed_test_events": 15,
    "operations_snapshot": 8,
    "sustainment_actions": 7,
    "governed_measure_catalog": 6,
}

EXPECTED_FACT_COUNTS = {
    "fact_sensor_observation": 2,
    "fact_system_status": 7,
    "fact_command_event": 4,
    "fact_system_participation": 7,
    "fact_readiness_snapshot": 4,
    "fact_maintenance_action": 3,
    "fact_test_measure": 6,
    "fact_finding": 4,
    "fact_objective_evaluation": 5,
    "fact_requirement_verification": 6,
    "fact_corrective_action": 4,
}

EXPECTED_PRODUCT_NAMES = [
    "gold_integrated_timeline",
    "gold_readiness_summary",
    "gold_finding_register",
    "gold_objective_status",
    "gold_requirement_verification_report",
    "gold_reconciliation_summary",
    "gold_lessons_learned",
    "gold_quick_look_summary",
    "gold_formal_report_summary",
]

DATA_SOURCE_METADATA = {
    "feed-scenario-topology": ("Scenario topology snapshot", "reference"),
    "feed-sensor-observation": ("Observed sensor replay lane", "observed"),
    "feed-command-integration": ("Observed command replay lane", "observed"),
    "feed-system-status": ("Observed status replay lane", "observed"),
    "feed-sustainment": ("Sustainment action lane", "operations"),
    "feed-operations-snapshot": ("Operations snapshot lane", "operations"),
}

SYSTEM_FAMILY_GROUP = {
    "TPY2": "sensor",
    "BATTLE_MANAGEMENT": "integration",
    "ARMY_INTEGRATION": "integration",
    "PATRIOT": "participant",
    "THAAD": "participant",
}

MEASURE_TO_EVIDENCE = {
    "gm-observation-latency-001": ["plan-001", "51000000-0000-4000-8000-000000000002"],
    "gm-track-continuity-001": [
        "plan-002",
        "51000000-0000-4000-8000-000000000002",
        "51000000-0000-4000-8000-000000000003",
    ],
    "gm-shared-track-latency-001": [
        "plan-003",
        "51000000-0000-4000-8000-000000000004",
        "ops-008",
    ],
    "gm-correlation-window-001": [
        "plan-004",
        "51000000-0000-4000-8000-000000000005",
        "52000000-0000-4000-8000-000000000005",
    ],
    "gm-readiness-coverage-001": [
        "ops-001",
        "ops-002",
        "ops-003",
        "ops-004",
        "51000000-0000-4000-8000-00000000000c",
    ],
    "gm-maintenance-open-actions-001": [
        "plan-008",
        "52000000-0000-4000-8000-000000000001",
        "52000000-0000-4000-8000-000000000002",
        "52000000-0000-4000-8000-000000000003",
    ],
}


def demo_root() -> Path:
    return Path(__file__).resolve().parent


def data_root(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        return Path(base_dir).resolve()
    return demo_root() / "data"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def _normalize_numeric(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _normalize_timestamps(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    return frame


def spark_compatible_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        series = result[column]
        if isinstance(series.dtype, pd.DatetimeTZDtype):
            series = series.dt.tz_convert("UTC").dt.tz_localize(None)
        if pd.api.types.is_datetime64_any_dtype(series.dtype) or pd.api.types.is_float_dtype(series.dtype):
            result[column] = series.astype(object).where(series.notna(), None)
        elif pd.api.types.is_object_dtype(series.dtype) and series.map(
            lambda value: isinstance(value, (dict, list))
        ).any():
            result[column] = series.map(
                lambda value: json.dumps(value) if isinstance(value, (dict, list)) else value
            )
    return result


def load_sources(base_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    root = data_root(base_dir)

    sources = {
        "scenario_topology": _load_csv(root / SOURCE_FILES["scenario_topology"]),
        "planned_test_baseline": _load_csv(root / SOURCE_FILES["planned_test_baseline"]),
        "operations_snapshot": _load_csv(root / SOURCE_FILES["operations_snapshot"]),
        "governed_measure_catalog": _load_csv(root / SOURCE_FILES["governed_measure_catalog"]),
        "observed_test_events": pd.json_normalize(
            _read_jsonl(root / SOURCE_FILES["observed_test_events"]),
            sep=".",
        ).fillna(""),
        "sustainment_actions": pd.json_normalize(
            _read_jsonl(root / SOURCE_FILES["sustainment_actions"]),
            sep=".",
        ).fillna(""),
    }

    _normalize_numeric(
        sources["planned_test_baseline"],
        ["predicted_value"],
    )
    _normalize_numeric(
        sources["operations_snapshot"],
        ["utc_offset_minutes", "measure_value"],
    )
    _normalize_numeric(
        sources["governed_measure_catalog"],
        ["threshold_value", "quick_look_order"],
    )
    _normalize_numeric(
        sources["observed_test_events"],
        [
            "sequence_number",
            "quality.score",
            "quality.freshness_ms",
            "quality.continuity",
            "position.x",
            "position.y",
            "position.z",
            "processing_delay_ms",
            "health_score",
            "metrics.stability_index",
            "metrics.alignment_index",
        ],
    )
    _normalize_numeric(
        sources["sustainment_actions"],
        ["sequence_number", "details.maintenance_minutes"],
    )

    _normalize_timestamps(
        sources["planned_test_baseline"],
        ["planned_event_time_utc"],
    )
    _normalize_timestamps(
        sources["operations_snapshot"],
        ["reported_time_utc"],
    )
    _normalize_timestamps(
        sources["governed_measure_catalog"],
        [],
    )
    _normalize_timestamps(
        sources["observed_test_events"],
        ["event_time_utc", "ingest_time_utc"],
    )
    _normalize_timestamps(
        sources["sustainment_actions"],
        ["event_time_utc", "ingest_time_utc", "details.due_time_utc"],
    )

    return sources


def validate_source_frames(sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    checks: list[dict[str, object]] = []

    for lane_name, expected_count in EXPECTED_SOURCE_COUNTS.items():
        observed_count = len(sources[lane_name])
        checks.append(
            {
                "check_name": f"{lane_name}_row_count",
                "passed": observed_count == expected_count,
                "observed_value": observed_count,
                "expected_value": expected_count,
            }
        )
        if "classification" in sources[lane_name].columns:
            distinct_classifications = sorted(
                set(value for value in sources[lane_name]["classification"].astype(str).tolist() if value)
            )
            checks.append(
                {
                    "check_name": f"{lane_name}_classification",
                    "passed": distinct_classifications == [SYNTHETIC_CLASSIFICATION],
                    "observed_value": ",".join(distinct_classifications),
                    "expected_value": SYNTHETIC_CLASSIFICATION,
                }
            )

    topology = sources["scenario_topology"]
    observed = sources["observed_test_events"]
    baseline = sources["planned_test_baseline"]
    operations = sources["operations_snapshot"]
    sustainment = sources["sustainment_actions"]
    measure_catalog = sources["governed_measure_catalog"]

    valid_site_ids = set(topology["site_id"])
    valid_system_ids = set(topology["system_instance_id"])
    valid_asset_ids = set(topology["asset_id"])
    valid_component_ids = set(topology["component_id"])
    valid_track_ids = set(baseline["track_id"])
    valid_objective_ids = set(measure_catalog["test_objective_id"])
    valid_requirement_ids = set(measure_catalog["requirement_id"])

    checks.extend(
        [
            _set_membership_check(
                "baseline_site_ids",
                set(baseline["site_id"]),
                valid_site_ids,
            ),
            _set_membership_check(
                "baseline_system_ids",
                set(baseline["system_instance_id"]),
                valid_system_ids,
            ),
            _set_membership_check(
                "baseline_component_ids",
                set(baseline["component_id"]),
                valid_component_ids,
            ),
            _set_membership_check(
                "baseline_objective_ids",
                set(baseline["test_objective_id"]),
                valid_objective_ids,
            ),
            _set_membership_check(
                "baseline_requirement_ids",
                set(baseline["requirement_id"]),
                valid_requirement_ids,
            ),
            _set_membership_check(
                "operations_system_ids",
                set(value for value in operations["system_instance_id"] if value),
                valid_system_ids,
            ),
            _set_membership_check(
                "operations_component_ids",
                set(value for value in operations["component_id"] if value),
                valid_component_ids,
            ),
            _set_membership_check(
                "operations_asset_ids",
                set(value for value in operations["asset_id"] if value),
                valid_asset_ids,
            ),
            _set_membership_check(
                "sustainment_system_ids",
                set(sustainment["system_instance_id"]),
                valid_system_ids,
            ),
            _set_membership_check(
                "sustainment_component_ids",
                set(sustainment["component_id"]),
                valid_component_ids,
            ),
            _set_membership_check(
                "sustainment_asset_ids",
                set(sustainment["asset_id"]),
                valid_asset_ids,
            ),
            _set_membership_check(
                "observed_track_ids",
                set(value for value in observed.get("track_id", pd.Series(dtype=str)).astype(str).tolist() if value),
                valid_track_ids,
            ),
            _set_membership_check(
                "observed_site_ids",
                set(
                    value
                    for value in observed.loc[
                        observed["event_type"] != "test.marker",
                        "site_id",
                    ].astype(str).tolist()
                    if value
                ),
                valid_site_ids,
            ),
            _set_membership_check(
                "observed_system_ids",
                set(
                    value
                    for value in observed.loc[
                        observed["event_type"] != "test.marker",
                        "source_instance_id",
                    ].astype(str).tolist()
                    if value
                ),
                valid_system_ids,
            ),
        ]
    )

    return pd.DataFrame(checks)


def _set_membership_check(check_name: str, observed_values: set[str], valid_values: set[str]) -> dict[str, object]:
    unexpected_values = sorted(value for value in observed_values if value not in valid_values)
    return {
        "check_name": check_name,
        "passed": not unexpected_values,
        "observed_value": ",".join(unexpected_values) if unexpected_values else "OK",
        "expected_value": "subset-of-reference",
    }


def _add_unknown_member(frame: pd.DataFrame, key_column: str, natural_key: str, unknown_value: str, label_values: dict[str, object]) -> pd.DataFrame:
    ordered = frame.reset_index(drop=True).copy()
    ordered.insert(0, key_column, range(1, len(ordered) + 1))
    unknown_row = {column: "" for column in ordered.columns}
    unknown_row[key_column] = 0
    unknown_row[natural_key] = unknown_value
    unknown_row.update(label_values)
    unknown_row.setdefault("scd_policy", "UNKNOWN_MEMBER")
    unknown_row.setdefault("effective_from_utc", "1970-01-01T00:00:00Z")
    unknown_row.setdefault("effective_to_utc", "")
    unknown_row.setdefault("is_current", True)
    return pd.concat([pd.DataFrame([unknown_row]), ordered], ignore_index=True)


def _finalize_dimension(frame: pd.DataFrame, key_column: str, natural_key: str, unknown_value: str, label_values: dict[str, object]) -> pd.DataFrame:
    finalized = frame.copy()
    finalized["scd_policy"] = finalized.get("scd_policy", "TYPE1_SNAPSHOT")
    finalized["effective_from_utc"] = finalized.get("effective_from_utc", SNAPSHOT_EFFECTIVE_FROM)
    finalized["effective_to_utc"] = finalized.get("effective_to_utc", "")
    finalized["is_current"] = finalized.get("is_current", True)
    return _add_unknown_member(finalized, key_column, natural_key, unknown_value, label_values)


def build_dimensions(sources: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    topology = sources["scenario_topology"]
    baseline = sources["planned_test_baseline"]
    observed = sources["observed_test_events"]
    operations = sources["operations_snapshot"]
    sustainment = sources["sustainment_actions"]
    measure_catalog = sources["governed_measure_catalog"]

    dim_site = _finalize_dimension(
        topology[["site_id", "site_name", "classification", "location_notice"]]
        .drop_duplicates()
        .sort_values(["site_id"]),
        "site_key",
        "site_id",
        "unknown-site",
        {
            "site_name": "Unknown Site",
            "classification": SYNTHETIC_CLASSIFICATION,
            "location_notice": LOCATION_NOTICE,
        },
    )

    asset_rows = (
        topology[["asset_id", "asset_name", "site_id", "system_family", "classification"]]
        .drop_duplicates()
        .sort_values(["asset_id"])
        .assign(asset_type="DEPLOYABLE_UNIT")
    )
    dim_asset = _finalize_dimension(
        asset_rows,
        "asset_key",
        "asset_id",
        "unknown-asset",
        {
            "asset_name": "Unknown Asset",
            "site_id": "unknown-site",
            "system_family": "UNKNOWN",
            "classification": SYNTHETIC_CLASSIFICATION,
            "asset_type": "UNKNOWN",
        },
    )

    family_rows = (
        topology[["system_family", "classification"]]
        .drop_duplicates()
        .sort_values(["system_family"])
        .assign(system_group=lambda frame: frame["system_family"].map(SYSTEM_FAMILY_GROUP))
    )
    dim_system_family = _finalize_dimension(
        family_rows,
        "system_family_key",
        "system_family",
        "UNKNOWN",
        {
            "classification": SYNTHETIC_CLASSIFICATION,
            "system_group": "unknown",
        },
    )

    instance_rows = (
        topology[["system_instance_id", "asset_id", "site_id", "system_family", "classification"]]
        .drop_duplicates()
        .sort_values(["system_instance_id"])
    )
    primary_components = (
        topology.sort_values(["system_instance_id", "component_id"])
        .drop_duplicates(["system_instance_id"])
        [["system_instance_id", "component_id", "component_role", "component_state"]]
    )
    instance_rows = instance_rows.merge(primary_components, on="system_instance_id", how="left")
    dim_system_instance = _finalize_dimension(
        instance_rows,
        "system_instance_key",
        "system_instance_id",
        "unknown-system-instance",
        {
            "asset_id": "unknown-asset",
            "site_id": "unknown-site",
            "system_family": "UNKNOWN",
            "classification": SYNTHETIC_CLASSIFICATION,
            "component_id": "unknown-component",
            "component_role": "UNKNOWN",
            "component_state": "UNKNOWN",
        },
    )

    component_rows = (
        topology[
            [
                "component_id",
                "component_name",
                "component_role",
                "component_state",
                "system_instance_id",
                "asset_id",
                "site_id",
                "classification",
            ]
        ]
        .drop_duplicates()
        .sort_values(["component_id"])
    )
    dim_component = _finalize_dimension(
        component_rows,
        "component_key",
        "component_id",
        "unknown-component",
        {
            "component_name": "Unknown Component",
            "component_role": "UNKNOWN",
            "component_state": "UNKNOWN",
            "system_instance_id": "unknown-system-instance",
            "asset_id": "unknown-asset",
            "site_id": "unknown-site",
            "classification": SYNTHETIC_CLASSIFICATION,
        },
    )

    scenario_rows = pd.DataFrame(
        {
            "scenario_id": sorted(set(baseline["scenario_id"]).union(observed["scenario_id"]).union(operations["scenario_id"]).union(sustainment["scenario_id"]).union(measure_catalog["scenario_id"])),
        }
    )
    scenario_rows["scenario_name"] = scenario_rows["scenario_id"].map(
        {"integrated-defense-001": "Fictional Integrated Defense Test 001"}
    ).fillna("Synthetic Scenario")
    scenario_rows["classification"] = SYNTHETIC_CLASSIFICATION
    dim_scenario = _finalize_dimension(
        scenario_rows.sort_values(["scenario_id"]),
        "scenario_key",
        "scenario_id",
        "unknown-scenario",
        {
            "scenario_name": "Unknown Scenario",
            "classification": SYNTHETIC_CLASSIFICATION,
        },
    )

    test_event_rows = pd.DataFrame(
        {
            "test_event_id": sorted(set(baseline["test_event_id"]).union(observed["test_event_id"]).union(operations["test_event_id"]).union(sustainment["test_event_id"]).union(measure_catalog["test_event_id"])),
        }
    )
    test_event_rows["scenario_id"] = "integrated-defense-001"
    test_event_rows["test_event_name"] = "Integrated Defense Analysis and Reporting Window"
    test_event_rows["classification"] = SYNTHETIC_CLASSIFICATION
    dim_test_event = _finalize_dimension(
        test_event_rows.sort_values(["test_event_id"]),
        "test_event_key",
        "test_event_id",
        "unknown-test-event",
        {
            "scenario_id": "unknown-scenario",
            "test_event_name": "Unknown Test Event",
            "classification": SYNTHETIC_CLASSIFICATION,
        },
    )

    track_ids = sorted(
        {
            value
            for value in pd.concat(
                [baseline["track_id"], observed.get("track_id", pd.Series(dtype=str))],
                ignore_index=True,
            ).astype(str)
            if value
        }
    )
    track_rows = pd.DataFrame({"track_id": track_ids})
    track_rows["scenario_id"] = "integrated-defense-001"
    track_rows["track_role"] = "PRIMARY_SYNTHETIC_TRACK"
    track_rows["classification"] = SYNTHETIC_CLASSIFICATION
    dim_track = _finalize_dimension(
        track_rows,
        "track_key",
        "track_id",
        "unknown-track",
        {
            "scenario_id": "unknown-scenario",
            "track_role": "UNKNOWN",
            "classification": SYNTHETIC_CLASSIFICATION,
        },
    )

    version_rows = pd.DataFrame(
        {
            "model_version_id": sorted(set(baseline["model_version_id"]).union(measure_catalog["model_version_id"])),
        }
    )
    version_rows["version_role"] = version_rows["model_version_id"].map(
        lambda value: "planning" if str(value).startswith("planning") else "governance"
    )
    version_rows["classification"] = SYNTHETIC_CLASSIFICATION
    dim_model_version = _finalize_dimension(
        version_rows,
        "model_version_key",
        "model_version_id",
        "unknown-model-version",
        {
            "version_role": "unknown",
            "classification": SYNTHETIC_CLASSIFICATION,
        },
    )

    objective_rows = (
        measure_catalog[
            [
                "test_objective_id",
                "test_objective_name",
                "formal_report_section",
                "classification",
            ]
        ]
        .drop_duplicates()
        .sort_values(["test_objective_id"])
    )
    dim_test_objective = _finalize_dimension(
        objective_rows,
        "test_objective_key",
        "test_objective_id",
        "unknown-objective",
        {
            "test_objective_name": "Unknown Objective",
            "formal_report_section": "Unknown",
            "classification": SYNTHETIC_CLASSIFICATION,
        },
    )

    requirement_rows = (
        measure_catalog[
            [
                "requirement_id",
                "requirement_name",
                "test_objective_id",
                "measure_group",
                "classification",
            ]
        ]
        .drop_duplicates()
        .sort_values(["requirement_id"])
    )
    dim_requirement = _finalize_dimension(
        requirement_rows,
        "requirement_key",
        "requirement_id",
        "unknown-requirement",
        {
            "requirement_name": "Unknown Requirement",
            "test_objective_id": "unknown-objective",
            "measure_group": "unknown",
            "classification": SYNTHETIC_CLASSIFICATION,
        },
    )

    source_rows = pd.DataFrame(
        [
            {
                "data_source_id": data_source_id,
                "data_source_name": metadata[0],
                "source_lane": metadata[1],
                "classification": SYNTHETIC_CLASSIFICATION,
            }
            for data_source_id, metadata in sorted(DATA_SOURCE_METADATA.items())
        ]
    )
    dim_data_source = _finalize_dimension(
        source_rows,
        "data_source_key",
        "data_source_id",
        "unknown-data-source",
        {
            "data_source_name": "Unknown Data Source",
            "source_lane": "unknown",
            "classification": SYNTHETIC_CLASSIFICATION,
        },
    )

    time_values = pd.Series(dtype="datetime64[ns, UTC]")
    for frame, columns in [
        (baseline, ["planned_event_time_utc"]),
        (observed, ["event_time_utc", "ingest_time_utc"]),
        (operations, ["reported_time_utc"]),
        (sustainment, ["event_time_utc", "ingest_time_utc", "details.due_time_utc"]),
    ]:
        for column in columns:
            if column in frame.columns:
                time_values = pd.concat([time_values, frame[column]], ignore_index=True)
    time_values = pd.concat(
        [time_values, pd.Series([pd.Timestamp(REPORT_TIMESTAMP_UTC)])],
        ignore_index=True,
    )
    time_values = time_values.dropna().drop_duplicates().sort_values().reset_index(drop=True)
    time_rows = pd.DataFrame({"time_utc": time_values})
    time_rows["time_id"] = time_rows["time_utc"].dt.strftime("%Y%m%d%H%M%S")
    time_rows["calendar_date"] = time_rows["time_utc"].dt.strftime("%Y-%m-%d")
    time_rows["hour_utc"] = time_rows["time_utc"].dt.hour
    time_rows["minute_utc"] = time_rows["time_utc"].dt.minute
    time_rows["second_utc"] = time_rows["time_utc"].dt.second
    time_rows["day_name"] = time_rows["time_utc"].dt.day_name()
    time_rows["classification"] = SYNTHETIC_CLASSIFICATION
    time_rows["time_utc"] = time_rows["time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    dim_time = _finalize_dimension(
        time_rows[["time_id", "time_utc", "calendar_date", "hour_utc", "minute_utc", "second_utc", "day_name", "classification"]],
        "time_key",
        "time_id",
        "0",
        {
            "time_utc": "1970-01-01T00:00:00Z",
            "calendar_date": "1970-01-01",
            "hour_utc": 0,
            "minute_utc": 0,
            "second_utc": 0,
            "day_name": "Thursday",
            "classification": SYNTHETIC_CLASSIFICATION,
        },
    )

    return {
        "dim_site": dim_site,
        "dim_asset": dim_asset,
        "dim_system_family": dim_system_family,
        "dim_system_instance": dim_system_instance,
        "dim_component": dim_component,
        "dim_scenario": dim_scenario,
        "dim_test_event": dim_test_event,
        "dim_track": dim_track,
        "dim_model_version": dim_model_version,
        "dim_test_objective": dim_test_objective,
        "dim_requirement": dim_requirement,
        "dim_data_source": dim_data_source,
        "dim_time": dim_time,
    }


def validate_dimensions(sources: dict[str, pd.DataFrame], dimensions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    checks: list[dict[str, object]] = []
    natural_key_columns = {
        "dim_site": "site_id",
        "dim_asset": "asset_id",
        "dim_system_family": "system_family",
        "dim_system_instance": "system_instance_id",
        "dim_component": "component_id",
        "dim_scenario": "scenario_id",
        "dim_test_event": "test_event_id",
        "dim_track": "track_id",
        "dim_model_version": "model_version_id",
        "dim_test_objective": "test_objective_id",
        "dim_requirement": "requirement_id",
        "dim_data_source": "data_source_id",
        "dim_time": "time_id",
    }

    for dimension_name, natural_key in natural_key_columns.items():
        frame = dimensions[dimension_name]
        duplicates = frame.loc[frame[natural_key].ne(frame.iloc[0][natural_key])].duplicated(natural_key).sum()
        checks.append(
            {
                "check_name": f"{dimension_name}_unique_{natural_key}",
                "passed": duplicates == 0,
                "observed_value": int(duplicates),
                "expected_value": 0,
            }
        )
        checks.append(
            {
                "check_name": f"{dimension_name}_unknown_member",
                "passed": int(frame.iloc[0, 0]) == 0,
                "observed_value": int(frame.iloc[0, 0]),
                "expected_value": 0,
            }
        )

    source_checks = validate_source_frames(sources)
    checks.extend(source_checks.to_dict("records"))
    return pd.DataFrame(checks).drop_duplicates(subset=["check_name"], keep="first")


def _key_map(frame: pd.DataFrame, natural_key: str, key_column: str) -> dict[str, int]:
    return dict(zip(frame[natural_key].astype(str), frame[key_column].astype(int)))


def _lookup_key(values: pd.Series, mapping: dict[str, int], unknown_key: int = 0) -> pd.Series:
    return values.astype(str).map(mapping).fillna(unknown_key).astype(int)


def _time_key(series: pd.Series, time_mapping: dict[str, int]) -> pd.Series:
    formatted = pd.to_datetime(series, utc=True, errors="coerce").dt.strftime("%Y%m%d%H%M%S").fillna("0")
    return _lookup_key(formatted, time_mapping)


def _preferred_component_lookup(topology: pd.DataFrame, preferred_roles: list[str]) -> dict[str, str]:
    preferred = topology[topology["component_role"].isin(preferred_roles)].copy()
    if preferred.empty:
        preferred = topology.copy()
    preferred = preferred.sort_values(["system_instance_id", "component_id"]).drop_duplicates(["system_instance_id"])
    return dict(zip(preferred["system_instance_id"], preferred["component_id"]))


def _measure_status(actual_value: float, threshold_direction: str, threshold_value: float) -> str:
    if threshold_direction == "<=":
        return "PASS" if actual_value <= threshold_value else "FAIL"
    if threshold_direction == ">=":
        return "PASS" if actual_value >= threshold_value else "FAIL"
    raise ValueError(f"Unsupported threshold direction: {threshold_direction}")


def build_facts(sources: dict[str, pd.DataFrame], dimensions: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    topology = sources["scenario_topology"]
    baseline = sources["planned_test_baseline"]
    observed = sources["observed_test_events"]
    operations = sources["operations_snapshot"]
    sustainment = sources["sustainment_actions"]
    measure_catalog = sources["governed_measure_catalog"]

    site_map = _key_map(dimensions["dim_site"], "site_id", "site_key")
    asset_map = _key_map(dimensions["dim_asset"], "asset_id", "asset_key")
    family_map = _key_map(dimensions["dim_system_family"], "system_family", "system_family_key")
    instance_map = _key_map(dimensions["dim_system_instance"], "system_instance_id", "system_instance_key")
    component_map = _key_map(dimensions["dim_component"], "component_id", "component_key")
    scenario_map = _key_map(dimensions["dim_scenario"], "scenario_id", "scenario_key")
    event_map = _key_map(dimensions["dim_test_event"], "test_event_id", "test_event_key")
    track_map = _key_map(dimensions["dim_track"], "track_id", "track_key")
    version_map = _key_map(dimensions["dim_model_version"], "model_version_id", "model_version_key")
    objective_map = _key_map(dimensions["dim_test_objective"], "test_objective_id", "test_objective_key")
    requirement_map = _key_map(dimensions["dim_requirement"], "requirement_id", "requirement_key")
    data_source_map = _key_map(dimensions["dim_data_source"], "data_source_id", "data_source_key")
    time_map = _key_map(dimensions["dim_time"], "time_id", "time_key")

    system_to_family = dict(zip(topology["system_instance_id"], topology["system_family"]))
    system_to_asset = dict(zip(topology["system_instance_id"], topology["asset_id"]))
    command_component_lookup = _preferred_component_lookup(topology, ["CORRELATION_SERVICE", "RELAY_FABRIC", "FIRE_CONTROL"])
    sensor_component_lookup = _preferred_component_lookup(topology, ["OBSERVATION_ARRAY", "ORGANIC_RADAR"])
    status_component_lookup = _preferred_component_lookup(topology, ["LAUNCHER_CONTROLLER", "FIRE_CONTROL", "CORRELATION_SERVICE", "TIME_ALIGNMENT"])

    sensor_frame = observed[observed["event_type"] == "sensor.observation"].copy().sort_values(["event_time_utc", "event_id"])
    sensor_frame["asset_id"] = sensor_frame["source_instance_id"].map(system_to_asset)
    sensor_frame["component_id"] = sensor_frame["source_instance_id"].map(sensor_component_lookup)
    sensor_frame["system_family"] = sensor_frame["source_instance_id"].map(system_to_family)
    sensor_frame["data_source_id"] = "feed-sensor-observation"
    fact_sensor_observation = sensor_frame.assign(
        scenario_key=_lookup_key(sensor_frame["scenario_id"], scenario_map),
        test_event_key=_lookup_key(sensor_frame["test_event_id"], event_map),
        site_key=_lookup_key(sensor_frame["site_id"], site_map),
        asset_key=_lookup_key(sensor_frame["asset_id"], asset_map),
        system_family_key=_lookup_key(sensor_frame["system_family"], family_map),
        system_instance_key=_lookup_key(sensor_frame["source_instance_id"], instance_map),
        component_key=_lookup_key(sensor_frame["component_id"], component_map),
        track_key=_lookup_key(sensor_frame["track_id"], track_map),
        data_source_key=_lookup_key(sensor_frame["data_source_id"], data_source_map),
        time_key=_time_key(sensor_frame["event_time_utc"], time_map),
        model_version_key=0,
    )[
        [
            "event_id",
            "scenario_key",
            "test_event_key",
            "site_key",
            "asset_key",
            "system_family_key",
            "system_instance_key",
            "component_key",
            "track_key",
            "data_source_key",
            "time_key",
            "model_version_key",
            "scenario_id",
            "test_event_id",
            "site_id",
            "asset_id",
            "source_instance_id",
            "component_id",
            "track_id",
            "event_time_utc",
            "observation_type",
            "quality.score",
            "quality.freshness_ms",
            "quality.continuity",
            "position.x",
            "position.y",
            "position.z",
            "classification",
        ]
    ].rename(
        columns={
            "source_instance_id": "system_instance_id",
            "quality.score": "quality_score",
            "quality.freshness_ms": "freshness_ms",
            "quality.continuity": "continuity_ratio",
            "position.x": "position_x",
            "position.y": "position_y",
            "position.z": "position_z",
        }
    )

    status_frame = observed[observed["event_type"] == "system.status"].copy().sort_values(["event_time_utc", "event_id"])
    status_frame["asset_id"] = status_frame["source_instance_id"].map(system_to_asset)
    status_frame["component_id"] = status_frame["source_instance_id"].map(status_component_lookup)
    status_frame["system_family"] = status_frame["source_instance_id"].map(system_to_family)
    status_frame["data_source_id"] = "feed-system-status"
    fact_system_status = status_frame.assign(
        scenario_key=_lookup_key(status_frame["scenario_id"], scenario_map),
        test_event_key=_lookup_key(status_frame["test_event_id"], event_map),
        site_key=_lookup_key(status_frame["site_id"], site_map),
        asset_key=_lookup_key(status_frame["asset_id"], asset_map),
        system_family_key=_lookup_key(status_frame["system_family"], family_map),
        system_instance_key=_lookup_key(status_frame["source_instance_id"], instance_map),
        component_key=_lookup_key(status_frame["component_id"], component_map),
        track_key=0,
        track_id="",
        data_source_key=_lookup_key(status_frame["data_source_id"], data_source_map),
        time_key=_time_key(status_frame["event_time_utc"], time_map),
        model_version_key=0,
    )[
        [
            "event_id",
            "scenario_key",
            "test_event_key",
            "site_key",
            "asset_key",
            "system_family_key",
            "system_instance_key",
            "component_key",
            "track_key",
            "data_source_key",
            "time_key",
            "model_version_key",
            "scenario_id",
            "test_event_id",
            "site_id",
            "asset_id",
            "source_instance_id",
            "component_id",
            "track_id",
            "event_time_utc",
            "operating_state",
            "readiness_state",
            "health_score",
            "metrics.stability_index",
            "metrics.alignment_index",
            "classification",
        ]
    ].rename(
        columns={
            "source_instance_id": "system_instance_id",
            "metrics.stability_index": "stability_index",
            "metrics.alignment_index": "alignment_index",
        }
    )

    command_frame = observed[observed["event_type"] == "command.integration"].copy().sort_values(["event_time_utc", "event_id"])
    command_frame["asset_id"] = command_frame["source_instance_id"].map(system_to_asset)
    command_frame["component_id"] = command_frame["source_instance_id"].map(command_component_lookup)
    command_frame["system_family"] = command_frame["source_instance_id"].map(system_to_family)
    command_frame["data_source_id"] = "feed-command-integration"
    fact_command_event = command_frame.assign(
        scenario_key=_lookup_key(command_frame["scenario_id"], scenario_map),
        test_event_key=_lookup_key(command_frame["test_event_id"], event_map),
        site_key=_lookup_key(command_frame["site_id"], site_map),
        asset_key=_lookup_key(command_frame["asset_id"], asset_map),
        system_family_key=_lookup_key(command_frame["system_family"], family_map),
        system_instance_key=_lookup_key(command_frame["source_instance_id"], instance_map),
        component_key=_lookup_key(command_frame["component_id"], component_map),
        track_key=_lookup_key(command_frame["track_id"], track_map),
        data_source_key=_lookup_key(command_frame["data_source_id"], data_source_map),
        time_key=_time_key(command_frame["event_time_utc"], time_map),
        model_version_key=0,
    )[
        [
            "event_id",
            "scenario_key",
            "test_event_key",
            "site_key",
            "asset_key",
            "system_family_key",
            "system_instance_key",
            "component_key",
            "track_key",
            "data_source_key",
            "time_key",
            "model_version_key",
            "scenario_id",
            "test_event_id",
            "site_id",
            "asset_id",
            "source_instance_id",
            "component_id",
            "track_id",
            "event_time_utc",
            "action",
            "status",
            "target_instance_id",
            "processing_delay_ms",
            "classification",
        ]
    ].rename(
        columns={
            "source_instance_id": "system_instance_id",
            "processing_delay_ms": "processing_delay_milliseconds",
        }
    )
    fact_command_event["processing_delay_seconds"] = (
        fact_command_event["processing_delay_milliseconds"] / 1000.0
    )

    readiness_frame = operations[operations["record_type"] == "READINESS_SNAPSHOT"].copy().sort_values(["reported_time_utc", "snapshot_record_id"])
    readiness_frame["system_family"] = readiness_frame["system_instance_id"].map(system_to_family)
    fact_readiness_snapshot = readiness_frame.assign(
        scenario_key=_lookup_key(readiness_frame["scenario_id"], scenario_map),
        test_event_key=_lookup_key(readiness_frame["test_event_id"], event_map),
        site_key=_lookup_key(readiness_frame["site_id"], site_map),
        asset_key=_lookup_key(readiness_frame["asset_id"], asset_map),
        system_family_key=_lookup_key(readiness_frame["system_family"], family_map),
        system_instance_key=_lookup_key(readiness_frame["system_instance_id"], instance_map),
        component_key=_lookup_key(readiness_frame["component_id"], component_map),
        track_key=0,
        data_source_key=_lookup_key(readiness_frame["data_source_id"], data_source_map),
        time_key=_time_key(readiness_frame["reported_time_utc"], time_map),
        model_version_key=0,
        test_objective_key=_lookup_key(readiness_frame["test_objective_id"], objective_map),
        requirement_key=_lookup_key(readiness_frame["requirement_id"], requirement_map),
    )[
        [
            "snapshot_record_id",
            "scenario_key",
            "test_event_key",
            "site_key",
            "asset_key",
            "system_family_key",
            "system_instance_key",
            "component_key",
            "track_key",
            "data_source_key",
            "time_key",
            "model_version_key",
            "test_objective_key",
            "requirement_key",
            "scenario_id",
            "test_event_id",
            "site_id",
            "asset_id",
            "system_instance_id",
            "component_id",
            "reported_time_utc",
            "reported_state",
            "expected_state",
            "measure_value",
            "review_status",
            "classification",
        ]
    ].rename(columns={"measure_value": "readiness_score"})

    maintenance_frame = sustainment[sustainment["record_type"] == "MAINTENANCE_ACTION"].copy().sort_values(["event_time_utc", "event_id"])
    maintenance_frame["system_family"] = maintenance_frame["system_instance_id"].map(system_to_family)
    fact_maintenance_action = maintenance_frame.assign(
        scenario_key=_lookup_key(maintenance_frame["scenario_id"], scenario_map),
        test_event_key=_lookup_key(maintenance_frame["test_event_id"], event_map),
        site_key=_lookup_key(maintenance_frame["site_id"], site_map),
        asset_key=_lookup_key(maintenance_frame["asset_id"], asset_map),
        system_family_key=_lookup_key(maintenance_frame["system_family"], family_map),
        system_instance_key=_lookup_key(maintenance_frame["system_instance_id"], instance_map),
        component_key=_lookup_key(maintenance_frame["component_id"], component_map),
        track_key=0,
        data_source_key=_lookup_key(maintenance_frame["data_source_id"], data_source_map),
        time_key=_time_key(maintenance_frame["event_time_utc"], time_map),
        model_version_key=0,
        test_objective_key=_lookup_key(maintenance_frame["test_objective_id"], objective_map),
        requirement_key=_lookup_key(maintenance_frame["requirement_id"], requirement_map),
    )[
        [
            "event_id",
            "scenario_key",
            "test_event_key",
            "site_key",
            "asset_key",
            "system_family_key",
            "system_instance_key",
            "component_key",
            "track_key",
            "data_source_key",
            "time_key",
            "model_version_key",
            "test_objective_key",
            "requirement_key",
            "scenario_id",
            "test_event_id",
            "site_id",
            "asset_id",
            "system_instance_id",
            "component_id",
            "event_time_utc",
            "action",
            "status",
            "readiness_before",
            "readiness_after",
            "reason_code",
            "details.work_order_id",
            "details.maintenance_minutes",
            "classification",
        ]
    ].rename(
        columns={
            "details.work_order_id": "work_order_id",
            "details.maintenance_minutes": "maintenance_minutes",
        }
    )

    corrective_frame = sustainment[sustainment["record_type"] == "CORRECTIVE_ACTION"].copy().sort_values(["event_time_utc", "event_id"])
    corrective_frame["system_family"] = corrective_frame["system_instance_id"].map(system_to_family)
    fact_corrective_action = corrective_frame.assign(
        scenario_key=_lookup_key(corrective_frame["scenario_id"], scenario_map),
        test_event_key=_lookup_key(corrective_frame["test_event_id"], event_map),
        site_key=_lookup_key(corrective_frame["site_id"], site_map),
        asset_key=_lookup_key(corrective_frame["asset_id"], asset_map),
        system_family_key=_lookup_key(corrective_frame["system_family"], family_map),
        system_instance_key=_lookup_key(corrective_frame["system_instance_id"], instance_map),
        component_key=_lookup_key(corrective_frame["component_id"], component_map),
        data_source_key=_lookup_key(corrective_frame["data_source_id"], data_source_map),
        time_key=_time_key(corrective_frame["event_time_utc"], time_map),
        track_key=0,
        model_version_key=0,
    )[
        [
            "event_id",
            "scenario_key",
            "test_event_key",
            "site_key",
            "asset_key",
            "system_family_key",
            "system_instance_key",
            "component_key",
            "track_key",
            "data_source_key",
            "time_key",
            "model_version_key",
            "scenario_id",
            "test_event_id",
            "site_id",
            "asset_id",
            "system_instance_id",
            "component_id",
            "event_time_utc",
            "action",
            "status",
            "details.corrective_action_id",
            "details.related_finding_id",
            "details.owner_role",
            "details.due_time_utc",
            "details.review_status",
            "details.note",
            "classification",
        ]
    ].rename(
        columns={
            "details.corrective_action_id": "corrective_action_id",
            "details.related_finding_id": "related_finding_id",
            "details.owner_role": "owner_role",
            "details.due_time_utc": "due_time_utc",
            "details.review_status": "review_status",
            "details.note": "action_note",
        }
    )

    event_summary = pd.concat(
        [
            sensor_frame[["source_instance_id", "event_time_utc"]].rename(columns={"source_instance_id": "system_instance_id"}),
            status_frame[["source_instance_id", "event_time_utc"]].rename(columns={"source_instance_id": "system_instance_id"}),
            command_frame[["source_instance_id", "event_time_utc"]].rename(columns={"source_instance_id": "system_instance_id"}),
        ],
        ignore_index=True,
    )
    event_rollup = (
        event_summary.groupby("system_instance_id", as_index=False)
        .agg(first_observed_time_utc=("event_time_utc", "min"), last_observed_time_utc=("event_time_utc", "max"), observed_event_count=("event_time_utc", "count"))
    )
    readiness_rollup = (
        fact_readiness_snapshot.sort_values(["reported_time_utc", "system_instance_id"]).drop_duplicates(["system_instance_id"], keep="last")
        [["system_instance_id", "reported_state"]]
        .rename(columns={"reported_state": "latest_readiness_state"})
    )
    fact_system_participation = (
        topology[["scenario_id", "test_event_id", "site_id", "asset_id", "system_family", "system_instance_id"]]
        .drop_duplicates()
        .merge(event_rollup, on="system_instance_id", how="left")
        .merge(readiness_rollup, on="system_instance_id", how="left")
        .assign(
            participation_status=lambda frame: frame["observed_event_count"].fillna(0).apply(lambda value: "ACTIVE" if value > 0 else "NOT_OBSERVED"),
            scenario_key=lambda frame: _lookup_key(frame["scenario_id"], scenario_map),
            test_event_key=lambda frame: _lookup_key(frame["test_event_id"], event_map),
            site_key=lambda frame: _lookup_key(frame["site_id"], site_map),
            asset_key=lambda frame: _lookup_key(frame["asset_id"], asset_map),
            system_family_key=lambda frame: _lookup_key(frame["system_family"], family_map),
            system_instance_key=lambda frame: _lookup_key(frame["system_instance_id"], instance_map),
            component_key=lambda frame: 0,
            track_key=lambda frame: 0,
            data_source_key=lambda frame: _lookup_key(pd.Series(["feed-operations-snapshot"] * len(frame)), data_source_map),
            time_key=lambda frame: _time_key(frame["last_observed_time_utc"], time_map),
            model_version_key=lambda frame: 0,
            classification=SYNTHETIC_CLASSIFICATION,
        )
    )[
        [
            "scenario_key",
            "test_event_key",
            "site_key",
            "asset_key",
            "system_family_key",
            "system_instance_key",
            "component_key",
            "track_key",
            "data_source_key",
            "time_key",
            "model_version_key",
            "scenario_id",
            "test_event_id",
            "site_id",
            "asset_id",
            "system_instance_id",
            "first_observed_time_utc",
            "last_observed_time_utc",
            "observed_event_count",
            "latest_readiness_state",
            "participation_status",
            "classification",
        ]
    ]

    detection_event = sensor_frame.loc[sensor_frame["observation_type"] == "DETECTION"].iloc[0]
    shared_event = command_frame.loc[command_frame["action"] == "SHARED_TRACK_PUBLISHED"].iloc[0]
    correlation_event = command_frame.loc[command_frame["action"] == "TRACK_CORRELATED"].iloc[0]
    readiness_ratio = round((readiness_frame["reported_state"] == "READY").mean(), 3)
    continuity_ratio = round(sensor_frame["quality.continuity"].mean(), 3)
    open_action_count = int(
        maintenance_frame["status"].isin(["OPEN", "IN_PROGRESS", "DEFERRED"]).sum()
    )
    measure_values = {
        "gm-observation-latency-001": float(
            abs(
                (
                    detection_event["event_time_utc"]
                    - baseline.loc[baseline["planned_record_id"] == "plan-001", "planned_event_time_utc"].iloc[0]
                ).total_seconds()
            )
        ),
        "gm-track-continuity-001": continuity_ratio,
        "gm-shared-track-latency-001": float(shared_event["processing_delay_ms"] / 1000.0),
        "gm-correlation-window-001": float(correlation_event["processing_delay_ms"] / 1000.0),
        "gm-readiness-coverage-001": readiness_ratio,
        "gm-maintenance-open-actions-001": float(open_action_count),
    }
    related_track_ids = {
        "gm-observation-latency-001": "track-demo-001",
        "gm-track-continuity-001": "track-demo-001",
        "gm-shared-track-latency-001": "track-demo-001",
        "gm-correlation-window-001": "track-demo-001",
        "gm-readiness-coverage-001": "",
        "gm-maintenance-open-actions-001": "",
    }

    measure_rows = []
    for _, definition in measure_catalog.sort_values("quick_look_order").iterrows():
        measure_id = definition["governed_measure_id"]
        actual_value = float(measure_values[measure_id])
        threshold_value = float(definition["threshold_value"])
        measure_status = _measure_status(actual_value, definition["threshold_direction"], threshold_value)
        related_track_id = related_track_ids[measure_id]
        measure_rows.append(
            {
                "governed_measure_id": measure_id,
                "scenario_key": scenario_map[definition["scenario_id"]],
                "test_event_key": event_map[definition["test_event_id"]],
                "track_key": track_map.get(related_track_id, 0),
                "test_objective_key": objective_map[definition["test_objective_id"]],
                "requirement_key": requirement_map[definition["requirement_id"]],
                "model_version_key": version_map[definition["model_version_id"]],
                "data_source_key": data_source_map[definition["data_source_id"]],
                "time_key": time_map[pd.Timestamp(REPORT_TIMESTAMP_UTC).strftime("%Y%m%d%H%M%S")],
                "scenario_id": definition["scenario_id"],
                "test_event_id": definition["test_event_id"],
                "track_id": related_track_id,
                "test_objective_id": definition["test_objective_id"],
                "requirement_id": definition["requirement_id"],
                "model_version_id": definition["model_version_id"],
                "data_source_id": definition["data_source_id"],
                "measure_name": definition["measure_name"],
                "measure_group": definition["measure_group"],
                "actual_value": actual_value,
                "threshold_direction": definition["threshold_direction"],
                "threshold_value": threshold_value,
                "measure_unit": definition["measure_unit"],
                "comparison_mode": definition["comparison_mode"],
                "measure_status": measure_status,
                "variance_to_threshold": round(actual_value - threshold_value, 3),
                "evidence_record_ids_json": json.dumps(MEASURE_TO_EVIDENCE[measure_id]),
                "report_time_utc": REPORT_TIMESTAMP_UTC,
                "classification": definition["classification"],
            }
        )
    fact_test_measure = pd.DataFrame(measure_rows)

    failed_measures = fact_test_measure[fact_test_measure["measure_status"] == "FAIL"].copy()
    finding_templates = measure_catalog[
        [
            "governed_measure_id",
            "failure_finding_id",
            "failure_finding_code",
            "failure_title",
            "limitations_text",
            "review_status_default",
            "review_owner_role",
            "corrective_action_id",
            "formal_report_section",
        ]
    ]
    fact_finding = failed_measures.merge(finding_templates, on="governed_measure_id", how="left")
    fact_finding["finding_status"] = "OPEN"
    fact_finding["severity"] = fact_finding["measure_group"].map(
        {"command": "high", "readiness": "high", "sustainment": "medium"}
    ).fillna("medium")
    fact_finding["evidence_count"] = fact_finding["evidence_record_ids_json"].map(lambda value: len(json.loads(value)))
    fact_finding["finding_summary"] = fact_finding.apply(
        lambda row: (
            f"{row['measure_name']} measured {row['actual_value']} {row['measure_unit']} "
            f"against {row['threshold_direction']} {row['threshold_value']} {row['measure_unit']}."
        ),
        axis=1,
    )
    fact_finding["review_time_utc"] = REPORT_TIMESTAMP_UTC
    fact_finding = fact_finding[
        [
            "failure_finding_id",
            "failure_finding_code",
            "finding_status",
            "severity",
            "governed_measure_id",
            "scenario_key",
            "test_event_key",
            "track_key",
            "test_objective_key",
            "requirement_key",
            "model_version_key",
            "data_source_key",
            "scenario_id",
            "test_event_id",
            "track_id",
            "test_objective_id",
            "requirement_id",
            "measure_name",
            "measure_group",
            "actual_value",
            "threshold_direction",
            "threshold_value",
            "measure_unit",
            "evidence_record_ids_json",
            "evidence_count",
            "finding_summary",
            "failure_title",
            "limitations_text",
            "review_status_default",
            "review_owner_role",
            "corrective_action_id",
            "formal_report_section",
            "model_version_id",
            "review_time_utc",
            "classification",
        ]
    ].rename(
        columns={
            "failure_finding_id": "finding_id",
            "failure_finding_code": "finding_code",
            "failure_title": "finding_title",
            "review_status_default": "review_status",
            "review_owner_role": "review_owner_role",
        }
    )

    objective_rollup = (
        fact_test_measure.groupby(["scenario_id", "test_event_id", "test_objective_id", "test_objective_key"], as_index=False)
        .agg(
            measure_count=("governed_measure_id", "count"),
            pass_count=("measure_status", lambda series: int((series == "PASS").sum())),
            fail_count=("measure_status", lambda series: int((series == "FAIL").sum())),
            governed_measure_ids_json=("governed_measure_id", lambda series: json.dumps(list(series))),
        )
    )
    objective_rollup["objective_status"] = objective_rollup.apply(
        lambda row: "PASS" if row["fail_count"] == 0 else ("AT_RISK" if row["pass_count"] > 0 else "FAIL"),
        axis=1,
    )
    objective_rollup["objective_score"] = (objective_rollup["pass_count"] / objective_rollup["measure_count"]).round(3)
    objective_rollup["linked_finding_count"] = objective_rollup["test_objective_id"].map(
        fact_finding.groupby("test_objective_id").size().to_dict()
    ).fillna(0).astype(int)
    objective_rollup["evaluation_time_utc"] = REPORT_TIMESTAMP_UTC
    objective_rollup["classification"] = SYNTHETIC_CLASSIFICATION
    fact_objective_evaluation = objective_rollup

    requirement_rollup = fact_test_measure.copy()
    requirement_rollup["verification_status"] = requirement_rollup["measure_status"].map(
        {"PASS": "VERIFIED", "FAIL": "NOT_VERIFIED"}
    )
    requirement_rollup["linked_finding_id"] = requirement_rollup["governed_measure_id"].map(
        measure_catalog.set_index("governed_measure_id")["failure_finding_id"].to_dict()
    )
    requirement_rollup.loc[requirement_rollup["measure_status"] == "PASS", "linked_finding_id"] = ""
    requirement_rollup["verification_time_utc"] = REPORT_TIMESTAMP_UTC
    fact_requirement_verification = requirement_rollup[
        [
            "governed_measure_id",
            "scenario_key",
            "test_event_key",
            "track_key",
            "test_objective_key",
            "requirement_key",
            "model_version_key",
            "data_source_key",
            "time_key",
            "scenario_id",
            "test_event_id",
            "track_id",
            "test_objective_id",
            "requirement_id",
            "measure_name",
            "actual_value",
            "threshold_direction",
            "threshold_value",
            "measure_unit",
            "measure_status",
            "verification_status",
            "linked_finding_id",
            "evidence_record_ids_json",
            "verification_time_utc",
            "classification",
        ]
    ]

    return {
        "fact_sensor_observation": fact_sensor_observation.reset_index(drop=True),
        "fact_system_status": fact_system_status.reset_index(drop=True),
        "fact_command_event": fact_command_event.reset_index(drop=True),
        "fact_system_participation": fact_system_participation.reset_index(drop=True),
        "fact_readiness_snapshot": fact_readiness_snapshot.reset_index(drop=True),
        "fact_maintenance_action": fact_maintenance_action.reset_index(drop=True),
        "fact_test_measure": fact_test_measure.reset_index(drop=True),
        "fact_finding": fact_finding.reset_index(drop=True),
        "fact_objective_evaluation": fact_objective_evaluation.reset_index(drop=True),
        "fact_requirement_verification": fact_requirement_verification.reset_index(drop=True),
        "fact_corrective_action": fact_corrective_action.reset_index(drop=True),
    }


def build_products(
    sources: dict[str, pd.DataFrame],
    dimensions: dict[str, pd.DataFrame],
    facts: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    baseline = sources["planned_test_baseline"]
    observed = sources["observed_test_events"]
    sustainment = sources["sustainment_actions"]
    measure_catalog = sources["governed_measure_catalog"]

    fact_findings = facts["fact_finding"]
    fact_measures = facts["fact_test_measure"]
    fact_objectives = facts["fact_objective_evaluation"]
    fact_requirements = facts["fact_requirement_verification"]
    fact_corrective = facts["fact_corrective_action"]
    fact_readiness = facts["fact_readiness_snapshot"]
    fact_status = facts["fact_system_status"]
    fact_command = facts["fact_command_event"]
    fact_sensor = facts["fact_sensor_observation"]
    fact_maintenance = facts["fact_maintenance_action"]
    fact_participation = facts["fact_system_participation"]

    timeline_frames = [
        baseline.assign(
            timeline_source="planned_baseline",
            timeline_category="planned_event",
            event_time_utc=baseline["planned_event_time_utc"],
            source_record_id=baseline["planned_record_id"],
            detail_text=baseline["planned_event_type"] + " -> " + baseline["expected_state"],
        )[
            [
                "timeline_source",
                "timeline_category",
                "event_time_utc",
                "scenario_id",
                "test_event_id",
                "site_id",
                "system_instance_id",
                "track_id",
                "source_record_id",
                "detail_text",
            ]
        ],
        fact_sensor.assign(
            timeline_source="sensor_observation",
            timeline_category="sensor_observation",
            source_record_id=fact_sensor["event_id"],
            detail_text=fact_sensor["observation_type"] + " quality=" + fact_sensor["quality_score"].round(2).astype(str),
        )[
            [
                "timeline_source",
                "timeline_category",
                "event_time_utc",
                "scenario_id",
                "test_event_id",
                "site_id",
                "system_instance_id",
                "track_id",
                "source_record_id",
                "detail_text",
            ]
        ],
        fact_command.assign(
            timeline_source="command_event",
            timeline_category="command_event",
            source_record_id=fact_command["event_id"],
            detail_text=fact_command["action"] + " status=" + fact_command["status"],
        )[
            [
                "timeline_source",
                "timeline_category",
                "event_time_utc",
                "scenario_id",
                "test_event_id",
                "site_id",
                "system_instance_id",
                "track_id",
                "source_record_id",
                "detail_text",
            ]
        ],
        fact_status.assign(
            timeline_source="system_status",
            timeline_category="system_status",
            source_record_id=fact_status["event_id"],
            detail_text=fact_status["operating_state"] + " / " + fact_status["readiness_state"],
        )[
            [
                "timeline_source",
                "timeline_category",
                "event_time_utc",
                "scenario_id",
                "test_event_id",
                "site_id",
                "system_instance_id",
                "track_id",
                "source_record_id",
                "detail_text",
            ]
        ],
        fact_readiness.assign(
            timeline_source="readiness_snapshot",
            timeline_category="readiness_snapshot",
            event_time_utc=fact_readiness["reported_time_utc"],
            track_id="",
            source_record_id=fact_readiness["snapshot_record_id"],
            detail_text=fact_readiness["reported_state"] + " expected=" + fact_readiness["expected_state"],
        )[
            [
                "timeline_source",
                "timeline_category",
                "event_time_utc",
                "scenario_id",
                "test_event_id",
                "site_id",
                "system_instance_id",
                "track_id",
                "source_record_id",
                "detail_text",
            ]
        ],
        fact_maintenance.assign(
            timeline_source="maintenance_action",
            timeline_category="maintenance_action",
            source_record_id=fact_maintenance["event_id"],
            track_id="",
            detail_text=fact_maintenance["action"] + " status=" + fact_maintenance["status"],
        )[
            [
                "timeline_source",
                "timeline_category",
                "event_time_utc",
                "scenario_id",
                "test_event_id",
                "site_id",
                "system_instance_id",
                "track_id",
                "source_record_id",
                "detail_text",
            ]
        ],
        fact_findings.assign(
            timeline_source="finding",
            timeline_category="finding",
            event_time_utc=pd.to_datetime(fact_findings["review_time_utc"], utc=True),
            site_id="",
            system_instance_id="",
            source_record_id=fact_findings["finding_id"],
            detail_text=fact_findings["finding_code"] + " review=" + fact_findings["review_status"],
        )[
            [
                "timeline_source",
                "timeline_category",
                "event_time_utc",
                "scenario_id",
                "test_event_id",
                "site_id",
                "system_instance_id",
                "track_id",
                "source_record_id",
                "detail_text",
            ]
        ],
        fact_corrective.assign(
            timeline_source="corrective_action",
            timeline_category="corrective_action",
            source_record_id=fact_corrective["corrective_action_id"],
            track_id="",
            detail_text=fact_corrective["action"] + " status=" + fact_corrective["status"],
        )[
            [
                "timeline_source",
                "timeline_category",
                "event_time_utc",
                "scenario_id",
                "test_event_id",
                "site_id",
                "system_instance_id",
                "track_id",
                "source_record_id",
                "detail_text",
            ]
        ],
    ]
    gold_integrated_timeline = pd.concat(timeline_frames, ignore_index=True).sort_values(
        ["event_time_utc", "timeline_source", "source_record_id"]
    ).reset_index(drop=True)
    gold_integrated_timeline.insert(0, "timeline_index", range(1, len(gold_integrated_timeline) + 1))
    gold_integrated_timeline["event_time_utc"] = pd.to_datetime(
        gold_integrated_timeline["event_time_utc"], utc=True, errors="coerce"
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    latest_status = (
        fact_status.sort_values(["event_time_utc", "system_instance_id"]).drop_duplicates(["system_instance_id"], keep="last")
    )
    open_actions = (
        fact_maintenance.groupby("system_instance_id", as_index=False)
        .agg(open_maintenance_actions=("event_id", "count"))
    )
    finding_counts = (
        fact_findings.groupby("requirement_id", as_index=False)
        .agg(linked_findings=("finding_id", "count"))
    )
    readiness_measure = fact_measures[
        fact_measures["governed_measure_id"] == "gm-readiness-coverage-001"
    ][["actual_value", "measure_status"]].rename(
        columns={"actual_value": "governed_readiness_ratio", "measure_status": "governed_readiness_status"}
    )
    gold_readiness_summary = (
        fact_participation.merge(
            latest_status[
                [
                    "system_instance_id",
                    "operating_state",
                    "readiness_state",
                    "health_score",
                ]
            ],
            on="system_instance_id",
            how="left",
        )
        .merge(open_actions, on="system_instance_id", how="left")
        .fillna({"open_maintenance_actions": 0})
    )
    gold_readiness_summary["governed_readiness_ratio"] = readiness_measure.iloc[0]["governed_readiness_ratio"]
    gold_readiness_summary["governed_readiness_status"] = readiness_measure.iloc[0]["governed_readiness_status"]
    gold_readiness_summary = gold_readiness_summary[
        [
            "scenario_id",
            "test_event_id",
            "site_id",
            "asset_id",
            "system_instance_id",
            "participation_status",
            "latest_readiness_state",
            "operating_state",
            "readiness_state",
            "health_score",
            "observed_event_count",
            "open_maintenance_actions",
            "governed_readiness_ratio",
            "governed_readiness_status",
        ]
    ].sort_values(["site_id", "system_instance_id"])

    gold_finding_register = fact_findings.merge(
        fact_corrective[
            [
                "corrective_action_id",
                "status",
                "owner_role",
                "due_time_utc",
                "review_status",
            ]
        ].rename(
            columns={
                "status": "corrective_action_status",
                "review_status": "corrective_action_review_status",
            }
        ),
        on="corrective_action_id",
        how="left",
    )[
        [
            "finding_id",
            "finding_code",
            "finding_title",
            "severity",
            "measure_name",
            "actual_value",
            "threshold_direction",
            "threshold_value",
            "measure_unit",
            "review_status",
            "review_owner_role",
            "corrective_action_id",
            "corrective_action_status",
            "owner_role",
            "due_time_utc",
            "evidence_record_ids_json",
            "limitations_text",
            "formal_report_section",
        ]
    ]

    objective_names = dimensions["dim_test_objective"][["test_objective_id", "test_objective_name", "formal_report_section"]]
    gold_objective_status = fact_objectives.merge(objective_names, on="test_objective_id", how="left")[
        [
            "scenario_id",
            "test_event_id",
            "test_objective_id",
            "test_objective_name",
            "formal_report_section",
            "objective_status",
            "objective_score",
            "measure_count",
            "pass_count",
            "fail_count",
            "linked_finding_count",
            "governed_measure_ids_json",
            "evaluation_time_utc",
        ]
    ]

    requirement_names = dimensions["dim_requirement"][["requirement_id", "requirement_name", "measure_group"]]
    gold_requirement_verification_report = fact_requirements.merge(requirement_names, on="requirement_id", how="left")[
        [
            "scenario_id",
            "test_event_id",
            "test_objective_id",
            "requirement_id",
            "requirement_name",
            "measure_group",
            "governed_measure_id",
            "measure_name",
            "actual_value",
            "threshold_direction",
            "threshold_value",
            "measure_unit",
            "verification_status",
            "linked_finding_id",
            "evidence_record_ids_json",
            "verification_time_utc",
        ]
    ]

    observed_sensor_lookup = (
        observed[observed["event_type"] == "sensor.observation"]
        .assign(comparison_key=lambda frame: frame["track_id"] + "|" + frame["observation_type"])
        .set_index("comparison_key")
    )
    observed_command_lookup = (
        observed[observed["event_type"] == "command.integration"]
        .assign(comparison_key=lambda frame: frame["track_id"] + "|" + frame["action"])
        .set_index("comparison_key")
    )
    readiness_lookup = (
        facts["fact_readiness_snapshot"]
        .assign(comparison_key=lambda frame: frame["system_instance_id"] + "|SYSTEM_READY")
        .set_index("comparison_key")
    )
    sustainment_lookup = (
        sustainment[sustainment["action"] == "WORK_ORDER_COMPLETED"]
        .assign(comparison_key=lambda frame: frame["asset_id"] + "|WORK_ORDER_COMPLETED")
        .set_index("comparison_key")
    )

    reconciliation_rows = []
    for _, planned_row in baseline.sort_values("planned_record_id").iterrows():
        comparison_key = planned_row["comparison_key"]
        actual_record_id = ""
        actual_time = pd.NaT
        actual_state = ""
        reconciliation_status = "MISSING_OBSERVED"

        if planned_row["planned_event_type"] in {"DETECTION", "TRACK_UPDATE"} and comparison_key in observed_sensor_lookup.index:
            actual = observed_sensor_lookup.loc[comparison_key]
            actual_record_id = actual["event_id"]
            actual_time = actual["event_time_utc"]
            actual_state = actual["observation_type"]
            reconciliation_status = "MATCHED"
        elif planned_row["planned_event_type"] in {"SHARED_TRACK_PUBLISHED", "TRACK_CORRELATED"} and comparison_key in observed_command_lookup.index:
            actual = observed_command_lookup.loc[comparison_key]
            actual_record_id = actual["event_id"]
            actual_time = actual["event_time_utc"]
            actual_state = actual["status"]
            reconciliation_status = "MATCHED"
        elif planned_row["planned_event_type"] == "SYSTEM_READY" and comparison_key in readiness_lookup.index:
            actual = readiness_lookup.loc[comparison_key]
            actual_record_id = actual["snapshot_record_id"]
            actual_time = actual["reported_time_utc"]
            actual_state = actual["reported_state"]
            reconciliation_status = "MATCHED" if actual_state == planned_row["expected_state"] else "STATE_MISMATCH"
        elif planned_row["planned_event_type"] == "WORK_ORDER_COMPLETED" and comparison_key in sustainment_lookup.index:
            actual = sustainment_lookup.loc[comparison_key]
            actual_record_id = actual["event_id"]
            actual_time = actual["event_time_utc"]
            actual_state = actual["status"]
            reconciliation_status = "MATCHED"

        variance_seconds = (
            abs((pd.to_datetime(actual_time, utc=True) - planned_row["planned_event_time_utc"]).total_seconds())
            if pd.notna(actual_time)
            else None
        )
        if reconciliation_status == "MATCHED" and variance_seconds is not None and variance_seconds > 30:
            reconciliation_status = "TIME_VARIANCE"

        reconciliation_rows.append(
            {
                "planned_record_id": planned_row["planned_record_id"],
                "comparison_key": comparison_key,
                "planned_event_type": planned_row["planned_event_type"],
                "planned_event_time_utc": planned_row["planned_event_time_utc"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expected_state": planned_row["expected_state"],
                "actual_record_id": actual_record_id,
                "actual_time_utc": pd.to_datetime(actual_time, utc=True).strftime("%Y-%m-%dT%H:%M:%SZ") if pd.notna(actual_time) else "",
                "actual_state": actual_state,
                "variance_seconds": variance_seconds,
                "reconciliation_status": reconciliation_status,
            }
        )
    gold_reconciliation_summary = pd.DataFrame(reconciliation_rows)

    lesson_lookup = measure_catalog.set_index("governed_measure_id")["lesson_statement"].to_dict()
    gold_lessons_learned = fact_findings.assign(
        lesson_id=lambda frame: frame["finding_id"].map(lambda value: f"lesson-{value}"),
        lesson_statement=lambda frame: frame["governed_measure_id"].map(lesson_lookup),
    )[
        [
            "lesson_id",
            "finding_id",
            "test_objective_id",
            "requirement_id",
            "governed_measure_id",
            "formal_report_section",
            "lesson_statement",
            "limitations_text",
            "corrective_action_id",
            "review_status",
        ]
    ]

    finding_lookup = fact_findings.groupby("test_objective_id")["finding_id"].agg(list).to_dict()
    gold_quick_look_summary = gold_objective_status.copy()
    gold_quick_look_summary["linked_finding_ids_json"] = gold_quick_look_summary["test_objective_id"].map(
        lambda value: json.dumps(finding_lookup.get(value, []))
    )
    gold_quick_look_summary["report_view"] = "quick_look"

    section_lookup = measure_catalog[["governed_measure_id", "formal_report_section"]]
    measure_with_sections = fact_measures.merge(section_lookup, on="governed_measure_id", how="left")
    gold_formal_report_summary = (
        measure_with_sections.groupby("formal_report_section", as_index=False)
        .agg(
            measure_count=("governed_measure_id", "count"),
            pass_count=("measure_status", lambda series: int((series == "PASS").sum())),
            fail_count=("measure_status", lambda series: int((series == "FAIL").sum())),
            governed_measure_ids_json=("governed_measure_id", lambda series: json.dumps(list(series))),
        )
    )
    gold_formal_report_summary["report_view"] = "formal_report"
    gold_formal_report_summary["linked_finding_count"] = gold_formal_report_summary["formal_report_section"].map(
        fact_findings.groupby("formal_report_section").size().to_dict()
    ).fillna(0).astype(int)

    return {
        "gold_integrated_timeline": gold_integrated_timeline,
        "gold_readiness_summary": gold_readiness_summary,
        "gold_finding_register": gold_finding_register,
        "gold_objective_status": gold_objective_status,
        "gold_requirement_verification_report": gold_requirement_verification_report,
        "gold_reconciliation_summary": gold_reconciliation_summary,
        "gold_lessons_learned": gold_lessons_learned,
        "gold_quick_look_summary": gold_quick_look_summary,
        "gold_formal_report_summary": gold_formal_report_summary,
    }