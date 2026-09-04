from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


EVENT_NAMESPACE = uuid.UUID("62de2567-296e-4707-a7ee-3ad06be674bb")


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def create_envelope(
    *,
    scenario: dict[str, Any],
    site_id: str,
    source_system: str,
    source_instance_id: str,
    event_type: str,
    ordering_key: str,
    sequence_number: int,
    event_time: datetime,
    test_event_id: str,
    simulation_run_id: str,
    run_manifest_id: str | None = None,
    startup_seed: int | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> dict[str, Any]:
    event_key = "|".join(
        [
            scenario["scenario_id"],
            source_instance_id,
            event_type,
            ordering_key,
            str(sequence_number),
            utc_text(event_time),
        ]
    )
    return {
        "event_id": str(uuid.uuid5(EVENT_NAMESPACE, event_key)),
        "event_type": event_type,
        "schema_version": "1.0.0",
        "scenario_id": scenario["scenario_id"],
        "simulation_run_id": simulation_run_id,
        "run_manifest_id": run_manifest_id,
        "test_event_id": test_event_id,
        "site_id": site_id,
        "source_system": source_system,
        "source_instance_id": source_instance_id,
        "ordering_key": ordering_key,
        "sequence_number": sequence_number,
        "event_time_utc": utc_text(event_time),
        "ingest_time_utc": utc_text(event_time),
        "startup_seed": startup_seed,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
        "classification": "SYNTHETIC_UNCLASS",
        "location_notice": scenario["location_notice"],
        "synthetic": True,
    }
