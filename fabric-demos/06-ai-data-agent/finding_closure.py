import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import uuid

from publish_review_source import build_record


FINDING_ID = "finding-streaming-envelope-quarantine-001"


def build_finding(record):
    package = record["Package"]
    rejected = package["rejected"]
    if len(rejected) != 1 or rejected[0]["reason"] != "MISSING_SITE_ID":
        raise ValueError("This scenario requires exactly one missing-site rejection")
    evidence = rejected[0]
    source = next(item["record"] for item in record["RawRecords"] if item["source_line"] == evidence["source_line"])
    if source["event_id"] != evidence["event_id"] or source.get("site_id"):
        raise ValueError("Rejected source does not match the cited record")
    if source["test_event_id"] != record["TestEventId"]:
        raise ValueError("Evidence belongs to a different test event")
    return {
        "finding_id": FINDING_ID,
        "test_event_id": record["TestEventId"],
        "package_id": record["PackageId"],
        "source_line": evidence["source_line"],
        "event_id": evidence["event_id"],
        "status": "OPEN",
        "disposition": "QUARANTINE_RETAINED",
        "execution_authorization": False,
    }


def validate_transition(finding, package_id, action, rationale, human_review):
    if finding["package_id"] != package_id:
        raise ValueError("Evidence package does not match this finding")
    if not rationale.strip():
        raise ValueError("A rationale is required")
    if not human_review:
        raise ValueError("A reviewer must inspect the cited source before deciding")
    transitions = {
        ("OPEN", "ACCEPT_EVIDENCE"): "EVIDENCE_ACCEPTED",
        ("CHANGES_REQUESTED", "ACCEPT_EVIDENCE"): "EVIDENCE_ACCEPTED",
        ("OPEN", "REQUEST_CHANGES"): "CHANGES_REQUESTED",
        ("EVIDENCE_ACCEPTED", "REQUEST_CHANGES"): "CHANGES_REQUESTED",
        ("EVIDENCE_ACCEPTED", "CLOSE_FINDING"): "CLOSED",
    }
    status = transitions.get((finding["status"], action))
    if status is None:
        raise ValueError("Invalid transition or finding already closed")
    return status


