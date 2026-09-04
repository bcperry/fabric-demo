from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import sys
import warnings
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
EMULATOR_SRC = ROOT / "02-emulators" / "src"
if str(EMULATOR_SRC) not in sys.path:
    sys.path.insert(0, str(EMULATOR_SRC))

from mda_emulators.engine import TOPICS, ScenarioEngine  # noqa: E402
from mda_emulators.scenario import load_scenario  # noqa: E402


UTC = timezone.utc
DEMO_ID = "integrated-test-data"
DEMO_TITLE = "Integrated Test Data Product"
RELEASE_ID = "2026.11.03"
SCENARIO_PATH = ROOT / "01-contracts" / "examples" / "scenario.integrated-defense.json"
START_TIME = datetime(2026, 11, 3, 15, 0, 0, tzinfo=UTC)
DURATION_SECONDS = 180
OBSERVED_RUN_ID = "run-demo07-integrated-001"
BASELINE_RUN_ID = "sim-demo07-integrated-001"
MODEL_VERSION = "model-integrated-defense-v1"
POSTGRES_ENGINE = "PostgreSQL"

DATA_DIR = ROOT / "data"
BASELINE_DIR = (
    DATA_DIR
    / "baseline"
    / "scenario_id=integrated-defense-001"
    / f"simulation_run_id={BASELINE_RUN_ID}"
)

OBSERVED_STREAM_PATH = DATA_DIR / "observed_eventstream.jsonl"
STARTUP_MANIFEST_PATH = DATA_DIR / "startup_seed_manifest.json"
FALLBACK_MANIFEST_PATH = DATA_DIR / "fallback_bundle_manifest.json"
POSTGRES_BATCH_MANIFEST_PATH = DATA_DIR / "postgres_batch_manifest.json"
PREDICTED_TRACKS_PATH = BASELINE_DIR / "predicted_tracks.jsonl"
PREDICTED_EVENTS_PATH = BASELINE_DIR / "predicted_events.jsonl"
PREDICTED_MEASURES_PATH = BASELINE_DIR / "predicted_measures.jsonl"
ENVIRONMENTAL_ASSUMPTIONS_PATH = BASELINE_DIR / "environmental_assumptions.jsonl"
BASELINE_MANIFEST_PATH = BASELINE_DIR / "manifest.json"
DEMO_MANIFEST_PATH = ROOT / "RELEASE_MANIFEST.json"

CSV_PATHS = {
    "postgres_test_event": DATA_DIR / "postgres_test_event_batch01.csv",
    "postgres_test_objective": DATA_DIR / "postgres_test_objective_batch01.csv",
    "postgres_required_feed": DATA_DIR / "postgres_required_feed_batch01.csv",
    "postgres_site": DATA_DIR / "postgres_site_batch01.csv",
    "postgres_system_instance": DATA_DIR / "postgres_system_instance_batch01.csv",
    "postgres_readiness_history_batch01": DATA_DIR / "postgres_readiness_history_batch01.csv",
    "postgres_readiness_history_batch02": DATA_DIR / "postgres_readiness_history_batch02.csv",
    "postgres_maintenance_action": DATA_DIR / "postgres_maintenance_action_batch01.csv",
    "postgres_inventory_position": DATA_DIR / "postgres_inventory_position_batch01.csv",
    "postgres_finding": DATA_DIR / "postgres_finding_batch01.csv",
    "postgres_finding_evidence": DATA_DIR / "postgres_finding_evidence_batch01.csv",
    "postgres_corrective_action": DATA_DIR / "postgres_corrective_action_batch01.csv",
    "postgres_report_review": DATA_DIR / "postgres_report_review_batch01.csv",
}

EXAMPLE_SPECS = [
    ("sensor-observation", "sensor.observation", "track_id"),
    ("system-status", "system.status", "operating_state"),
    ("command-integration", "command.integration", "action"),
    ("sustainment", "sustainment.event", "asset_id"),
    ("target-telemetry", "target.telemetry", "velocity"),
    ("interceptor-telemetry", "interceptor.telemetry", "update_receipt_state"),
    ("instrumentation-observation", "instrumentation.observation", "sensor_modality"),
    ("groundtruth-observation", "groundtruth.observation", "truth_role"),
    ("environment-observation", "environment.observation", "condition_summary"),
    ("instrumentation-health", "instrumentation.health", "observed_lag_ms"),
    ("network-health", "network.health", "latency_ms"),
    ("readiness-poll", "readiness.poll", "participant_role"),
    ("operator-test-event", "operator.test_event", "decision_authority"),
    ("safety-status", "safety.status", "authority_scope"),
]


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Cannot write an empty CSV file: {path}")
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _hash_rows(rows: Any) -> str:
    normalized = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _scenario() -> dict[str, Any]:
    return load_scenario(SCENARIO_PATH)


