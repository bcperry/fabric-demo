import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import urllib.request

from publish_review_source import build_record


CLOCK_FIELDS = ("event_time_utc", "ingest_time_utc", "preserved_window_start_utc", "preserved_window_end_utc")


def original_payload(event):
    restored = dict(event)
    if restored.pop("transport_mode", None) != "recorded_replay":
        raise ValueError("Run is not explicitly a recorded replay")
    restored["simulation_run_id"] = restored.pop("recorded_simulation_run_id")
    restored.pop("replay_speed")
    restored.pop("published_time_utc")
    for field in CLOCK_FIELDS:
        recorded_field = "recorded_" + field
        if recorded_field in restored:
            restored[field] = restored.pop(recorded_field)
    return restored


def comparable_payload(event):
    normalized = dict(event)
    for field in CLOCK_FIELDS:
        value = normalized.get(field)
        if isinstance(value, str):
            try:
                timestamp = re.sub(r"\.0+(?=Z$)", "", value)
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    normalized[field] = parsed.astimezone(timezone.utc).isoformat()
            except ValueError:
                pass
    return json.dumps(normalized, sort_keys=True)


def verify_payloads(package, events):
    expected = Counter(comparable_payload(row["record"]) for row in package["RawRecords"])
    actual = Counter(comparable_payload(original_payload(event)) for event in events)
    if actual != expected:
        raise ValueError("Recovered payloads do not exactly match the original recorded fixture")


def main():
    parser = argparse.ArgumentParser(description="Verify exact source payload lineage without joining unrelated administrative events.")
    parser.add_argument("run_id")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    package = build_record()
    root = Path(__file__).resolve().parents[2]
    source = json.loads((root / "fabric-demos/04-real-time-ingestion/fabric-items/MDA Live Test Control.KQLDashboard/RealTimeDashboard.json").read_text())["dataSources"][0]
    token = subprocess.check_output(["az", "account", "get-access-token", "--resource", "https://kusto.kusto.windows.net", "--query", "accessToken", "-o", "tsv"], text=True).strip()

    def execute(query, management=False):
        request = urllib.request.Request(
            source["clusterUri"] + ("/v1/rest/mgmt" if management else "/v2/rest/query"),
            data=json.dumps({"db": source["database"], "csl": query}).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
        if management:
            return result
        if any(frame.get("HasErrors") for frame in result):
            raise RuntimeError("Lineage query failed")
        return next(frame["Rows"] for frame in result if frame.get("TableKind") == "PrimaryResult")

    run_literal = json.dumps(args.run_id)
    rows = execute("RawIntegratedTestEvents | where tostring(event.simulation_run_id) == " + run_literal + " | project event")
    events = [json.loads(row[0]) if isinstance(row[0], str) else row[0] for row in rows]
    verify_payloads(package, events)
    counts = execute("CanonicalIntegratedTestEvents(datetime(2000-01-01), datetime(2100-01-01)) | where Run == " + run_literal + " | count")
    if counts[0][0] != package["Package"]["counts"]["canonical_events"]:
        raise ValueError("Canonical count differs from the source package")
    entry = {
        "PackageId": package["PackageId"], "RunId": args.run_id,
        "Relationship": "REPLAY_DERIVED_FROM_RECORDED_PACKAGE",
        "VerifiedAt": datetime.now(timezone.utc).isoformat(),
        "RawRecords": len(events), "CanonicalEvents": counts[0][0],
        "Verification": "Payload multiset matches after reversing replay metadata and comparing clock instants; not byte-identical transport",
        "AdministrativeClosureEstablished": False,
    }
    if args.record:
        execute(".create-merge table EvidenceReplayLineage (PackageId:string, RunId:string, Relationship:string, VerifiedAt:datetime, RawRecords:long, CanonicalEvents:long, Verification:string, AdministrativeClosureEstablished:bool)", True)
        execute(".ingest inline into table EvidenceReplayLineage with (format='multijson') <|\n" + json.dumps(entry), True)
        if not execute("EvidenceReplayLineage | where RunId == " + run_literal + " | take 1"):
            raise RuntimeError("Lineage write could not be verified")
    print(json.dumps(entry))


if __name__ == "__main__":
    main()