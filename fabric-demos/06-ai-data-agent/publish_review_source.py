import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "shared/integrated-test-data/projections/realtime"


def build_record():
    package = json.loads((SOURCE / "review_package.json").read_text())
    content = {key: value for key, value in package.items() if key != "package_id"}
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if package["package_id"] != "recorded-review-" + digest:
        raise ValueError("Review package identity differs from its content")
    raw_bytes = (SOURCE / package["source"]["file"]).read_bytes()
    rules_bytes = (SOURCE / package["rules"]["file"]).read_bytes()
    for content, expected in (
        (raw_bytes, package["source"]["sha256"]),
        (rules_bytes, package["rules"]["sha256"]),
    ):
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Source digest differs from review package")
    records = [
        {"source_line": line_number, "record": json.loads(line)}
        for line_number, line in enumerate(raw_bytes.decode().splitlines(), 1)
    ]
    if len(records) != package["counts"]["raw_records"]:
        raise ValueError("Source record count differs from review package")
    return {
        "PackageId": package["package_id"],
        "TestEventId": package["scope"]["test_event_id"],
        "SourcePath": "shared/integrated-test-data/projections/realtime/review_package.json",
        "Package": package,
        "RawRecords": records,
        "Rules": json.loads(rules_bytes),
    }


def build_reference_record():
    path = ROOT / "fabric-demos/02-database-mirroring/sql/seed_director_brief.sql"
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    return {
        "DocumentId": "source-reference-" + digest,
        "SourcePath": path.relative_to(ROOT).as_posix(),
        "ContentSha256": digest,
        "Content": content.decode(),
        "Limitations": "Checked-in synthetic SQL seed, not proof of current deployed status. No verified mapping links this administrative event to the streaming fixture, and this document does not establish current finding closure or human adjudication.",
    }


def build_context_record():
    recorded = build_record()
    reference = build_reference_record()
    package = recorded["Package"]
    return {
        **recorded,
        "ReferenceDocumentId": reference["DocumentId"],
        "ReferenceSourcePath": reference["SourcePath"],
        "ReferenceContentSha256": reference["ContentSha256"],
        "ReferenceContent": reference["Content"],
        "ReferenceLimitations": reference["Limitations"],
        "ContextLimitations": "Side-by-side source retrieval only, not a verified event relationship. The recorded streaming fixture is test-streaming-findings-001. The separate checked-in administrative SQL seed describes test-integrated-defense-001 and Kadena. Neither source establishes verified cross-event mapping or current finding closure. A checked-in SQL seed is not proof of current deployed status.",
        "Review": package["review"],
        "Limitations": package["limitations"],
        "RecordedClock": package["clock"],
        "FollowOnObservations": package["follow_on_observations"],
        "SyntheticRuleNotice": package["rules"]["notice"],
        "Counts": package["counts"],
        "Source": package["source"],
    }


def comparable_context(value, field=""):
    if isinstance(value, dict):
        return {name: comparable_context(child, name) for name, child in value.items()}
    if isinstance(value, list):
        return [comparable_context(child, field) for child in value]
    if isinstance(value, str) and field.endswith("_utc"):
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.0+Z", value)
        if match:
            return match[1] + "Z"
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    record = build_record()
    if not args.publish:
        print(f"Validated {record['PackageId']}: {len(record['RawRecords'])} source records")
        return
    dashboard = json.loads((ROOT / "fabric-demos/04-real-time-ingestion/fabric-items/MDA Live Test Control.KQLDashboard/RealTimeDashboard.json").read_text())
    source = dashboard["dataSources"][0]
    token = subprocess.check_output(
        ["az", "account", "get-access-token", "--resource", "https://kusto.kusto.windows.net", "--query", "accessToken", "-o", "tsv"],
        text=True,
    ).strip()

    def request(command, management=True):
        endpoint = "/v1/rest/mgmt" if management else "/v2/rest/query"
        message = urllib.request.Request(
            source["clusterUri"] + endpoint,
            data=json.dumps({"db": source["database"], "csl": command}).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(message, timeout=120) as response:
            result = json.load(response)
        if isinstance(result, list) and any(frame.get("HasErrors") for frame in result):
            raise RuntimeError("Eventhouse query failed")
        return result

    request(".create-merge table EvidenceReviewPackages (PackageId:string, TestEventId:string, SourcePath:string, Package:dynamic, RawRecords:dynamic, Rules:dynamic)")
    query = "EvidenceReviewPackages | where PackageId == " + json.dumps(record["PackageId"]) + " | count"
    frames = request(query, management=False)
    existing = next(frame["Rows"][0][0] for frame in frames if frame.get("TableKind") == "PrimaryResult")
    if not existing:
        request(".ingest inline into table EvidenceReviewPackages with (format='multijson') <|\n" + json.dumps(record))
    frames = request(query, management=False)
    count = next(frame["Rows"][0][0] for frame in frames if frame.get("TableKind") == "PrimaryResult")
    if count < 1:
        raise RuntimeError("Published package is not queryable")
    print(f"Queryable package {record['PackageId']}; stored rows={count}")
    reference = build_reference_record()
    request(".create-merge table EvidenceReferenceDocuments (DocumentId:string, SourcePath:string, ContentSha256:string, Content:string, Limitations:string)")
    query = "EvidenceReferenceDocuments | where DocumentId == " + json.dumps(reference["DocumentId"])
    frames = request(query, management=False)
    rows = next(frame["Rows"] for frame in frames if frame.get("TableKind") == "PrimaryResult")
    if not rows:
        request(".ingest inline into table EvidenceReferenceDocuments with (format='multijson') <|\n" + json.dumps(reference))
    frames = request(query, management=False)
    table = next(frame for frame in frames if frame.get("TableKind") == "PrimaryResult")
    records = [dict(zip((column["ColumnName"] for column in table["Columns"]), row)) for row in table["Rows"]]
    if not records or any(row != reference for row in records):
        raise RuntimeError("Published source reference differs from checked-in bytes")
    print(f"Verified source reference {reference['DocumentId']}; stored rows={len(records)}")
    context = build_context_record()
    schema = ", ".join(
        f"{name}:{'string' if isinstance(value, str) else 'dynamic'}"
        for name, value in context.items()
    )
    request(f".create-merge table EvidenceReviewContext ({schema})")
    query = "EvidenceReviewContext | where PackageId == " + json.dumps(context["PackageId"])
    frames = request(query, management=False)
    rows = next(frame["Rows"] for frame in frames if frame.get("TableKind") == "PrimaryResult")
    if not rows:
        request(".ingest inline into table EvidenceReviewContext with (format='multijson') <|\n" + json.dumps(context))
    frames = request(query, management=False)
    table = next(frame for frame in frames if frame.get("TableKind") == "PrimaryResult")
    contexts = [dict(zip((column["ColumnName"] for column in table["Columns"]), row)) for row in table["Rows"]]
    if not contexts or any(comparable_context(row) != comparable_context(context) for row in contexts):
        raise RuntimeError("Published review context differs from its independently identified source records")
    print(f"Verified comparison context for {context['PackageId']}; stored rows={len(contexts)}")


if __name__ == "__main__":
    main()