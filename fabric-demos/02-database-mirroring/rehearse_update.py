# /// script
# dependencies = ["psycopg[binary]>=3.2,<4"]
# ///
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import urllib.request

import psycopg


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = "10327698-2b0d-446f-9b1b-beabe18a4bda"
DATASET = "0d51632a-221a-4656-ba62-e2f471ce9172"
ACTION = "action-0001-0004-1"
ORIGINAL_OWNER = "Kadena Range Evidence Lead"
REHEARSAL_OWNER = "Kadena Range Evidence Lead (synthetic rehearsal)"


def token(resource):
    return subprocess.check_output(
        ["az", "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"], text=True
    ).strip()


def connect():
    return psycopg.connect(
        host="pg-mda-demo-4u6mawdzlpyh4.postgres.database.azure.com",
        dbname="mdaoperations",
        user="admin@mngenvmcap005042.onmicrosoft.com",
        password=token("https://ossrdbms-aad.database.windows.net"),
        sslmode="require",
        connect_timeout=15,
    )


def change_owner(expected, replacement):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE mda_ops.corrective_action SET owner_role=%s WHERE corrective_action_id=%s AND owner_role=%s RETURNING corrective_action_id,owner_role",
                (replacement, ACTION, expected),
            )
            rows = cursor.fetchall()
            if len(rows) != 1:
                raise RuntimeError("Action owner changed outside this rehearsal; no overwrite performed")
    print(json.dumps({"utc": datetime.now(timezone.utc).isoformat(), "source": rows}))


def require_running_mirror():
    request = urllib.request.Request(
        f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE}/mirroredDatabases/fdccee22-7557-4d68-a387-aa7fc1d48343/getMirroringStatus",
        data=b"{}",
        headers={"Authorization": "Bearer " + token("https://api.fabric.microsoft.com"), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        status = json.load(response)["status"]
    if status != "Running":
        raise RuntimeError(f"Mirror is {status}; resume replication before changing source data")


def rebuild_and_verify(expected):
    subprocess.run(
        [str(ROOT / "shared/setup-scripts/fabric_demo_cli.sh"), "run-notebook", "03-star-schema-bi.Folder/03_gold_test_products"],
        check=True,
        cwd=ROOT,
    )
    subprocess.run(
        [str(ROOT / "shared/setup-scripts/fabric_demo_cli.sh"), "refresh-demo-03-items"],
        check=True,
        cwd=ROOT,
    )
    query = "EVALUATE SELECTCOLUMNS(FILTER('gold_mirror_casework', 'gold_mirror_casework'[finding_id] = \"finding-0001-0004\"), \"Owner\", 'gold_mirror_casework'[next_action_owner])"
    request = urllib.request.Request(
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE}/datasets/{DATASET}/executeQueries",
        data=json.dumps({"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}}).encode(),
        headers={"Authorization": "Bearer " + token("https://analysis.windows.net/powerbi/api"), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)
    rows = result["results"][0]["tables"][0].get("rows", [])
    if rows != [{"[Owner]": expected}]:
        raise RuntimeError(f"Source-to-model owner mismatch: {rows}")
    print(json.dumps({"utc": datetime.now(timezone.utc).isoformat(), "model_verified_owner": expected}))


def main():
    parser = argparse.ArgumentParser(description="Rehearse and restore one synthetic action owner; does not change status or approval.")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.restore:
        change_owner(REHEARSAL_OWNER, ORIGINAL_OWNER)
        rebuild_and_verify(ORIGINAL_OWNER)
    elif args.execute:
        require_running_mirror()
        change_owner(ORIGINAL_OWNER, REHEARSAL_OWNER)
        try:
            rebuild_and_verify(REHEARSAL_OWNER)
        finally:
            change_owner(REHEARSAL_OWNER, ORIGINAL_OWNER)
            rebuild_and_verify(ORIGINAL_OWNER)
    else:
        print(f"No changes. --execute temporarily changes {ACTION}; --restore recovers an interrupted rehearsal.")


if __name__ == "__main__":
    main()