"""Collect local/fixture live-test evidence without cloud access or credentials.

CLI inputs: --manifest and --execution are JSON objects; --telemetry and
--diagnostics are JSON arrays or JSONL files (empty files mean absent evidence).
--output-directory is the immutable bundle directory, not a cloud destination.
Use a new output directory for a later collection revision. Identical sanitized
inputs produce identical bytes; a conflicting existing bundle is rejected.

APIs: collect_evidence(manifest, telemetry, diagnostics, execution) -> summary;
write_bundle(manifest, telemetry, diagnostics, execution, output_directory)
-> Path. Iterables may contain event dicts or Kafka {topic, key, event} wrappers.

Summary schema live-test-evidence.v1:
    run_id: UUID; execution: {execution_id: str, status: uppercase known or UNKNOWN}
    evidence_state: COMPLETE | INCOMPLETE; collection_state: COLLECTED | COLLECTING
    channels: {tspi, temperature, error: {expected, received, duplicates, missing,
                                                                         unexpected: int}}
    counts: {telemetry_records, diagnostic_records, unrelated_telemetry,
                     unrelated_diagnostics, invalid_telemetry, invalid_diagnostics,
                     conflicting_events, duplicate_diagnostics: int}
    sequence: {expected_first, expected_last, missing: int}
    diagnostics: {started, terminal: int, terminal_kinds: [str], complete: bool,
                                emitted_counts_meaning: attempted_enqueues}
    provenance: {source: local_file_inputs, stdout_acquired: false,
                             stderr_acquired: false, raw_stdout_retained: false,
                             raw_stderr_retained: false, telemetry_delivery_verified: false,
                             execution_linkage: manifest_membership_only,
                             telemetry_scope: identity_and_measurement_fingerprint}

Bundle files: manifest.json (sanitized manifest projection), summary.json,
telemetry.json (sorted unique sanitized identity records), diagnostics.json
(sorted unique whitelisted structured records), bundle.json. The bundle index
has schema_version live-test-bundle.v1, run_id, execution_id, and files mapping
each other filename to {sha256: hex, size_bytes: int}. It is not self-hashed.

The live-test-collector-manifest.v1 projection is a whitelisted subset, not a
validated live-test-run.v1 request. It preserves exact, shape-checked catalog,
input and asset pins and local/non-deployable declarations. Missing pins are
null and listed in projection.unavailable_pins; unknown metadata is omitted.
Its evidence_state is COLLECTED/COLLECTING, while the summary uses
COMPLETE/INCOMPLETE. rehearse_live_test.py separately persists the full request.
No input bytes, image resolution, contract chain or authorization are verified.
Unknown log fields, exception payloads, credentials, and telemetry measurement
payloads are never retained. Valid synthetic channel data is fingerprinted with
SHA256 over sorted-key, compact, ASCII JSON (no NaN/Infinity). Missing data has
a null measurement_sha256 and UNAVAILABLE measurement_status and cannot prove
completeness. This is finite shape validation, not physical/model validation.
Malformed evidence is counted, not copied. Counts are capped at 360,000 per
channel (the local contract maximum of 3600 seconds at 100 Hz).

Inputs are supplied local evidence, not acquired job stdout/stderr or verified
broker receipts. Terminal emitted_counts are attempted enqueues, not receipts.
Run-scoped records cannot distinguish multiple executions of the same run;
execution linkage proves manifest membership only. No Azure export is performed.
"""

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from uuid import UUID


