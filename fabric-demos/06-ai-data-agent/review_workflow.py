import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import urllib.request
import uuid

from publish_review_source import build_record


def validate_decision(action, rationale, human_review):
    if action not in {"REQUEST_REVIEW", "ACCEPT_EVIDENCE", "REQUEST_CHANGES"}:
        raise ValueError("Unsupported review action")
    if not rationale.strip():
        raise ValueError("A review rationale is required")
    if action != "REQUEST_REVIEW" and not human_review:
        raise ValueError("A human must review the cited source bytes before recording a decision")


def main():
    parser = argparse.ArgumentParser(description="Persist evidence review decisions, not execution authorization or finding closure.")
    parser.add_argument("action", choices=["REQUEST_REVIEW", "ACCEPT_EVIDENCE", "REQUEST_CHANGES"])
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--human-reviewed-source-bytes", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    validate_decision(args.action, args.rationale, args.human_reviewed_source_bytes)
    package = build_record()
    if not args.execute:
        print(f"Validated {args.action} for {package['PackageId']}; no record written")
        return
    account = json.loads(subprocess.check_output(["az", "account", "show", "-o", "json"], text=True))
    if args.action != "REQUEST_REVIEW" and account["user"]["type"] != "user":
        raise ValueError("Evidence acceptance requires an interactive user identity")
    token = subprocess.check_output(
        ["az", "account", "get-access-token", "--resource", "https://kusto.kusto.windows.net", "--query", "accessToken", "-o", "tsv"], text=True
    ).strip()
    root = Path(__file__).resolve().parents[2]
    source = json.loads((root / "fabric-demos/04-real-time-ingestion/fabric-items/MDA Live Test Control.KQLDashboard/RealTimeDashboard.json").read_text())["dataSources"][0]

    def execute(query, management=True):
        request = urllib.request.Request(
            source["clusterUri"] + ("/v1/rest/mgmt" if management else "/v2/rest/query"),
            data=json.dumps({"db": source["database"], "csl": query}).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
        if isinstance(result, list) and any(frame.get("HasErrors") for frame in result):
            raise RuntimeError("Review query failed")
        return result

    execute(".create-merge table EvidenceReviewJournal (ReviewId:string, PackageId:string, Decision:string, Actor:string, TenantId:string, RecordedAt:datetime, Rationale:string, HumanReviewedSourceBytes:bool, ExecutionAuthorization:bool)")
    review_id = str(uuid.uuid4())
    entry = {
        "ReviewId": review_id,
        "PackageId": package["PackageId"],
        "Decision": args.action,
        "Actor": account["user"]["name"],
        "TenantId": account["tenantId"],
        "RecordedAt": datetime.now(timezone.utc).isoformat(),
        "Rationale": args.rationale,
        "HumanReviewedSourceBytes": args.human_reviewed_source_bytes,
        "ExecutionAuthorization": False,
    }
    execute(".ingest inline into table EvidenceReviewJournal with (format='multijson') <|\n" + json.dumps(entry))
    result = execute("EvidenceReviewJournal | where ReviewId == " + json.dumps(review_id) + " | project ReviewId, PackageId, Decision, ExecutionAuthorization", management=False)
    rows = next(frame["Rows"] for frame in result if frame.get("TableKind") == "PrimaryResult")
    if len(rows) != 1:
        raise RuntimeError("Review write could not be verified")
    print(json.dumps({"verified_review": rows[0]}))


if __name__ == "__main__":
    main()