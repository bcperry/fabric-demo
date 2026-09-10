import argparse
from datetime import datetime, timezone
import json
import struct
import subprocess
import urllib.request

import pyodbc


DATABASE = "210c14b4-028c-4db9-91f2-e617cd21a2dc"
CLUSTER = "https://trd-a9m8t1hz02fkh7c6k4.z9.kusto.fabric.microsoft.com"
SOURCES = {
    "OntologySensorObservation": {
        "query": "SELECT event_id AS observation_id, track_id, system_instance_id, observation_type, event_time_utc AS observation_time_utc, quality_score FROM dbo.fact_sensor_observation",
        "schema": "observation_id:string, track_id:string, system_instance_id:string, observation_type:string, observation_time_utc:datetime, quality_score:real",
        "key": "observation_id",
        "clock": "observation_time_utc",
    },
    "OntologyCommandEvent": {
        "query": "SELECT event_id AS command_event_id, track_id, system_instance_id, action AS action_name, status AS action_status, event_time_utc, CAST(processing_delay_milliseconds AS bigint) AS processing_delay_ms FROM dbo.fact_command_event",
        "schema": "command_event_id:string, track_id:string, system_instance_id:string, action_name:string, action_status:string, event_time_utc:datetime, processing_delay_ms:long",
        "key": "command_event_id",
        "clock": "event_time_utc",
    },
}


def token(resource):
    return subprocess.check_output(
        ["az", "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"], text=True
    ).strip()


def normalize_record(record, clock):
    result = dict(record)
    value = result[clock]
    instant = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    result[clock] = instant.astimezone(timezone.utc).isoformat(timespec="microseconds")
    return result


def main():
    parser = argparse.ArgumentParser(description="Copy recorded lakehouse facts to isolated ontology history tables; never replay or shift their clocks.")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    access = token("https://database.windows.net/").encode("utf-16-le")
    connection = pyodbc.connect(
        "Driver={ODBC Driver 18 for SQL Server};Server=vn5apkookwwe3a2drhjqv2vhqy-tb3deeanfnxujgy3x2v6dcsl3i.datawarehouse.fabric.microsoft.com;Database=IntegratedTestLakehouse;Encrypt=yes;",
        attrs_before={1256: struct.pack("<I", len(access)) + access},
    )
    records = {}
    try:
        for table, source in SOURCES.items():
            cursor = connection.execute(source["query"])
            columns = [column[0] for column in cursor.description]
            rows = [normalize_record(dict(zip(columns, row)), source["clock"]) for row in cursor.fetchall()]
            keys = [row[source["key"]] for row in rows]
            if not rows or not all(keys) or len(set(keys)) != len(keys):
                raise ValueError(f"{table}: empty or nonunique lakehouse identities")
            records[table] = rows
    finally:
        connection.close()
    if not args.publish:
        print(json.dumps({table: {"rows": len(rows), "first": rows[0]} for table, rows in records.items()}))
        return
    access = token("https://kusto.kusto.windows.net")

    def request(query, management=False):
        endpoint = "/v1/rest/mgmt" if management else "/v2/rest/query"
        message = urllib.request.Request(CLUSTER + endpoint, data=json.dumps({"db": DATABASE, "csl": query}).encode(), headers={"Authorization": "Bearer " + access, "Content-Type": "application/json"})
        with urllib.request.urlopen(message, timeout=120) as response:
            frames = json.load(response)
        if isinstance(frames, list):
            if any(frame.get("HasErrors") for frame in frames):
                raise RuntimeError("Ontology history query failed")
            table = next(frame for frame in frames if frame.get("TableKind") == "PrimaryResult")
            columns = [column["ColumnName"] for column in table["Columns"]]
            return [dict(zip(columns, row)) for row in table["Rows"]]
        return frames

    for table, source in SOURCES.items():
        request(f".create-merge table {table} ({source['schema']})", management=True)
        expected = {row[source["key"]]: row for row in records[table]}
        query = f"{table} | where {source['key']} in ({', '.join(json.dumps(key) for key in expected)})"
        existing = [normalize_record(row, source["clock"]) for row in request(query)]
        if any(row != expected[row[source["key"]]] for row in existing):
            raise ValueError(f"{table}: existing history differs from lakehouse; refusing overwrite")
        existing_keys = {row[source["key"]] for row in existing}
        if len(existing_keys) != len(existing):
            raise ValueError(f"{table}: duplicate existing identities")
        missing = [row for key, row in expected.items() if key not in existing_keys]
        if missing:
            request(f".ingest inline into table {table} with (format='multijson') <|\n" + "\n".join(json.dumps(row) for row in missing), management=True)
        actual = [normalize_record(row, source["clock"]) for row in request(query)]
        if len(actual) != len(expected) or any(row != expected[row[source["key"]]] for row in actual):
            raise RuntimeError(f"{table}: history publication verification failed")
        print(f"{table}: verified {len(actual)} exact lakehouse records; inserted {len(missing)}")


if __name__ == "__main__":
    main()