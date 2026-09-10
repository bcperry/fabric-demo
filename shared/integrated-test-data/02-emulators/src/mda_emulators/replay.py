from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def load_json_lines(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"Line {line_number} must contain a JSON object")
            for field in ("event_id", "event_type", "ordering_key"):
                if not record.get(field):
                    raise ValueError(f"Line {line_number} is missing {field}")
            records.append(record)
    if not records:
        raise ValueError(f"No events found in {path}")
    return records


def rebase_event_times(
    records: list[dict[str, Any]], start_time: datetime
) -> list[dict[str, Any]]:
    valid_times = [
        parsed
        for record in records
        if (parsed := parse_rfc3339(record.get("event_time_utc"))) is not None
    ]
    if not valid_times:
        raise ValueError("At least one valid event_time_utc is required for rebasing")

    source_start = min(valid_times)
    rebased = []
    for record in records:
        shifted = dict(record)
        for field in (
            "event_time_utc",
            "ingest_time_utc",
            "preserved_window_start_utc",
            "preserved_window_end_utc",
        ):
            value = parse_rfc3339(record.get(field))
            if value is not None:
                shifted[f"recorded_{field}"] = record[field]
                shifted[field] = format_utc(start_time + (value - source_start))
        rebased.append(shifted)
    return rebased


def paced_records(
    records: list[dict[str, Any]], speed: float
) -> Iterator[tuple[float, dict[str, Any]]]:
    if speed <= 0:
        raise ValueError("speed must be greater than zero")
    previous_time = None
    for record in records:
        event_time = parse_rfc3339(record.get("event_time_utc"))
        delay = 0.0
        if event_time is not None and previous_time is not None:
            delay = max(0.0, (event_time - previous_time).total_seconds() / speed)
        if event_time is not None:
            previous_time = max(previous_time, event_time) if previous_time else event_time
        yield delay, record


def parse_rfc3339(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")