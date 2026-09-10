# /// script
# dependencies = ["pyodbc>=5,<6"]
# ///
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import subprocess
import sys

import pyodbc

from finding_closure import build_finding
from publish_review_source import build_record


def main():
    parser = argparse.ArgumentParser(description="Read-only verification of administrative finding, exact source package, and Eventhouse replay.")
    parser.add_argument("run_id")
    args = parser.parse_args()
    record = build_record()
    finding = build_finding(record)
    token = subprocess.check_output(
        ["az", "account", "get-access-token", "--resource", "https://database.windows.net/", "--query", "accessToken", "-o", "tsv"], text=True
    ).strip().encode("utf-16-le")
    connection_string = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=vn5apkookwwe3a2drhjqv2vhqy-tb3deeanfnxujgy3x2v6dcsl3i.datawarehouse.fabric.microsoft.com;DATABASE=mdaoperations;Encrypt=yes;"
    with pyodbc.connect(connection_string, attrs_before={1256: struct.pack("<I", len(token)) + token}, timeout=30) as connection:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT finding.test_event_id,finding.finding_status,evidence.evidence_reference
            FROM mda_ops.finding finding JOIN mda_ops.finding_evidence evidence
            ON finding.finding_id=evidence.finding_id
            WHERE finding.finding_id=? AND evidence.finding_evidence_id='evidence-streaming-envelope-quarantine-001'
        """, finding["finding_id"])
        rows = cursor.fetchall()
    expected_reference = record["SourcePath"] + "#package=" + record["PackageId"] + ";source_line=" + str(finding["source_line"]) + ";event_id=" + finding["event_id"]
    if len(rows) != 1 or rows[0][0] != finding["test_event_id"] or rows[0][2] != expected_reference:
        raise RuntimeError("Mirrored finding/evidence identity mismatch; check replication and SQL metadata sync")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("verify_replay_lineage.py")), args.run_id],
        check=True, capture_output=True, text=True,
    )
    lineage = json.loads(result.stdout)
    if lineage["PackageId"] != record["PackageId"]:
        raise RuntimeError("Replay lineage uses a different evidence package")
    print(json.dumps({
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "finding_id": finding["finding_id"], "test_event_id": rows[0][0],
        "mirrored_status": rows[0][1], "evidence_reference": rows[0][2],
        "replay_lineage": lineage,
        "scope": "Synthetic quarantine disposition only; not Kadena closure or execution authorization",
    }, indent=2))


if __name__ == "__main__":
    main()