def _observed_stream() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    engine = ScenarioEngine(
        _scenario(),
        start_time=START_TIME,
        run_id=OBSERVED_RUN_ID,
    )
    manifest = engine.build_run_manifest(DURATION_SECONDS)
    records = [
        {"topic": topic, "key": event["ordering_key"], "event": event}
        for topic, event in engine.generate(DURATION_SECONDS)
    ]
    return manifest, records


def _predicted_products() -> dict[str, Any]:
    scenario = copy.deepcopy(_scenario())
    scenario["anomalies"] = []
    engine = ScenarioEngine(
        scenario,
        start_time=START_TIME,
        run_id=BASELINE_RUN_ID,
    )
    generated = list(engine.generate(DURATION_SECONDS))
    events = [event for _, event in generated]

    predicted_tracks = [
        {
            "scenario_id": scenario["scenario_id"],
            "simulation_run_id": BASELINE_RUN_ID,
            "test_event_id": engine.test_event_id,
            "model_version": MODEL_VERSION,
            "event_type": event["event_type"],
            "source_system": event["source_system"],
            "source_instance_id": event["source_instance_id"],
            "track_id": event["track_id"],
            "expected_event_time_utc": event["event_time_utc"],
            "expected_position": event.get("position"),
            "expected_quality": event.get("quality"),
            "classification": event["classification"],
        }
        for event in events
        if event["event_type"]
        in {
            "sensor.observation",
            "target.telemetry",
            "interceptor.telemetry",
            "groundtruth.observation",
        }
    ]
    predicted_events = [
        {
            "scenario_id": scenario["scenario_id"],
            "simulation_run_id": BASELINE_RUN_ID,
            "test_event_id": engine.test_event_id,
            "track_id": event["track_id"],
            "source_system": event["source_system"],
            "source_instance_id": event["source_instance_id"],
            "action": event["action"],
            "expected_status": event["status"],
            "expected_processing_delay_ms": event["processing_delay_ms"],
            "expected_event_time_utc": event["event_time_utc"],
            "classification": event["classification"],
        }
        for event in events
        if event["event_type"] == "command.integration"
    ]
    first_detection = next(
        event for event in events if event["event_type"] == "sensor.observation"
    )
    first_assignment = next(
        event
        for event in events
        if event["event_type"] == "command.integration"
        and event["action"] == "ASSIGNMENT_ACKNOWLEDGED"
    )
    predicted_measures = [
        {
            "scenario_id": scenario["scenario_id"],
            "simulation_run_id": BASELINE_RUN_ID,
            "measure_id": "measure-predicted-detection-count",
            "measure_name": "Predicted TPY-2 detection and update count",
            "measure_value": len(
                [event for event in events if event["event_type"] == "sensor.observation"]
            ),
            "unit": "events",
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "scenario_id": scenario["scenario_id"],
            "simulation_run_id": BASELINE_RUN_ID,
            "measure_id": "measure-predicted-first-detection",
            "measure_name": "Predicted first detection time",
            "measure_value": first_detection["event_time_utc"],
            "unit": "utc",
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "scenario_id": scenario["scenario_id"],
            "simulation_run_id": BASELINE_RUN_ID,
            "measure_id": "measure-predicted-assignment-ack-delay",
            "measure_name": "Predicted assignment acknowledgement processing delay",
            "measure_value": first_assignment["processing_delay_ms"],
            "unit": "milliseconds",
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "scenario_id": scenario["scenario_id"],
            "simulation_run_id": BASELINE_RUN_ID,
            "measure_id": "measure-predicted-network-status",
            "measure_name": "Predicted network health events",
            "measure_value": 0,
            "unit": "degraded-events",
            "classification": "SYNTHETIC_UNCLASS",
        },
    ]
    environmental_assumptions = [
        {
            "scenario_id": scenario["scenario_id"],
            "simulation_run_id": BASELINE_RUN_ID,
            "model_version": MODEL_VERSION,
            "assumption_id": "env-assumption-001",
            "condition_summary": "NOMINAL",
            "visibility_state": "CLEAR",
            "expected_effect": "NONE",
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "scenario_id": scenario["scenario_id"],
            "simulation_run_id": BASELINE_RUN_ID,
            "model_version": MODEL_VERSION,
            "assumption_id": "env-assumption-002",
            "condition_summary": "NOMINAL",
            "visibility_state": "CLEAR",
            "expected_effect": "No scripted data-quality delay",
            "classification": "SYNTHETIC_UNCLASS",
        },
    ]
    manifest = {
        "schema_version": "1.0.0",
        "scenario_id": scenario["scenario_id"],
        "simulation_run_id": BASELINE_RUN_ID,
        "model_version": MODEL_VERSION,
        "classification": "SYNTHETIC_UNCLASS",
        "generated_time_utc": _format_utc(START_TIME),
        "files": [
            {
                "path": _relative(PREDICTED_TRACKS_PATH),
                "row_count": len(predicted_tracks),
                "sha256": _hash_rows(predicted_tracks),
            },
            {
                "path": _relative(PREDICTED_EVENTS_PATH),
                "row_count": len(predicted_events),
                "sha256": _hash_rows(predicted_events),
            },
            {
                "path": _relative(PREDICTED_MEASURES_PATH),
                "row_count": len(predicted_measures),
                "sha256": _hash_rows(predicted_measures),
            },
            {
                "path": _relative(ENVIRONMENTAL_ASSUMPTIONS_PATH),
                "row_count": len(environmental_assumptions),
                "sha256": _hash_rows(environmental_assumptions),
            },
        ],
    }
    return {
        "predicted_tracks": predicted_tracks,
        "predicted_events": predicted_events,
        "predicted_measures": predicted_measures,
        "environmental_assumptions": environmental_assumptions,
        "manifest": manifest,
    }


