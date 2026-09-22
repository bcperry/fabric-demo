"""Pure, stdlib-only P5/P6 synthetic governance. NOT AUTHORIZATION.

Integration seam: refresh_reference -> review_reference -> promote_reference ->
select_reference returns exact bytes/parameters for a local run's input pin.
Keep this state beside, never inside or overwriting, the initial catalog fixtures.
All mutators return deep copies; callers own persistence and concurrency control.
Trusted services must authenticate/authorize actors and supply validated object IDs;
these functions cannot establish identity or human review. No cloud gate is closed.

Versions are ``sha256:<digest>`` of original UTF-8 JSON bytes, not semantic JSON.
REFERENCE_SCHEMA describes the supported JSON Schema subset; the validator also
enforces finite numbers and internal channel rates strictly below TSPI.
Review/promotion are local model states, never certification or permission grants.
"""

import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from uuid import UUID


PARAMETER_LIMITS = {
    "duration_seconds": (1, 3600),
    "tspi_hz": (0.01, 100),
    "temperature_hz": (0.01, 100),
    "error_hz": (0.01, 100),
}
REFERENCE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": list(PARAMETER_LIMITS),
    "properties": {
        name: {"type": "integer" if name == "duration_seconds" else "number",
               "minimum": lower, "maximum": upper}
        for name, (lower, upper) in PARAMETER_LIMITS.items()
    },
}
TAG_RULE_VERSION = "synthetic-reference-tags.v1"
TAG_KEYS = {"source_kind", "rate_profile"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _time(value):
    _require(isinstance(value, str), "expected an aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("expected an aware ISO timestamp") from None
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
             "timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _timestamp(value):
    return _time(value).isoformat()


def _hash(value):
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             "expected lowercase SHA-256")


def _object_id(value):
    _require(isinstance(value, str), "expected object_id UUID")
    try:
        parsed = UUID(value)
    except ValueError:
        raise ValueError("expected object_id UUID") from None
    _require(parsed.int != 0, "object_id cannot be zero")
    return str(parsed)


def _number(value, lower, upper, label):
    _require(type(value) in (int, float) and lower <= value <= upper
             and math.isfinite(value), f"{label}: outside finite bounds")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON field")
        result[key] = value
    return result


def validate_reference(raw, expected_sha256):
    """Return a content-addressed snapshot or raise ValueError; no I/O.

    The schema is deliberately limited to the four synthetic generator parameters.
    Original bytes are retained so replay does not depend on JSON serialization.
    """
    _require(isinstance(raw, bytes), "reference must be bytes")
    _hash(expected_sha256)
    digest = hashlib.sha256(raw).hexdigest()
    _require(digest == expected_sha256, "reference hash mismatch")
    try:
        parameters = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValueError("corrupt reference JSON") from error
    _require(isinstance(parameters, dict) and set(parameters) == set(PARAMETER_LIMITS),
             "reference schema: missing or unknown fields")
    for name, (lower, upper) in PARAMETER_LIMITS.items():
        _number(parameters[name], lower, upper, name)
    _require(type(parameters["duration_seconds"]) is int, "duration_seconds must be integer")
    _require(max(parameters["temperature_hz"], parameters["error_hz"]) < parameters["tspi_hz"],
             "internal channel rates must be below tspi_hz")
    return {"version": "sha256:" + digest, "sha256": digest, "bytes": raw,
            "parameters": parameters, "classification": "SYNTHETIC_UNCLASS",
            "synthetic": True, "permitted_use": "LOCAL_CONTRACT_TEST_ONLY"}


def new_reference_catalog(reference_id):
    """Create a separate local catalog; never reads or writes initial fixtures."""
    _require(isinstance(reference_id, str) and bool(reference_id.strip()), "reference_id required")
    return {"reference_id": reference_id, "snapshots": {}, "reviews": {},
            "promoted": None, "quarantine": [], "history": []}


def refresh_reference(catalog, raw, *, expected_sha256, publisher_object_id,
                      effective_at, received_at, max_age_seconds):
    """Append valid bytes or a quarantine record, preserving every earlier version.

    Bad content/hash/schema is quarantined. Invalid refresh metadata raises.
    Freshness is measured from effective_at, not reset by receipt or promotion.
    Repeating identical content and metadata is idempotent; conflicting metadata
    for an existing version raises rather than silently overwriting its provenance.
    """
    effective = _timestamp(effective_at)
    received = _timestamp(received_at)
    _require(_time(effective) <= _time(received), "effective_at exceeds received_at")
    _number(max_age_seconds, 1, 31536000, "max_age_seconds")
    publisher = _object_id(publisher_object_id)
    result = copy.deepcopy(catalog)
    try:
        snapshot = validate_reference(raw, expected_sha256)
    except ValueError as error:
        result["quarantine"].append({
            "bytes": raw, "expected_sha256": expected_sha256,
            "actual_sha256": hashlib.sha256(raw).hexdigest() if isinstance(raw, bytes) else None,
            "reason": str(error), "effective_at": effective, "received_at": received,
            "publisher_object_id": publisher, "max_age_seconds": max_age_seconds,
        })
        return result
    snapshot.update(publisher_object_id=publisher, effective_at=effective,
                    received_at=received, max_age_seconds=max_age_seconds)
    version = snapshot["version"]
    if version in result["snapshots"]:
        _require(result["snapshots"][version] == snapshot, "immutable version metadata conflict")
        return result
    result["snapshots"][version] = snapshot
    result["reviews"][version] = {"state": "NOT_REVIEWED", "history": []}
    return result


def _pinned(catalog, version, sha256):
    _hash(sha256)
    _require(version == "sha256:" + sha256, "version/hash mismatch")
    _require(version in catalog["snapshots"], "unknown reference version")
    snapshot = catalog["snapshots"][version]
    validated = validate_reference(snapshot["bytes"], sha256)
    _require(all(snapshot.get(key) == value for key, value in validated.items()),
             "snapshot integrity mismatch")
    return snapshot


def review_reference(catalog, *, version, sha256, action, actor, recorded_at, rationale):
    """NOT AUTH: actor={'object_id': UUID} must be validated by the calling service.

    Explicit request_review -> accept/reject only, scoped to exact version/hash.
    Decisions require an actor distinct from the publisher. Terminal decisions
    cannot be rewritten; this local history makes no claim of real human approval.
    """
    snapshot = _pinned(catalog, version, sha256)
    _require(isinstance(actor, dict) and set(actor) == {"object_id"}, "validated actor object required")
    actor_id = _object_id(actor["object_id"])
    _require(isinstance(rationale, str) and bool(rationale.strip()), "rationale required")
    review = catalog["reviews"][version]
    transitions = {("NOT_REVIEWED", "request_review"): "PENDING_REVIEW",
                   ("PENDING_REVIEW", "accept"): "APPROVED",
                   ("PENDING_REVIEW", "reject"): "REJECTED"}
    _require(isinstance(action, str) and (review["state"], action) in transitions,
             "invalid review transition")
    if action != "request_review":
        _require(actor_id != snapshot["publisher_object_id"], "publisher cannot review own version")
    timestamp = _timestamp(recorded_at)
    previous = review["history"][-1]["recorded_at"] if review["history"] else snapshot["received_at"]
    _require(_time(timestamp) >= _time(previous), "review timestamp precedes history")
    result = copy.deepcopy(catalog)
    updated = result["reviews"][version]
    updated["state"] = transitions[(review["state"], action)]
    updated["history"].append({"version": version, "sha256": sha256, "action": action,
                               "actor_object_id": actor_id, "recorded_at": timestamp,
                               "rationale": rationale, "state": updated["state"]})
    return result


def promote_reference(catalog, *, version, sha256, recorded_at):
    """Explicit local promotion of an approved pin; does not grant permissions."""
    _pinned(catalog, version, sha256)
    review = catalog["reviews"][version]
    _require(review["state"] == "APPROVED", "promotion requires approved exact version")
    timestamp = _timestamp(recorded_at)
    previous = review["history"][-1]["recorded_at"]
    _require(_time(timestamp) >= _time(previous), "promotion precedes approval")
    if catalog["history"]:
        _require(_time(timestamp) >= _time(catalog["history"][-1]["recorded_at"]),
                 "promotion precedes history")
    result = copy.deepcopy(catalog)
    pin = {"version": version, "sha256": sha256}
    if result["promoted"] != pin:
        result["promoted"] = pin
        result["history"].append({**pin, "action": "promote", "recorded_at": timestamp})
    return result


def select_reference(catalog, *, now, pin=None, allow_stale_replay=False):
    """Return a detached exact snapshot; never fall back to a different version.

    New runs use the promoted, approved snapshot and must satisfy its max-age SLA.
    Replay supplies {'version', 'sha256'} explicitly; only an explicit replay may
    opt into stale data. Receipt/approval/promotion in the future is always refused.
    """
    _require(type(allow_stale_replay) is bool, "allow_stale_replay must be boolean")
    _require(not allow_stale_replay or pin is not None, "stale replay requires explicit pin")
    chosen = catalog["promoted"] if pin is None else pin
    _require(isinstance(chosen, dict) and set(chosen) == {"version", "sha256"}, "exact pin required")
    snapshot = _pinned(catalog, chosen["version"], chosen["sha256"])
    review = catalog["reviews"][chosen["version"]]
    _require(review["state"] == "APPROVED", "reference is not approved")
    moment = _time(now)
    _require(moment >= _time(snapshot["received_at"]), "reference not yet received")
    _require(moment >= _time(review["history"][-1]["recorded_at"]), "reference not yet approved")
    if pin is None:
        _require(moment >= _time(catalog["history"][-1]["recorded_at"]), "reference not yet promoted")
    age = (moment - _time(snapshot["effective_at"])).total_seconds()
    _require(allow_stale_replay or age <= snapshot["max_age_seconds"], "stale reference refused")
    return copy.deepcopy(snapshot)


def propose_tags(snapshot, *, rule_version=TAG_RULE_VERSION):
    """Deterministic descriptive tags, pinned rule/source provenance; no ACL effects."""
    _require(rule_version == TAG_RULE_VERSION, "unsupported tag rule version")
    validated = validate_reference(snapshot["bytes"], snapshot["sha256"])
    _require(all(snapshot.get(key) == value for key, value in validated.items()),
             "snapshot integrity mismatch")
    return {"rule_version": rule_version, "source_sha256": snapshot["sha256"],
            "source_version": snapshot["version"], "classification": "SYNTHETIC_UNCLASS",
            "tags": {"source_kind": "synthetic-reference",
                     "rate_profile": "high" if snapshot["parameters"]["tspi_hz"] >= 50 else "standard"}}


def apply_tag_proposal(current, proposal, *, manual_overrides=None):
    """Return new tag state; preserve overrides when rerunning rules on the same pin.

    Classification/access keys cannot be overridden by anyone through this API.
    Changing source pins requires fresh state, preventing cross-version overrides.
    """
    fields = {"rule_version", "source_sha256", "source_version", "classification", "tags"}
    _require(isinstance(proposal, dict) and set(proposal) == fields, "invalid tag proposal")
    _require(proposal["classification"] == "SYNTHETIC_UNCLASS", "classification update forbidden")
    _require(proposal["rule_version"] == TAG_RULE_VERSION, "unsupported tag rule version")
    _hash(proposal["source_sha256"])
    _require(proposal["source_version"] == "sha256:" + proposal["source_sha256"], "tag pin mismatch")
    _require(isinstance(proposal["tags"], dict) and set(proposal["tags"]) == TAG_KEYS,
             "only descriptive tag keys allowed")
    overrides = {}
    if current is not None:
        _require(current["classification"] == proposal["classification"], "classification update forbidden")
        _require(all(current[key] == proposal[key] for key in ("source_version", "source_sha256")),
                 "tag source mismatch")
        overrides = copy.deepcopy(current["manual_overrides"])
    if manual_overrides is not None:
        _require(isinstance(manual_overrides, dict), "manual_overrides must be an object")
        overrides.update(manual_overrides)
    _require(set(overrides) <= TAG_KEYS, "classification/access updates forbidden")
    _require(all(isinstance(value, str) and bool(value.strip())
                 for value in [*proposal["tags"].values(), *overrides.values()]), "tag text required")
    result = copy.deepcopy(proposal)
    result["manual_overrides"] = overrides
    result["tags"].update(overrides)
    return result


def technical_completion_rate(predeclared_run_ids, outcomes):
    """Succeeded/(succeeded+failed) over a predeclared cohort; not operational probability.

    Outcomes use lowercase succeeded/failed/canceled/unknown. Missing/other states
    count as unknown and are excluded, as are canceled runs. No eligible samples
    yields no estimate or interval. Caller must freeze the cohort before execution.
    """
    declared = list(predeclared_run_ids)
    _require(all(isinstance(run_id, str) and bool(run_id.strip()) for run_id in declared),
             "predeclared run IDs required")
    _require(len(set(declared)) == len(declared), "duplicate predeclared run IDs")
    _require(isinstance(outcomes, dict) and set(outcomes) <= set(declared), "outcome outside declared cohort")
    counts = {"succeeded": 0, "failed": 0, "canceled": 0, "unknown": 0}
    for run_id in declared:
        outcome = outcomes.get(run_id, "unknown")
        _require(isinstance(outcome, str), "outcome must be text")
        counts[outcome if outcome in counts else "unknown"] += 1
    sample_size = counts["succeeded"] + counts["failed"]
    estimate = counts["succeeded"] / sample_size if sample_size else None
    interval = None
    if sample_size:
        z_score = 1.959963984540054
        scale = 1 + z_score ** 2 / sample_size
        center = (estimate + z_score ** 2 / (2 * sample_size)) / scale
        half_width = z_score * math.sqrt(estimate * (1 - estimate) / sample_size
                                       + z_score ** 2 / (4 * sample_size ** 2)) / scale
        interval = (max(0.0, center - half_width), min(1.0, center + half_width))
    return {"metric": "technical_completion_rate", "estimate": estimate,
            "sample_size": sample_size, "declared_size": len(declared), "counts": counts,
            "wilson95": interval, "operational_probability": False}