def provision(connection, record):
    from psycopg.types.json import Jsonb

    finding = build_finding(record)
    package = record["Package"]
    scope = package["scope"]
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mda_ops.evidence_disposition (
                finding_id text PRIMARY KEY REFERENCES mda_ops.finding(finding_id),
                package_id text NOT NULL,
                source_line integer NOT NULL CHECK (source_line > 0),
                event_id text NOT NULL,
                source_sha256 text NOT NULL,
                review_state text NOT NULL CHECK (review_state IN ('OPEN','CHANGES_REQUESTED','EVIDENCE_ACCEPTED','CLOSED')),
                package jsonb NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mda_ops.evidence_disposition_audit (
                audit_id uuid PRIMARY KEY,
                finding_id text NOT NULL REFERENCES mda_ops.evidence_disposition(finding_id),
                package_id text NOT NULL,
                action text NOT NULL,
                prior_state text NOT NULL,
                new_state text NOT NULL,
                actor text NOT NULL,
                recorded_at_utc timestamptz NOT NULL DEFAULT clock_timestamp(),
                rationale text NOT NULL,
                execution_authorization boolean NOT NULL DEFAULT false CHECK (NOT execution_authorization)
            )
        """)
        cursor.execute("""
            INSERT INTO mda_ops.test_event
            (test_event_id,scenario_id,test_type,observed_run_manifest_id,predicted_run_manifest_id,event_name,planned_start_time_utc,planned_end_time_utc,classification)
            VALUES (%s,%s,'DATA_QUALITY_REVIEW',%s,'NOT_APPLICABLE','Synthetic recorded-envelope quarantine review',%s,%s,'SYNTHETIC_UNCLASS')
            ON CONFLICT (test_event_id) DO NOTHING
        """, (record["TestEventId"], scope["scenario_id"], scope["simulation_run_id"], package["clock"]["first_event_utc"], package["clock"]["last_recorded_event_utc"]))
        cursor.execute("SELECT scenario_id,observed_run_manifest_id FROM mda_ops.test_event WHERE test_event_id=%s", (record["TestEventId"],))
        if cursor.fetchone() != (scope["scenario_id"], scope["simulation_run_id"]):
            raise ValueError("Existing administrative event has different source identity")
        cursor.execute("""
            INSERT INTO mda_ops.finding
            (finding_id,test_event_id,severity,finding_status,finding_title,finding_summary,identified_at_utc,classification)
            VALUES (%s,%s,'LOW','OPEN','Review rejected envelope disposition',
            'Synthetic data-quality review only. Retain the cited source record in quarantine; disposition does not repair the source or establish test success.',%s,'SYNTHETIC_UNCLASS')
            ON CONFLICT (finding_id) DO NOTHING
        """, (FINDING_ID, record["TestEventId"], datetime.now(timezone.utc)))
        cursor.execute("SELECT test_event_id FROM mda_ops.finding WHERE finding_id=%s", (FINDING_ID,))
        if cursor.fetchone() != (record["TestEventId"],):
            raise ValueError("Existing finding belongs to a different event")
        cursor.execute("""
            INSERT INTO mda_ops.evidence_disposition
            VALUES (%s,%s,%s,%s,%s,'OPEN',%s) ON CONFLICT (finding_id) DO NOTHING
        """, (FINDING_ID, record["PackageId"], finding["source_line"], finding["event_id"], package["source"]["sha256"], Jsonb(package)))
        cursor.execute("SELECT package_id,source_line,event_id,source_sha256 FROM mda_ops.evidence_disposition WHERE finding_id=%s", (FINDING_ID,))
        if cursor.fetchone() != (record["PackageId"], finding["source_line"], finding["event_id"], package["source"]["sha256"]):
            raise ValueError("Existing finding is bound to different evidence")
        reference = record["SourcePath"] + "#package=" + record["PackageId"] + ";source_line=" + str(finding["source_line"]) + ";event_id=" + finding["event_id"]
        cursor.execute("""
            INSERT INTO mda_ops.finding_evidence VALUES
            ('evidence-streaming-envelope-quarantine-001',%s,'HASH_VERIFIED_RECORDED_PACKAGE',%s,'QUARANTINED_RAW_RECORD',%s,'SYNTHETIC_UNCLASS')
            ON CONFLICT (finding_evidence_id) DO NOTHING
        """, (FINDING_ID, reference, datetime.now(timezone.utc)))
        cursor.execute("SELECT finding_id,evidence_reference FROM mda_ops.finding_evidence WHERE finding_evidence_id='evidence-streaming-envelope-quarantine-001'")
        if cursor.fetchone() != (FINDING_ID, reference):
            raise ValueError("Existing evidence attachment differs from this package")
    return finding


def transition(connection, record, action, rationale, human_review):
    finding = build_finding(record)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT disposition.package_id,disposition.review_state,finding.test_event_id,finding.finding_status
            FROM mda_ops.evidence_disposition disposition JOIN mda_ops.finding finding USING (finding_id)
            WHERE finding_id=%s FOR UPDATE OF disposition,finding
        """, (FINDING_ID,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Provision the finding first")
        package_id, prior_state, test_event_id, finding_status = row
        if test_event_id != finding["test_event_id"] or finding_status != ("CLOSED" if prior_state == "CLOSED" else "OPEN"):
            raise ValueError("Administrative finding changed outside this workflow")
        finding.update(package_id=package_id, status=prior_state)
        new_state = validate_transition(finding, record["PackageId"], action, rationale, human_review)
        cursor.execute("UPDATE mda_ops.evidence_disposition SET review_state=%s WHERE finding_id=%s", (new_state, FINDING_ID))
        if new_state == "CLOSED":
            cursor.execute("UPDATE mda_ops.finding SET finding_status='CLOSED' WHERE finding_id=%s", (FINDING_ID,))
        cursor.execute("""
            INSERT INTO mda_ops.evidence_disposition_audit
            (audit_id,finding_id,package_id,action,prior_state,new_state,actor,rationale)
            VALUES (%s,%s,%s,%s,%s,%s,session_user,%s)
        """, (uuid.uuid4(), FINDING_ID, package_id, action, prior_state, new_state, rationale))
    return new_state


def main():
    parser = argparse.ArgumentParser(description="Review synthetic quarantine disposition; never authorizes execution.")
    parser.add_argument("action", choices=["PROVISION", "REHEARSE", "ACCEPT_EVIDENCE", "REQUEST_CHANGES", "CLOSE_FINDING"])
    parser.add_argument("--rationale", default="")
    parser.add_argument("--human-reviewed-source-bytes", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    record = build_record()
    finding = build_finding(record)
    if args.action not in {"PROVISION", "REHEARSE"}:
        if not args.rationale.strip() or not args.human_reviewed_source_bytes:
            raise ValueError("A decision requires a rationale and actual human source review")
    if not args.execute:
        print(json.dumps({"validated_finding": finding, "database_changed": False, "database_state_checked": False}))
        return
    import importlib.util

    spec = importlib.util.spec_from_file_location("mirror_rehearsal", Path(__file__).resolve().parents[1] / "02-database-mirroring/rehearse_update.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    account = json.loads(subprocess.check_output(["az", "account", "show", "-o", "json"], text=True))
    if account["user"]["type"] != "user":
        raise ValueError("This demo workflow requires an interactive user identity")
    with module.connect() as connection:
        if args.action == "PROVISION":
            provision(connection, record)
            result = "Provisioned exact-source finding; no review decision recorded"
        elif args.action == "REHEARSE":
            provision(connection, record)
            transition(connection, record, "REQUEST_CHANGES", "ROLLBACK-ONLY SYNTHETIC TEST", True)
            transition(connection, record, "ACCEPT_EVIDENCE", "ROLLBACK-ONLY SYNTHETIC TEST", True)
            transition(connection, record, "CLOSE_FINDING", "ROLLBACK-ONLY SYNTHETIC TEST", True)
            with connection.cursor() as cursor:
                cursor.execute("SELECT finding_status FROM mda_ops.finding WHERE finding_id=%s", (FINDING_ID,))
                if cursor.fetchone() != ("CLOSED",):
                    raise RuntimeError("Closure did not reach administrative finding")
                cursor.execute("SELECT count(*) FROM mda_ops.evidence_disposition_audit WHERE finding_id=%s AND rationale='ROLLBACK-ONLY SYNTHETIC TEST'", (FINDING_ID,))
                if cursor.fetchone() != (3,):
                    raise RuntimeError("Audit transitions did not match rehearsal")
            connection.rollback()
            result = "Verified three atomic transitions and CLOSED finding; all rehearsal writes rolled back"
        else:
            result = transition(connection, record, args.action, args.rationale, args.human_reviewed_source_bytes)
    print(json.dumps({"finding_id": FINDING_ID, "result": result}))


if __name__ == "__main__":
    main()