def _readiness_state(entry: dict[str, Any]) -> str:
    if entry.get("readiness_state"):
        return entry["readiness_state"]
    if entry["source_system"] == "SAFETY_MONITOR":
        return "READY"
    if entry["event_profile"] == "DEGRADED":
        return "LIMITED"
    return "READY"


def _health_score(entry: dict[str, Any]) -> float:
    if entry["source_system"] in {"NETWORK_MONITOR", "INSTRUMENTATION_MONITOR"}:
        return 0.82
    if entry["event_profile"] == "DEGRADED":
        return 0.84
    return 0.97


def _postgres_rows(
    observed_manifest: dict[str, Any],
    observed_records: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    events = [record["event"] for record in observed_records]
    delayed_event = next(
        event
        for event in events
        if event["event_type"] == "command.integration" and event["status"] == "DELAYED"
    )
    network_degraded = next(
        event
        for event in events
        if event["event_type"] == "network.health" and event["status"] == "DEGRADED"
    )
    instrumentation_degraded = next(
        event
        for event in events
        if event["event_type"] == "instrumentation.health"
        and event["status"] == "DEGRADED"
    )
    operator_hold = next(
        event
        for event in events
        if event["event_type"] == "operator.test_event"
        and event["marker"] == "HOLD_ISSUED"
    )
    operator_resume = next(
        event
        for event in events
        if event["event_type"] == "operator.test_event"
        and event["marker"] == "RESUME_AUTHORIZED"
    )
    safety_evidence = next(
        event
        for event in events
        if event["event_type"] == "safety.status"
        and event["advisory_state"] == "AMBER"
    )
    readiness_recovery = next(
        event
        for event in events
        if event["event_type"] == "readiness.poll"
        and event["poll_id"] == "poll-recovery-001"
        and event["participant_role"] == "role-test-director"
    )

    test_event_rows = [
        {
            "test_event_id": observed_manifest["test_event_id"],
            "scenario_id": observed_manifest["scenario_id"],
            "observed_run_manifest_id": observed_manifest["run_manifest_id"],
            "predicted_run_manifest_id": BASELINE_RUN_ID,
            "event_name": "Synthetic integrated defense lifecycle rehearsal",
            "planned_start_time_utc": observed_manifest["start_time_utc"],
            "planned_end_time_utc": _format_utc(START_TIME + timedelta(seconds=DURATION_SECONDS)),
            "classification": "SYNTHETIC_UNCLASS",
        }
    ]
    objective_rows = [
        {
            "objective_id": "obj-track-fusion",
            "objective_name": "Shared track reaches both engagement lanes",
            "objective_phase": "Running",
            "success_measure": "One TPY-2 track produces shared-track, assignment, and THAAD participation events.",
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "objective_id": "obj-observed-vs-predicted",
            "objective_name": "Observed chain is compared against deterministic prediction",
            "objective_phase": "Analysis",
            "success_measure": "Exactly one delayed observed assignment acknowledgement differs from the predicted baseline.",
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "objective_id": "obj-range-evidence",
            "objective_name": "Range instrumentation explains the deviation",
            "objective_phase": "Analysis",
            "success_measure": "Instrumentation and ground-truth lanes isolate the timing issue to synthetic data alignment.",
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "objective_id": "obj-readiness-recovery",
            "objective_name": "Readiness posture is recoverable for the next event",
            "objective_phase": "Post-Test Reporting",
            "success_measure": "Recovery poll captures a limitation and corrective action without losing lineage.",
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "objective_id": "obj-safety-boundary",
            "objective_name": "Safety evidence stays advisory",
            "objective_phase": "Running|Post-Test Reporting",
            "success_measure": "Safety-status evidence recommends action but never becomes an authoritative operator decision.",
            "classification": "SYNTHETIC_UNCLASS",
        },
    ]
    required_feed_rows = [
        {
            "required_feed_id": "feed-sensor-observation",
            "feed_name": "TPY-2 sensor observation",
            "source_pattern": "streaming",
            "expected_topic": TOPICS["sensor.observation"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "required_feed_id": "feed-command-integration",
            "feed_name": "Integration command events",
            "source_pattern": "streaming",
            "expected_topic": TOPICS["command.integration"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "required_feed_id": "feed-range-evidence",
            "feed_name": "Instrumentation and optical evidence",
            "source_pattern": "streaming",
            "expected_topic": TOPICS["instrumentation.observation"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "required_feed_id": "feed-network-health",
            "feed_name": "Abstract network health",
            "source_pattern": "streaming",
            "expected_topic": TOPICS["network.health"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "required_feed_id": "feed-readiness-poll",
            "feed_name": "Authoritative readiness poll",
            "source_pattern": "streaming",
            "expected_topic": TOPICS["readiness.poll"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "required_feed_id": "feed-operator-control",
            "feed_name": "Authoritative operator decisions",
            "source_pattern": "streaming",
            "expected_topic": TOPICS["operator.test_event"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "required_feed_id": "feed-safety-evidence",
            "feed_name": "Advisory safety evidence",
            "source_pattern": "streaming",
            "expected_topic": TOPICS["safety.status"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "required_feed_id": "feed-postgres-admin",
            "feed_name": "PostgreSQL administrative control plane",
            "source_pattern": "postgresql",
            "expected_topic": "",
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "required_feed_id": "feed-adls-baseline",
            "feed_name": "Emulated baseline package",
            "source_pattern": "adls",
            "expected_topic": "",
            "classification": "SYNTHETIC_UNCLASS",
        },
    ]
    site_rows = [
        {
            "site_id": site["site_id"],
            "display_name": site["display_name"],
            "latitude": site["location"]["latitude"],
            "longitude": site["location"]["longitude"],
            "location_notice": observed_manifest["location_notice"],
            "classification": "SYNTHETIC_UNCLASS",
            "updated_at_utc": observed_manifest["start_time_utc"],
        }
        for site in _scenario()["sites"]
    ]
    system_instance_rows = [
        {
            "system_instance_id": entry["source_instance_id"],
            "site_id": entry["site_id"],
            "system_family": entry["source_system"],
            "mission_role": entry["role"],
            "event_profile": entry["event_profile"],
            "startup_seed": entry["startup_seed"],
            "configuration_version": "1.0.0",
            "classification": "SYNTHETIC_UNCLASS",
            "updated_at_utc": observed_manifest["start_time_utc"],
        }
        for entry in observed_manifest["sources"]
    ]
    readiness_history_batch01 = [
        {
            "readiness_event_id": f"ready-{entry['source_instance_id']}-001",
            "system_instance_id": entry["source_instance_id"],
            "readiness_state": _readiness_state(entry),
            "health_score": _health_score(entry),
            "reason_code": "INITIAL_REHEARSAL_BASELINE",
            "effective_at_utc": _format_utc(START_TIME - timedelta(minutes=5)),
            "recorded_at_utc": _format_utc(START_TIME - timedelta(minutes=4)),
            "classification": "SYNTHETIC_UNCLASS",
        }
        for entry in observed_manifest["sources"]
    ]
    readiness_history_batch02 = [
        {
            "readiness_event_id": "ready-army-int-bravo-01-002",
            "system_instance_id": "army-int-bravo-01",
            "readiness_state": "LIMITED",
            "health_score": 0.78,
            "reason_code": "CLOCK_ALIGNMENT_DELAY_REVIEW",
            "effective_at_utc": delayed_event["event_time_utc"],
            "recorded_at_utc": operator_hold["event_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "readiness_event_id": "ready-army-int-bravo-01-003",
            "system_instance_id": "army-int-bravo-01",
            "readiness_state": "READY",
            "health_score": 0.94,
            "reason_code": "CORRECTIVE_ACTION_APPLIED",
            "effective_at_utc": operator_resume["event_time_utc"],
            "recorded_at_utc": readiness_recovery["event_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
    ]
    maintenance_action_rows = [
        {
            "maintenance_action_id": "maint-patriot-bravo-02-001",
            "system_instance_id": "patriot-bravo-02",
            "work_order_id": "wo-synthetic-001",
            "action_type": "CLOCK_BUFFER_RECALIBRATION",
            "status": "COMPLETE",
            "reason_code": "SYNTHETIC_COMPONENT_CONDITION",
            "started_at_utc": _format_utc(START_TIME + timedelta(seconds=75)),
            "completed_at_utc": _format_utc(START_TIME + timedelta(seconds=135)),
            "updated_at_utc": _format_utc(START_TIME + timedelta(seconds=135)),
            "classification": "SYNTHETIC_UNCLASS",
        }
    ]
    inventory_position_rows = [
        {
            "system_instance_id": "patriot-bravo-01",
            "inventory_category": "PARTS_BUFFER",
            "quantity_available": 4,
            "quantity_required": 3,
            "updated_at_utc": observed_manifest["start_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "system_instance_id": "patriot-bravo-02",
            "inventory_category": "TIMING_MODULE",
            "quantity_available": 1,
            "quantity_required": 1,
            "updated_at_utc": observed_manifest["start_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "system_instance_id": "thaad-charlie-01",
            "inventory_category": "TEST_PARTICIPATION_KIT",
            "quantity_available": 2,
            "quantity_required": 1,
            "updated_at_utc": observed_manifest["start_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
    ]
    finding_rows = [
        {
            "finding_id": "finding-clock-alignment-001",
            "test_event_id": observed_manifest["test_event_id"],
            "severity": "MEDIUM",
            "finding_status": "OPEN",
            "finding_title": "Synthetic clock-alignment delay affected one assignment acknowledgement",
            "finding_summary": "Observed assignment acknowledgement lag exceeded the predicted baseline and aligned with network and instrumentation evidence.",
            "identified_at_utc": delayed_event["event_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        }
    ]
    finding_evidence_rows = [
        {
            "finding_evidence_id": "evidence-001",
            "finding_id": "finding-clock-alignment-001",
            "evidence_source": "observed_eventstream",
            "evidence_reference": delayed_event["event_id"],
            "evidence_type": delayed_event["event_type"],
            "recorded_at_utc": delayed_event["event_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "finding_evidence_id": "evidence-002",
            "finding_id": "finding-clock-alignment-001",
            "evidence_source": "observed_eventstream",
            "evidence_reference": instrumentation_degraded["event_id"],
            "evidence_type": instrumentation_degraded["event_type"],
            "recorded_at_utc": instrumentation_degraded["event_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "finding_evidence_id": "evidence-003",
            "finding_id": "finding-clock-alignment-001",
            "evidence_source": "observed_eventstream",
            "evidence_reference": network_degraded["event_id"],
            "evidence_type": network_degraded["event_type"],
            "recorded_at_utc": network_degraded["event_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "finding_evidence_id": "evidence-004",
            "finding_id": "finding-clock-alignment-001",
            "evidence_source": "observed_eventstream",
            "evidence_reference": operator_hold["event_id"],
            "evidence_type": operator_hold["event_type"],
            "recorded_at_utc": operator_hold["event_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "finding_evidence_id": "evidence-005",
            "finding_id": "finding-clock-alignment-001",
            "evidence_source": "observed_eventstream",
            "evidence_reference": safety_evidence["event_id"],
            "evidence_type": safety_evidence["event_type"],
            "recorded_at_utc": safety_evidence["event_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "finding_evidence_id": "evidence-006",
            "finding_id": "finding-clock-alignment-001",
            "evidence_source": "postgresql",
            "evidence_reference": "ready-army-int-bravo-01-002",
            "evidence_type": "readiness_history",
            "recorded_at_utc": operator_hold["event_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        },
    ]
    corrective_action_rows = [
        {
            "corrective_action_id": "action-clock-alignment-001",
            "finding_id": "finding-clock-alignment-001",
            "action_title": "Recalibrate timing cell and preserve reporting limitation",
            "action_status": "IN_PROGRESS",
            "owner_role": "role-data-control",
            "due_time_utc": _format_utc(START_TIME + timedelta(days=7)),
            "recorded_at_utc": operator_resume["event_time_utc"],
            "classification": "SYNTHETIC_UNCLASS",
        }
    ]
    report_review_rows = [
        {
            "report_review_id": "review-quicklook-001",
            "test_event_id": observed_manifest["test_event_id"],
            "report_stage": "QUICKLOOK",
            "reviewer_role": "role-test-director",
            "review_status": "APPROVED",
            "review_time_utc": _format_utc(START_TIME + timedelta(minutes=20)),
            "classification": "SYNTHETIC_UNCLASS",
        },
        {
            "report_review_id": "review-final-001",
            "test_event_id": observed_manifest["test_event_id"],
            "report_stage": "FINAL",
            "reviewer_role": "role-independent-evaluator",
            "review_status": "PENDING",
            "review_time_utc": "",
            "classification": "SYNTHETIC_UNCLASS",
        },
    ]

    return {
        "postgres_test_event": test_event_rows,
        "postgres_test_objective": objective_rows,
        "postgres_required_feed": required_feed_rows,
        "postgres_site": site_rows,
        "postgres_system_instance": system_instance_rows,
        "postgres_readiness_history_batch01": readiness_history_batch01,
        "postgres_readiness_history_batch02": readiness_history_batch02,
        "postgres_maintenance_action": maintenance_action_rows,
        "postgres_inventory_position": inventory_position_rows,
        "postgres_finding": finding_rows,
        "postgres_finding_evidence": finding_evidence_rows,
        "postgres_corrective_action": corrective_action_rows,
        "postgres_report_review": report_review_rows,
    }


def _postgres_batch_manifest(rows_by_file: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    load_order = [
        ("postgres_test_event", 1, "test_event_id", "planned_start_time_utc"),
        ("postgres_test_objective", 2, "objective_id", "objective_name"),
        ("postgres_required_feed", 3, "required_feed_id", "feed_name"),
        ("postgres_site", 4, "site_id", "updated_at_utc"),
        ("postgres_system_instance", 5, "system_instance_id", "updated_at_utc"),
        ("postgres_readiness_history_batch01", 6, "readiness_event_id", "effective_at_utc"),
        ("postgres_readiness_history_batch02", 7, "readiness_event_id", "effective_at_utc"),
        ("postgres_maintenance_action", 8, "maintenance_action_id", "updated_at_utc"),
        ("postgres_inventory_position", 9, "system_instance_id|inventory_category", "updated_at_utc"),
        ("postgres_finding", 10, "finding_id", "identified_at_utc"),
        ("postgres_finding_evidence", 11, "finding_evidence_id", "recorded_at_utc"),
        ("postgres_corrective_action", 12, "corrective_action_id", "recorded_at_utc"),
        ("postgres_report_review", 13, "report_review_id", "review_time_utc"),
    ]
    return {
        "schema_version": "1.0.0",
        "database_engine": POSTGRES_ENGINE,
        "schema_name": "mda_ops",
        "batches": [
            {
                "table_name": name.replace("postgres_", ""),
                "path": _relative(CSV_PATHS[name]),
                "load_order": order,
                "primary_key": primary_key,
                "watermark_column": watermark_column,
                "row_count": len(rows_by_file[name]),
                "sha256": _hash_rows(rows_by_file[name]),
            }
            for name, order, primary_key, watermark_column in load_order
        ],
    }


def _contract_examples(observed_records: list[dict[str, Any]]) -> dict[Path, Any]:
    events_by_type: dict[str, dict[str, Any]] = {}
    for record in observed_records:
        event = record["event"]
        events_by_type.setdefault(event["event_type"], event)

    outputs: dict[Path, Any] = {}
    examples_dir = ROOT / "01-contracts" / "examples"
    for base_name, event_type, missing_field in EXAMPLE_SPECS:
        positive = copy.deepcopy(events_by_type[event_type])
        negative = copy.deepcopy(positive)
        negative.pop(missing_field, None)
        outputs[examples_dir / f"{base_name}.positive.json"] = positive
        outputs[examples_dir / f"{base_name}.negative.json"] = negative
    return outputs


def _demo_manifest(
    observed_manifest: dict[str, Any],
    observed_records: list[dict[str, Any]],
    predicted_products: dict[str, Any],
    rows_by_file: dict[str, list[dict[str, Any]]],
    postgres_manifest: dict[str, Any],
) -> dict[str, Any]:
    event_counts = Counter(record["topic"] for record in observed_records)
    delayed_event = next(
        record["event"]
        for record in observed_records
        if record["event"]["event_type"] == "command.integration"
        and record["event"]["status"] == "DELAYED"
    )
    return {
        "demo_id": DEMO_ID,
        "title": DEMO_TITLE,
        "classification": "SYNTHETIC_UNCLASS",
        "no_execution_claims": "This folder provides a deterministic local capstone package only. It does not claim that Kubernetes, Eventstream, Eventhouse, PostgreSQL, ADLS, or Fabric items were deployed or executed from this repository.",
        "scenario_id": observed_manifest["scenario_id"],
        "observed_run_manifest_id": observed_manifest["run_manifest_id"],
        "predicted_run_manifest_id": predicted_products["manifest"]["simulation_run_id"],
        "observed_event_count": len(observed_records),
        "observed_event_topics": dict(event_counts),
        "delayed_event_id": delayed_event["event_id"],
        "delayed_target_instance_id": delayed_event["source_instance_id"],
        "artifacts": [
            {
                "path": _relative(OBSERVED_STREAM_PATH),
                "role": "Observed streaming fallback package",
                "row_count": len(observed_records),
            },
            {
                "path": _relative(STARTUP_MANIFEST_PATH),
                "role": "Persisted startup seed and source identity manifest",
                "row_count": len(observed_manifest["sources"]),
            },
            {
                "path": _relative(POSTGRES_BATCH_MANIFEST_PATH),
                "role": "PostgreSQL batch load order and checksums",
                "row_count": len(postgres_manifest["batches"]),
            },
            {
                "path": _relative(PREDICTED_TRACKS_PATH),
                "role": "ADLS baseline predicted tracks",
                "row_count": len(predicted_products["predicted_tracks"]),
            },
            {
                "path": _relative(PREDICTED_EVENTS_PATH),
                "role": "ADLS baseline predicted command events",
                "row_count": len(predicted_products["predicted_events"]),
            },
            {
                "path": _relative(PREDICTED_MEASURES_PATH),
                "role": "ADLS baseline predicted measures",
                "row_count": len(predicted_products["predicted_measures"]),
            },
            {
                "path": _relative(ENVIRONMENTAL_ASSUMPTIONS_PATH),
                "role": "ADLS baseline environmental assumptions",
                "row_count": len(predicted_products["environmental_assumptions"]),
            },
        ]
        + [
            {
                "path": _relative(CSV_PATHS[name]),
                "role": name.replace("postgres_", "PostgreSQL ").replace("_", " "),
                "row_count": len(rows),
            }
            for name, rows in rows_by_file.items()
        ],
    }


def expected_assets() -> dict[str, Any]:
    observed_manifest, observed_records = _observed_stream()
    predicted_products = _predicted_products()
    rows_by_file = _postgres_rows(observed_manifest, observed_records)
    postgres_manifest = _postgres_batch_manifest(rows_by_file)
    fallback_manifest = {
        "schema_version": "1.0.0",
        "bundle_id": "fallback-demo07-integrated-001",
        "classification": "SYNTHETIC_UNCLASS",
        "scenario_id": observed_manifest["scenario_id"],
        "observed_run_manifest_id": observed_manifest["run_manifest_id"],
        "observed_event_count": len(observed_records),
        "observed_event_sha256": _hash_rows(observed_records),
        "postgres_batch_manifest": _relative(POSTGRES_BATCH_MANIFEST_PATH),
        "baseline_manifest": _relative(BASELINE_MANIFEST_PATH),
    }
    demo_manifest = _demo_manifest(
        observed_manifest,
        observed_records,
        predicted_products,
        rows_by_file,
        postgres_manifest,
    )
    contract_examples = _contract_examples(observed_records)
    return {
        "observed_manifest": observed_manifest,
        "observed_records": observed_records,
        "predicted_products": predicted_products,
        "rows_by_file": rows_by_file,
        "postgres_manifest": postgres_manifest,
        "fallback_manifest": fallback_manifest,
        "demo_manifest": demo_manifest,
        "contract_examples": contract_examples,
    }


def write_assets() -> None:
    assets = expected_assets()
    _write_json(STARTUP_MANIFEST_PATH, assets["observed_manifest"])
    _write_jsonl(OBSERVED_STREAM_PATH, assets["observed_records"])
    _write_json(POSTGRES_BATCH_MANIFEST_PATH, assets["postgres_manifest"])
    _write_json(FALLBACK_MANIFEST_PATH, assets["fallback_manifest"])

    predicted = assets["predicted_products"]
    _write_jsonl(PREDICTED_TRACKS_PATH, predicted["predicted_tracks"])
    _write_jsonl(PREDICTED_EVENTS_PATH, predicted["predicted_events"])
    _write_jsonl(PREDICTED_MEASURES_PATH, predicted["predicted_measures"])
    _write_jsonl(ENVIRONMENTAL_ASSUMPTIONS_PATH, predicted["environmental_assumptions"])
    _write_json(BASELINE_MANIFEST_PATH, predicted["manifest"])

    for name, rows in assets["rows_by_file"].items():
        _write_csv(CSV_PATHS[name], rows)

    for path, payload in assets["contract_examples"].items():
        _write_json(path, payload)

    _write_json(DEMO_MANIFEST_PATH, assets["demo_manifest"])
    print(f"Shared release {RELEASE_ID} assets written")


def _normalize_csv_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append(
            {
                key: "" if value is None else str(value)
                for key, value in row.items()
            }
        )
    return normalized


def _validate_contracts(assets: dict[str, Any]) -> None:
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"jsonschema\.RefResolver is deprecated.*",
                category=DeprecationWarning,
            )
            from jsonschema import Draft202012Validator, RefResolver
            from jsonschema.exceptions import ValidationError
    except ImportError:
        print("Contract schemas: SKIPPED (jsonschema not installed in this interpreter)")
        return

    contract_root = ROOT / "01-contracts"
    store: dict[str, Any] = {}
    for path in contract_root.rglob("*.schema.json"):
        schema = _read_json(path)
        store[path.resolve().as_uri()] = schema
        if "$id" in schema:
            store[schema["$id"]] = schema

    schema_paths = {
        "sensor-observation": contract_root / "events" / "sensor-observation.schema.json",
        "system-status": contract_root / "events" / "system-status.schema.json",
        "command-integration": contract_root / "events" / "command-integration.schema.json",
        "sustainment": contract_root / "events" / "sustainment.schema.json",
        "target-telemetry": contract_root / "events" / "target-telemetry.schema.json",
        "interceptor-telemetry": contract_root / "events" / "interceptor-telemetry.schema.json",
        "instrumentation-observation": contract_root / "events" / "instrumentation-observation.schema.json",
        "groundtruth-observation": contract_root / "events" / "groundtruth-observation.schema.json",
        "environment-observation": contract_root / "events" / "environment-observation.schema.json",
        "instrumentation-health": contract_root / "events" / "instrumentation-health.schema.json",
        "network-health": contract_root / "events" / "network-health.schema.json",
        "readiness-poll": contract_root / "events" / "readiness-poll.schema.json",
        "operator-test-event": contract_root / "events" / "operator-test-event.schema.json",
        "safety-status": contract_root / "events" / "safety-status.schema.json",
    }
    observed_by_type: dict[str, dict[str, Any]] = {}
    for record in assets["observed_records"]:
        observed_by_type.setdefault(record["event"]["event_type"], record["event"])

    for schema_path in contract_root.rglob("*.schema.json"):
        schema = _read_json(schema_path)
        Draft202012Validator.check_schema(schema)

    for base_name, event_type, _ in EXAMPLE_SPECS:
        schema = _read_json(schema_paths[base_name])
        resolver = RefResolver(
            base_uri=schema_paths[base_name].resolve().as_uri(),
            referrer=schema,
            store=store,
        )
        validator = Draft202012Validator(schema, resolver=resolver)
        validator.validate(_read_json(ROOT / "01-contracts" / "examples" / f"{base_name}.positive.json"))
        validator.validate(observed_by_type[event_type])
        try:
            validator.validate(_read_json(ROOT / "01-contracts" / "examples" / f"{base_name}.negative.json"))
        except ValidationError:
            continue
        raise RuntimeError(f"Negative contract example unexpectedly validated: {base_name}")
    print("Contract schemas: OK")


def validate() -> None:
    assets = expected_assets()

    if _read_json(STARTUP_MANIFEST_PATH) != assets["observed_manifest"]:
        raise RuntimeError("Startup manifest does not match expected deterministic content")
    if _read_jsonl(OBSERVED_STREAM_PATH) != assets["observed_records"]:
        raise RuntimeError("Observed eventstream does not match expected deterministic content")
    if _read_json(POSTGRES_BATCH_MANIFEST_PATH) != assets["postgres_manifest"]:
        raise RuntimeError("PostgreSQL batch manifest does not match expected content")
    if _read_json(FALLBACK_MANIFEST_PATH) != assets["fallback_manifest"]:
        raise RuntimeError("Fallback bundle manifest does not match expected content")

    predicted = assets["predicted_products"]
    if _read_jsonl(PREDICTED_TRACKS_PATH) != predicted["predicted_tracks"]:
        raise RuntimeError("Predicted tracks do not match expected content")
    if _read_jsonl(PREDICTED_EVENTS_PATH) != predicted["predicted_events"]:
        raise RuntimeError("Predicted events do not match expected content")
    if _read_jsonl(PREDICTED_MEASURES_PATH) != predicted["predicted_measures"]:
        raise RuntimeError("Predicted measures do not match expected content")
    if _read_jsonl(ENVIRONMENTAL_ASSUMPTIONS_PATH) != predicted["environmental_assumptions"]:
        raise RuntimeError("Environmental assumptions do not match expected content")
    if _read_json(BASELINE_MANIFEST_PATH) != predicted["manifest"]:
        raise RuntimeError("Baseline manifest does not match expected content")

    for name, expected_rows in assets["rows_by_file"].items():
        if _read_csv(CSV_PATHS[name]) != _normalize_csv_rows(expected_rows):
            raise RuntimeError(f"CSV content mismatch for {CSV_PATHS[name].name}")

    for path, payload in assets["contract_examples"].items():
        if _read_json(path) != payload:
            raise RuntimeError(f"Contract example mismatch for {path.name}")

    if _read_json(DEMO_MANIFEST_PATH) != assets["demo_manifest"]:
        raise RuntimeError("Demo manifest does not match expected content")

    delayed = [
        record["event"]
        for record in assets["observed_records"]
        if record["event"]["event_type"] == "command.integration"
        and record["event"]["status"] == "DELAYED"
    ]
    if len(delayed) != 1:
        raise RuntimeError(f"Expected exactly one delayed command event, found {len(delayed)}")

    operator_decisions = [
        record["event"]
        for record in assets["observed_records"]
        if record["event"]["event_type"] == "operator.test_event"
    ]
    if any(event["decision_authority"] != "HUMAN_AUTHORITY" for event in operator_decisions):
        raise RuntimeError("Operator test events lost their authoritative human-decision boundary")

    safety_events = [
        record["event"]
        for record in assets["observed_records"]
        if record["event"]["event_type"] == "safety.status"
    ]
    if any(event["authority_scope"] != "EVIDENCE_ONLY" for event in safety_events):
        raise RuntimeError("Safety status events lost their advisory-only boundary")

    _validate_contracts(assets)
    print(
        f"Shared release {RELEASE_ID} validation: OK "
        f"({len(assets['observed_records'])} observed events; "
        f"{len(assets['rows_by_file'])} PostgreSQL batch files)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and validate the shared integrated-test release")
    parser.add_argument("command", choices=("write-assets", "validate", "summary"))
    args = parser.parse_args()

    if args.command == "write-assets":
        write_assets()
    elif args.command == "validate":
        validate()
    else:
        assets = expected_assets()
        counts = Counter(record["topic"] for record in assets["observed_records"])
        delayed_event = next(
            record["event"]
            for record in assets["observed_records"]
            if record["event"]["event_type"] == "command.integration"
            and record["event"]["status"] == "DELAYED"
        )
        print(
            json.dumps(
                {
                    "scenario_id": assets["observed_manifest"]["scenario_id"],
                    "observed_event_count": len(assets["observed_records"]),
                    "topic_counts": dict(counts),
                    "delayed_event_id": delayed_event["event_id"],
                    "delayed_source_instance_id": delayed_event["source_instance_id"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()