CHANNELS = ("tspi", "temperature", "error")
MAX_EXPECTED_PER_CHANNEL = 360_000
STATUSES = {"PENDING", "RUNNING", "PROCESSING", "SUCCEEDED", "FAILED", "CANCELED", "CANCELLED", "UNKNOWN"}
KINDS = {"started", "completed", "canceled", "failed"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
INPUT_PINS = ("product_id", "version", "sha256", "uri", "contract_version")
ASSET_PINS = ("asset_id", "version", "image_digest", "digest_kind", "deployable", "input_contract", "output_contract")
CONTRACT_PINS = {"synthetic-scenario.v1", "live-test-input.v1", "live-test-events.v1", "live-test-output.v1"}
MEASUREMENT_FIELDS = {
    "tspi": {"latitude_deg", "longitude_deg", "altitude_m"},
    "temperature": {"temperature_c"},
    "error": {"error_word"},
}


def _identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Expected a bounded identifier")
    return value


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError("Expected a UUID")
    try:
        if str(UUID(value)) != value:
            raise ValueError("Expected a canonical UUID")
    except (ValueError, AttributeError):
        raise ValueError("Expected a canonical UUID") from None
    return value


def _number(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Expected a finite positive number")
    return value


def _integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("Expected a nonnegative integer")
    return value


def _seed(value):
    if type(value) is not int:
        raise ValueError("Expected an integer seed")
    return value


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Expected a timezone-aware timestamp")
    value = re.sub(r"(\.[0-9]{6})0+(?=Z$|[+-][0-9]{2}:[0-9]{2}$)", r"\1", value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Expected a timezone-aware timestamp") from None
    if parsed.utcoffset() is None:
        raise ValueError("Expected a timezone-aware timestamp")
    return value


def _expected_count(duration, rate):
    duration, rate = _number(duration), _number(rate)
    if _number(duration * rate) > MAX_EXPECTED_PER_CHANNEL or MAX_EXPECTED_PER_CHANNEL / rate < duration:
        raise ValueError("Expected count exceeds collector limit")
    lower, upper = 1, MAX_EXPECTED_PER_CHANNEL
    while lower < upper:
        middle = (lower + upper) // 2
        if middle / rate < duration:
            lower = middle + 1
        else:
            upper = middle
    return lower


def _context(manifest, execution):
    if manifest.get("schema_version") not in ("live-test-run.v1", "live-test-acquired-run.v1"):
        raise ValueError("Unsupported manifest schema")
    run_id = _uuid(manifest.get("run_id"))
    _uuid(manifest.get("request_id"))
    _seed(manifest.get("seed"))
    parameters = manifest["parameters"]
    duration = _number(parameters["duration_seconds"])
    expected = {channel: _expected_count(duration, _number(parameters[f"{channel}_hz"])) for channel in CHANNELS}
    execution_id = _identifier(execution.get("execution_id"))
    if sum(entry.get("execution_id") == execution_id for entry in manifest["executions"]) != 1:
        raise ValueError("Execution ID is not registered exactly once in manifest")
    if execution.get("run_id", run_id) != run_id:
        raise ValueError("Execution run ID does not match manifest")
    status = execution.get("status", "UNKNOWN")
    if not isinstance(status, str) or status.upper() not in STATUSES:
        status = "UNKNOWN"
    return run_id, expected, {"execution_id": execution_id, "status": status.upper()}


def _measurement_hash(event):
    if "synthetic" in event and event["synthetic"] is not True:
        raise ValueError("Expected synthetic telemetry")
    if "data" not in event:
        return None
    data = event["data"]
    if event.get("synthetic") is not True or not isinstance(data, dict) or set(data) != MEASUREMENT_FIELDS[event["channel"]]:
        raise ValueError("Expected synthetic channel measurement data")
    try:
        finite = all(type(value) in (int, float) and math.isfinite(value) for value in data.values())
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("Expected finite numeric measurements")
    if event["channel"] == "error" and (type(data["error_word"]) is not int or data["error_word"] < 0):
        raise ValueError("Expected a nonnegative integer error word")
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _event(record, run_id, expected):
    event = record.get("event", record)
    if not isinstance(event, dict) or not isinstance(event.get("run_id"), str):
        raise ValueError("Telemetry has no run identity")
    if event["run_id"] != run_id:
        return None
    sequence = _integer(event.get("sequence_number"))
    if not 1 <= sequence <= sum(expected.values()):
        raise ValueError("Telemetry sequence is outside the requested run")
    if event.get("event_id") != f"{run_id}:{sequence}" or event.get("channel") not in CHANNELS:
        raise ValueError("Invalid event identity or channel")
    if event.get("schema_version") != "target-vehicle.v1":
        raise ValueError("Unsupported telemetry schema")
    measurement_hash = _measurement_hash(event)
    return {
        "schema_version": "target-vehicle.v1", "run_id": run_id,
        "vehicle_id": _identifier(event.get("vehicle_id")),
        "event_id": event["event_id"], "sequence_number": sequence,
        "channel": event["channel"], "event_time_utc": _timestamp(event.get("event_time_utc")),
        "startup_seed": _seed(event.get("startup_seed")),
        "measurement_sha256": measurement_hash,
        "measurement_status": "FINITE_SYNTHETIC_SHAPE" if measurement_hash is not None else "UNAVAILABLE",
    }


def _diagnostic(record, run_id):
    if not isinstance(record, dict) or not isinstance(record.get("run_id"), str):
        raise ValueError("Diagnostic has no run identity")
    if record["run_id"] != run_id:
        return None
    if record.get("schema_version") != "live-test-diagnostic.v1" or record.get("kind") not in KINDS:
        raise ValueError("Unsupported diagnostic schema or kind")
    clean = {
        "schema_version": "live-test-diagnostic.v1", "run_id": run_id,
        "vehicle_id": _identifier(record.get("vehicle_id")),
        "event_time_utc": _timestamp(record.get("event_time_utc")),
        "kind": record["kind"], "seed": _seed(record.get("seed")),
    }
    if clean["kind"] == "started":
        clean["duration_seconds"] = _number(record.get("duration_seconds"))
        clean["rates"] = {channel: _number(record["rates"][channel]) for channel in CHANNELS}
    else:
        clean["emitted_counts"] = {channel: _integer(record["emitted_counts"][channel]) for channel in CHANNELS}
    return clean


def collect_evidence(manifest, telemetry, diagnostics, execution):
    """Return a deterministic summary; never infer receipt from execution status.

    Events use the target-vehicle.v1 global 1-based sequence and run:sequence ID.
    Unrelated runs are counted and ignored; malformed matching evidence prevents
    completeness. Duplicate identities with identical measurement fingerprints
    do not increase received counts; missing measurements cannot prove completeness.
    """
    run_id, expected, known_execution = _context(manifest, execution)
    channels = {channel: {"expected": count, "received": 0, "duplicates": 0, "missing": count, "unexpected": 0}
                for channel, count in expected.items()}
    candidates = {}
    counts = Counter()
    for record in telemetry:
        counts["telemetry_records"] += 1
        try:
            event = _event(record, run_id, expected)
            if event is None:
                counts["unrelated_telemetry"] += 1
                continue
            if event["startup_seed"] != manifest["seed"]:
                raise ValueError("Telemetry seed mismatch")
            if record.get("execution_id", known_execution["execution_id"]) != known_execution["execution_id"]:
                raise ValueError("Telemetry execution mismatch")
            if record.get("event", record).get("execution_id", known_execution["execution_id"]) != known_execution["execution_id"]:
                raise ValueError("Telemetry execution mismatch")
        except (ValueError, TypeError, KeyError, AttributeError):
            counts["invalid_telemetry"] += 1
            continue
        if event["measurement_sha256"] is None:
            counts["unavailable_measurements"] += 1
        identity = event["event_id"]
        candidates.setdefault(identity, []).append(event)
    events = {}
    for identity, observations in candidates.items():
        variants = Counter(_json_bytes(event) for event in observations)
        for encoded, occurrences in variants.items():
            channels[json.loads(encoded)["channel"]]["duplicates"] += occurrences - 1
        if len(variants) > 1:
            counts["conflicting_events"] += len(variants) - 1
        else:
            events[identity] = observations[0]
            channels[observations[0]["channel"]]["received"] += 1
    logs = []
    for record in diagnostics:
        counts["diagnostic_records"] += 1
        try:
            log = _diagnostic(record, run_id)
            if log is None:
                counts["unrelated_diagnostics"] += 1
                continue
            if log["seed"] != manifest["seed"]:
                raise ValueError("Diagnostic seed mismatch")
            if record.get("execution_id", known_execution["execution_id"]) != known_execution["execution_id"]:
                raise ValueError("Diagnostic execution mismatch")
        except (ValueError, TypeError, KeyError, AttributeError):
            counts["invalid_diagnostics"] += 1
            continue
        if log in logs:
            counts["duplicate_diagnostics"] += 1
        else:
            logs.append(log)
    for stats in channels.values():
        stats["missing"] = max(0, stats["expected"] - stats["received"])
        stats["unexpected"] = max(0, stats["received"] - stats["expected"])
    starts = [log for log in logs if log["kind"] == "started"]
    terminals = [log for log in logs if log["kind"] != "started"]
    diagnostic_complete = len(starts) == len(terminals) == 1
    if diagnostic_complete:
        start, terminal = starts[0], terminals[0]
        diagnostic_complete = (
            terminal["kind"] == "completed" and terminal["emitted_counts"] == expected
            and start["duration_seconds"] == manifest["parameters"]["duration_seconds"]
            and all(start["rates"][channel] == manifest["parameters"][f"{channel}_hz"] for channel in CHANNELS)
            and start["vehicle_id"] == terminal["vehicle_id"]
            and datetime.fromisoformat(start["event_time_utc"].replace("Z", "+00:00"))
            <= datetime.fromisoformat(terminal["event_time_utc"].replace("Z", "+00:00"))
            and all(event["vehicle_id"] == start["vehicle_id"] for event in events.values())
        )
    missing_sequences = sum(expected.values()) - len(events)
    complete = (diagnostic_complete and not missing_sequences
                and not any(stats["missing"] or stats["unexpected"] for stats in channels.values())
                and not any(counts[key] for key in ("invalid_telemetry", "invalid_diagnostics", "conflicting_events",
                                                    "unavailable_measurements")))
    return {
        "schema_version": "live-test-evidence.v1", "run_id": run_id,
        "execution": known_execution,
        "evidence_state": "COMPLETE" if complete else "INCOMPLETE",
        "collection_state": "COLLECTED" if complete else "COLLECTING",
        "channels": channels,
        "counts": {key: counts[key] for key in (
            "telemetry_records", "diagnostic_records", "unrelated_telemetry", "unrelated_diagnostics",
            "invalid_telemetry", "invalid_diagnostics", "conflicting_events", "duplicate_diagnostics",
            "unavailable_measurements")},
        "sequence": {"expected_first": 1, "expected_last": sum(expected.values()), "missing": missing_sequences},
        "diagnostics": {"started": len(starts), "terminal": len(terminals),
                        "terminal_kinds": sorted({log["kind"] for log in terminals}),
                        "complete": bool(diagnostic_complete), "emitted_counts_meaning": "attempted_enqueues"},
        "provenance": {"source": "local_file_inputs", "stdout_acquired": False, "stderr_acquired": False,
                       "raw_stdout_retained": False, "raw_stderr_retained": False,
                       "telemetry_delivery_verified": False, "execution_linkage": "manifest_membership_only",
                       "telemetry_scope": "identity_and_measurement_fingerprint",
                       "measurement_validation": "finite_synthetic_shape_only"},
    }


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def _safe_label(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@ -]{0,127}", value):
        return "REDACTED"
    if re.search(r"(?i)bearer|password|secret|token|credential|authorization|connectionstring|sharedaccess", value):
        return "REDACTED"
    return value


def _pin_value(field, value):
    if field in ("deployable", "synthetic"):
        if value is not (field == "synthetic"):
            raise ValueError("Expected a synthetic, non-deployable declaration")
        return value
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise ValueError("Expected a bounded structured pin")
    if field in ("catalog_id", "product_id", "asset_id"):
        return _identifier(value)
    if field == "version":
        valid = len(value) <= 128 and re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value)
    elif field in ("sha256", "image_digest"):
        valid = re.fullmatch(("sha256:" if field == "image_digest" else "") + r"[0-9a-f]{64}", value)
    elif field == "uri":
        valid = re.fullmatch(r"repo://[A-Za-z0-9_./-]+", value) and all(
            part not in ("", ".", "..") for part in value[len("repo://"):].split("/"))
    elif field in ("contract_version", "input_contract", "output_contract"):
        valid = value in CONTRACT_PINS
    else:
        valid = value == {"requester_kind": "LOCAL_DECLARED", "digest_kind": "SYNTHETIC_PLACEHOLDER"}.get(field)
    if not valid:
        raise ValueError("Invalid structured pin")
    return value


def _project_pins(record, fields, path, unavailable):
    if not isinstance(record, dict):
        raise ValueError("Expected a pin object")
    projected = {}
    for field in fields:
        if field in record:
            projected[field] = _pin_value(field, record[field])
        else:
            projected[field] = None
            unavailable.append(f"{path}{field}")
    return projected


def _manifest_projection(manifest, summary):
    unavailable = []
    declarations = _project_pins(manifest, ("catalog_id", "requester_kind", "synthetic", "deployable"), "", unavailable)
    input_pins = _project_pins(manifest.get("input", {}), INPUT_PINS, "input.", unavailable)
    source_assets = manifest.get("assets", [])
    if not isinstance(source_assets, list):
        raise ValueError("Expected an asset list")
    if not source_assets:
        unavailable.append("assets")
    assets = []
    for index, asset in enumerate(source_assets):
        if isinstance(asset, str):
            asset = {"asset_id": asset}
        projected = _project_pins(asset, ASSET_PINS, f"assets[{index}].", unavailable)
        projected.update({key: _safe_label(asset[key]) for key in ("vehicle_id", "type") if key in asset})
        assets.append(projected)
    return {
        "schema_version": "live-test-collector-manifest.v1", "run_id": summary["run_id"],
        **declarations,
        "projection": {"scope": "whitelisted_subset", "contract_validation": "not_performed",
                       "pin_validation": "shape_only", "unavailable_pins": sorted(unavailable)},
        "request_id": _uuid(manifest["request_id"]),
        "preset_id": _safe_label(manifest.get("preset_id")),
        "requester": _safe_label(manifest.get("requester")), "seed": _seed(manifest["seed"]),
        "created_at": _timestamp(manifest["created_at"]), "assets": assets, "input": input_pins,
        "parameters": {key: _number(manifest["parameters"][key]) for key in
                       ("duration_seconds", "tspi_hz", "temperature_hz", "error_hz")},
        "executions": [summary["execution"]], "telemetry": [], "logs": [], "outputs": [],
        "state": _identifier(manifest["state"]), "evidence_state": summary["collection_state"],
    }


def _retained(records, sanitizer, manifest, execution, expected):
    unique = {}
    for record in records:
        try:
            clean = sanitizer(record, manifest["run_id"], expected) if sanitizer is _event else sanitizer(record, manifest["run_id"])
            if clean is None or clean.get("seed", clean.get("startup_seed")) != manifest["seed"]:
                continue
            if record.get("execution_id", execution["execution_id"]) != execution["execution_id"]:
                continue
            if record.get("event", record).get("execution_id", execution["execution_id"]) != execution["execution_id"]:
                continue
            unique[_json_bytes(clean)] = clean
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return [unique[key] for key in sorted(unique)]


def _matches(directory, files):
    if directory.is_symlink() or not directory.is_dir():
        return False
    if {entry.name for entry in directory.iterdir()} != set(files):
        return False
    return all(not (directory / name).is_symlink() and (directory / name).is_file()
               and (directory / name).read_bytes() == content for name, content in files.items())


def write_bundle(manifest, telemetry, diagnostics, execution, output_directory):
    """Atomically publish one immutable local bundle, or verify an identical retry.

    Atomic directory rename prevents partial bundles. Competing identical writers
    converge; different contents require a new caller-selected revision directory.
    File permissions are owner-only. No wall-clock times or raw inputs are stored.
    """
    telemetry, diagnostics = list(telemetry), list(diagnostics)
    summary = collect_evidence(manifest, telemetry, diagnostics, execution)
    _, expected, known_execution = _context(manifest, execution)
    documents = {
        "manifest.json": _manifest_projection(manifest, summary), "summary.json": summary,
        "telemetry.json": _retained(telemetry, _event, manifest, known_execution, expected),
        "diagnostics.json": _retained(diagnostics, _diagnostic, manifest, known_execution, expected),
    }
    files = {name: _json_bytes(document) for name, document in documents.items()}
    files["bundle.json"] = _json_bytes({
        "schema_version": "live-test-bundle.v1", "run_id": summary["run_id"],
        "execution_id": known_execution["execution_id"],
        "files": {name: {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
                  for name, content in files.items()},
    })
    directory = Path(output_directory).absolute()
    if directory.exists() or directory.is_symlink():
        if _matches(directory, files):
            return directory
        raise ValueError("Conflicting existing bundle; choose a new revision directory")
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".live-test-", dir=directory.parent) as temporary:
        staging = Path(temporary)
        for name, content in files.items():
            descriptor = os.open(staging / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        try:
            os.rename(staging, directory)
        except OSError:
            if not _matches(directory, files):
                raise ValueError("Conflicting existing bundle; choose a new revision directory") from None
    return directory


def _read_records(path):
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        return []
    if text.lstrip().startswith("["):
        records = json.loads(text)
    else:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not isinstance(records, list):
        raise ValueError("Expected JSON records")
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("manifest", "telemetry", "diagnostics", "execution", "output-directory"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        execution = json.loads(Path(args.execution).read_text(encoding="utf-8"))
        write_bundle(manifest, _read_records(args.telemetry), _read_records(args.diagnostics),
                     execution, args.output_directory)
    except (ValueError, TypeError, KeyError, AttributeError, OSError, OverflowError):
        parser.exit(2, "Collection failed: invalid local input or conflicting/unwritable bundle; use a new directory for a revision.\n")
    print("Local evidence bundle written or identical existing bundle verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())