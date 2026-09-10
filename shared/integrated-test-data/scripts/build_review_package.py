from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re


DATA_ROOT = Path(__file__).resolve().parents[1]
REPLAY_ROOT = DATA_ROOT / "projections/realtime"
EVENTS = REPLAY_ROOT / "recorded_observed_events.jsonl"
RULES = REPLAY_ROOT / "finding_rules.json"
UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
SUPPORTED_TYPES = {
    "sensor.observation", "command.integration", "system.status",
    "test.marker", "preservation.marker",
}


def parse_utc(value):
    if not isinstance(value, str) or not UTC_PATTERN.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def utc_text(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def envelope_issue(event):
    for field in ("event_id", "event_type", "site_id", "source_system", "source_instance_id"):
        if not event.get(field):
            return f"MISSING_{field.upper()}"
    if parse_utc(event.get("event_time_utc")) is None:
        return "INVALID_EVENT_TIME"
    if event["event_type"] not in SUPPORTED_TYPES:
        return "UNSUPPORTED_EVENT_TYPE"
    return ""


def build_package(events_path=EVENTS, rules_path=RULES):
    raw_bytes = events_path.read_bytes()
    rule_bytes = rules_path.read_bytes()
    rules = json.loads(rule_bytes)
    records = [
        (line_number, json.loads(line))
        for line_number, line in enumerate(raw_bytes.decode("utf-8").splitlines(), 1)
        if line.strip()
    ]
    if not records or any(not isinstance(event, dict) for _, event in records):
        raise ValueError("The review source must contain JSON object records")
    if any(event.get("classification") != "SYNTHETIC_UNCLASS" or event.get("synthetic") is not True for _, event in records):
        raise ValueError("Only explicitly synthetic, unclassified records are supported")
    scopes = {(event.get("scenario_id"), event.get("simulation_run_id"), event.get("test_event_id")) for _, event in records}
    if len(scopes) != 1 or any(not value for value in next(iter(scopes))):
        raise ValueError("One explicit scenario, run, and test is required per review package")
    scenario, run, test = next(iter(scopes))
    accepted = defaultdict(list)
    rejected = []
    for line_number, event in records:
        issue = envelope_issue(event)
        reference = {"event_id": event.get("event_id"), "source_line": line_number}
        if issue:
            rejected.append({**reference, "reason": issue})
        else:
            accepted[event["event_id"]].append((line_number, event))
    if not accepted:
        raise ValueError("No admitted events are available for an analytical review")
    canonical = [
        min(group, key=lambda item: (parse_utc(item[1].get("ingest_time_utc")) or datetime.max.replace(tzinfo=timezone.utc), item[0]))
        for group in accepted.values()
    ]
    canonical.sort(key=lambda item: (parse_utc(item[1]["event_time_utc"]), item[0]))
    cutoff = max(parse_utc(event["event_time_utc"]) for _, event in canonical)
    follow_ons = []
    for rule in rules["expected_follow_on_events"]:
        for line_number, trigger in canonical:
            if trigger["event_type"] != rule["trigger_event_type"] or trigger.get("action") != rule["trigger_action"]:
                continue
            trigger_time = parse_utc(trigger["event_time_utc"])
            deadline = trigger_time + timedelta(seconds=rule["due_in_seconds"])
            matches = [
                event["event_id"] for _, event in canonical
                if event["event_type"] == rule["expected_event_type"]
                and event.get("action") == rule["expected_action"]
                and event.get("correlation_id") == trigger.get("correlation_id")
                and event.get("target_instance_id") == trigger.get("target_instance_id")
                and trigger_time <= parse_utc(event["event_time_utc"]) <= deadline
            ]
            follow_ons.append({
                "rule_key": rule["rule_key"], "trigger_event_id": trigger["event_id"],
                "source_line": line_number, "due_utc": utc_text(deadline),
                "observed_event_ids": matches,
                "observation": "OBSERVED" if matches else "UNDETERMINED" if cutoff < deadline else "NOT_OBSERVED_IN_RECORDED_WINDOW",
            })
    digest = hashlib.sha256(raw_bytes).hexdigest()
    package = {
        "schema_version": "1.0.0",
        "classification": "SYNTHETIC_UNCLASS",
        "scope": {"scenario_id": scenario, "simulation_run_id": run, "test_event_id": test, "mode": "RECORDED_REPLAY"},
        "source": {"file": events_path.name, "sha256": digest, "byte_count": len(raw_bytes)},
        "rules": {"file": rules_path.name, "sha256": hashlib.sha256(rule_bytes).hexdigest(), "ruleset_id": rules["ruleset_id"], "version": rules["ruleset_version"], "notice": rules["demo_notice"]},
        "counts": {
            "raw_records": len(records),
            "admitted_records_including_duplicates": sum(len(group) for group in accepted.values()),
            "canonical_events": len(canonical),
            "duplicate_records": sum(len(group) - 1 for group in accepted.values()),
            "rejected_records": len(rejected),
        },
        "clock": {
            "first_event_utc": canonical[0][1]["event_time_utc"],
            "last_recorded_event_utc": utc_text(cutoff),
            "event_time_basis": "Synthetic event clock, not a live authoritative clock",
            "ingest_time_basis": "Recorded synthetic source receipt; not Eventhouse receipt",
            "receiver_receipt": "NOT_CAPTURED_IN_LOCAL_FIXTURE",
            "capture_cutoff": "NOT_INDEPENDENTLY_VERIFIED",
        },
        "duplicates": [{"event_id": event_id, "source_lines": [line for line, _ in group]} for event_id, group in sorted(accepted.items()) if len(group) > 1],
        "rejected": rejected,
        "canonical_evidence": [{"event_id": event["event_id"], "source_line": line, "source_instance_id": event["source_instance_id"], "event_time_utc": event["event_time_utc"]} for line, event in canonical],
        "follow_on_observations": follow_ons,
        "review": {"status": "PENDING_HUMAN_REVIEW", "reviewer": None, "approved_at_utc": None, "evidence_status": "LOCAL_FILE_INTEGRITY_VERIFIED_ONLY"},
        "limitations": [
            "A checksum verifies these local bytes, not upstream capture completeness or authenticity.",
            "The embedded preservation marker is a source claim; its placeholder digest is not used as proof.",
            "No verified mapping joins this fixture to the administrative lead event or its objectives.",
            "No recovery, finding closure, participant failure, or execution authorization is established.",
            "Envelope admission is not full payload-schema or engineering validation.",
        ],
    }
    package_digest = hashlib.sha256(json.dumps(package, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    package["package_id"] = f"recorded-review-{package_digest}"
    return package


def render_quick_look(package):
    scope = package["scope"]
    counts = package["counts"]
    source = package["source"]
    lines = [
        "# Recorded Evidence Quick-Look", "",
        f"Status: **{package['review']['status']}**. Synthetic analytical review only.", "",
        f"Test: `{scope['test_event_id']}`. Run: `{scope['simulation_run_id']}`.",
        f"Mode: `{scope['mode']}`. Last recorded event: `{package['clock']['last_recorded_event_utc']}`.", "",
        "| Reconciliation | Count |", "| --- | ---: |",
        *[f"| {label.replace('_', ' ')} | {value} |" for label, value in counts.items()], "",
        f"Raw source: [{source['file']}]({source['file']}). SHA-256: `{source['sha256']}`.",
        f"Rules: [{package['rules']['file']}]({package['rules']['file']}), version `{package['rules']['version']}`.", "",
        "## Review Observations", "",
    ]
    for duplicate in package["duplicates"]:
        lines.append(f"- Duplicate `{duplicate['event_id']}`: source lines {', '.join(map(str, duplicate['source_lines']))}. Original records retained.")
    for rejected in package["rejected"]:
        lines.append(f"- Rejected envelope: [{rejected['event_id']}]({source['file']}#L{rejected['source_line']}), `{rejected['reason']}`.")
    for observation in package["follow_on_observations"]:
        lines.append(f"- Follow-on `{observation['rule_key']}`: **{observation['observation']}**. Due `{observation['due_utc']}`; [trigger evidence]({source['file']}#L{observation['source_line']}).")
    lines.extend(["", "## Limits and Handoff", "", *[f"- {limit}" for limit in package["limitations"]], "", "Reviewer and approval time remain unset. A human reviewer must examine the cited raw evidence and record any disposition separately.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Build or check the deterministic recorded evidence package")
    parser.add_argument("command", choices=("write", "check"))
    args = parser.parse_args()
    package = build_package()
    outputs = {
        REPLAY_ROOT / "review_package.json": json.dumps(package, indent=2) + "\n",
        REPLAY_ROOT / "QUICK_LOOK.md": render_quick_look(package),
    }
    for path, content in outputs.items():
        if args.command == "write":
            path.write_text(content, encoding="utf-8")
        elif not path.exists() or path.read_text(encoding="utf-8") != content:
            raise SystemExit(f"Stale or missing review artifact: {path.name}; run build_review_package.py write")
    print(f"Review package {args.command}: OK; {package['counts']}; approval remains pending")


if __name__ == "__main__":
    main()