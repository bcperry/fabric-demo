"""Read-only Azure acquisition; not validation of the strict P1 fixture contract."""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import requests

import collect_live_test as collector


def validate_ids(run_id, execution_id, job_resource_id, log_workspace_id):
    for value in (run_id, log_workspace_id):
        if str(UUID(value)) != value:
            raise ValueError("Expected canonical UUIDs for run and workspace customer ID")
    name = r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
    resource = rf"/subscriptions/([0-9a-f-]{{36}})/resourceGroups/{name}/providers/Microsoft\.App/jobs/{name}"
    match = re.fullmatch(resource, job_resource_id, re.IGNORECASE)
    if not re.fullmatch(name, execution_id) or not match:
        raise ValueError("Expected bounded execution name and ARM Microsoft.App/jobs resource ID")
    UUID(match[1])


def table_rows(payload):
    try:
        if isinstance(payload, dict):
            if payload.get("error"):
                raise ValueError
            tables = payload["tables"]
        else:
            if not isinstance(payload, list) or any(frame.get("HasErrors") for frame in payload):
                raise ValueError
            tables = [frame for frame in payload if frame.get("TableKind") == "PrimaryResult"]
        if not tables:
            raise ValueError
        result = []
        for table in tables:
            columns = [column.get("name", column.get("ColumnName"))
                       for column in table.get("columns", table.get("Columns", []))]
            if not columns or any(not isinstance(column, str) for column in columns) or len(set(columns)) != len(columns):
                raise ValueError
            rows = table.get("rows", table.get("Rows"))
            if not isinstance(rows, list):
                raise ValueError
            for row in rows:
                if not isinstance(row, list) or len(row) != len(columns):
                    raise ValueError
                result.append(dict(zip(columns, row)))
        return result
    except (KeyError, TypeError, AttributeError, ValueError):
        raise ValueError("Azure query failed, returned partial results, or had an invalid table response") from None


def az_json(*arguments):
    try:
        result = subprocess.run(["az", *arguments, "--only-show-errors", "-o", "json"],
                                capture_output=True, text=True, timeout=90, check=True)
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ValueError("Azure CLI read failed; check az login, subscription, resource and read permissions") from None


def access_token(resource):
    return az_json("account", "get-access-token", "--resource", resource, "--query", "accessToken")


def query(url, body, audience, http, token_getter):
    try:
        response = http(url, json=body, headers={"Authorization": f"Bearer {token_getter(audience)}"},
                        timeout=60, allow_redirects=False)
        payload = response.json() if response.status_code == 200 else None
    except requests.RequestException:
        raise ValueError("Azure query transport failure; check connectivity and authentication") from None
    except ValueError:
        raise ValueError("Azure query failed or was partial; check authentication, permissions and table schema") from None
    if response.status_code != 200:
        raise ValueError(f"Azure query HTTP {response.status_code}; check authentication, read permissions, table and endpoint")
    return table_rows(payload)


def log_query(job, execution, environment, run_id, system=False):
    def field(name):
        return f'tostring(coalesce(column_ifexists("{name}", ""), column_ifexists("{name}_s", "")))'
    table = "ContainerAppSystemLogs" if system else "ContainerAppConsoleLogs"
    scope = f"| where _ResourceId in~ ('{job}', '{environment}')"
    scope += f" | where job in ('{job.rsplit('/', 1)[1]}', '{execution}') or execution == '{execution}'"
    scope += f" | where isempty(execution) or execution == '{execution}'"
    base = f"{table} | extend job={field('JobName')}, execution={field('ExecutionName')} " + scope
    if system:
        return base + f" | project time=TimeGenerated, reason={field('Reason')}"
    return base + f" | extend record=parse_json({field('Log')}) | where tostring(record.run_id) == '{run_id}' | project record"


def acquire(run_id, execution_id, job_resource_id, log_workspace_id, kusto_endpoint=None,
            database=None, *, cli=az_json, http=requests.post, token_getter=access_token):
    created_at = datetime.now(timezone.utc).isoformat()
    validate_ids(run_id, execution_id, job_resource_id, log_workspace_id)
    if bool(kusto_endpoint) != bool(database) or (kusto_endpoint and not re.fullmatch(
            r"https://[a-z0-9-]+(?:\.[a-z0-9-]+)*\.kusto\.(?:windows\.net|fabric\.microsoft\.com)", kusto_endpoint)):
        raise ValueError("Supply both an HTTPS Azure/Fabric Kusto endpoint (no path) and database, or neither")
    if database and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,127}", database):
        raise ValueError("Expected bounded Kusto database name")
    arm = "https://management.azure.com"
    execution_resource = f"{job_resource_id}/executions/{execution_id}"
    raw = cli("rest", "--method", "get", "--url", f"{arm}{execution_resource}?api-version=2024-03-01")
    if raw.get("id", "").lower() != execution_resource.lower():
        raise ValueError("ARM returned a different execution resource")
    properties = raw["properties"]
    environment = cli("rest", "--method", "get", "--url", f"{arm}{job_resource_id}?api-version=2024-03-01",
                      "--query", "properties.environmentId")
    if not isinstance(environment, str) or not re.fullmatch(
            r"/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[A-Za-z0-9_-]+/providers/Microsoft\.App/managedEnvironments/[A-Za-z0-9_-]+", environment):
        raise ValueError("Job environment resource ID is missing or invalid")
    logs_url = f"https://api.loganalytics.azure.com/v1/workspaces/{log_workspace_id}/query"
    def logs(system=False):
        return query(logs_url, {"query": log_query(job_resource_id, execution_id, environment, run_id, system)},
                     "https://api.loganalytics.io", http, token_getter)
    diagnostics = []
    for row in logs():
        record = json.loads(row["record"]) if isinstance(row["record"], str) else row["record"]
        clean = collector._diagnostic(record, run_id)
        if clean is not None:
            if record.get("execution_id", execution_id) != execution_id:
                raise ValueError("Diagnostic belongs to a different execution")
            diagnostics.append(clean)
    starts = {json.dumps(record, sort_keys=True) for record in diagnostics if record["kind"] == "started"}
    if len(starts) != 1:
        raise ValueError("Need one distinct started diagnostic; check run/execution IDs, console logging, retention and ingestion delay")
    started = json.loads(starts.pop())
    status = str(properties.get("status", "UNKNOWN")).upper()
    status = status if status in collector.STATUSES else "UNKNOWN"
    execution = {"run_id": run_id, "execution_id": execution_id, "status": status}
    assets = []
    for container in properties.get("template", {}).get("containers", []):
        asset = {"asset_id": collector._identifier(container["name"])}
        digest = re.search(r"@(sha256:[0-9a-f]{64})\Z", container.get("image", ""))
        if digest:
            asset["image_digest"] = digest[1]
        assets.append(asset)
    manifest = {"schema_version": "live-test-acquired-run.v1", "run_id": run_id, "request_id": str(uuid4()),
                "requester": "azure-export", "created_at": created_at, "seed": started["seed"],
                "parameters": {"duration_seconds": started["duration_seconds"],
                               **{f"{channel}_hz": started["rates"][channel] for channel in collector.CHANNELS}},
                "executions": [execution], "assets": assets, "input": {}, "state": status,
                "evidence_state": "NOT_COLLECTED", "telemetry": [], "logs": [], "outputs": []}
    _, expected, _ = collector._context(manifest, execution)
    telemetry = []
    if kusto_endpoint:
        rows = query(kusto_endpoint + "/v2/rest/query", {"db": database,
                     "csl": f"RawTargetVehicleEvents | where tostring(event.run_id) == '{run_id}' | project event"},
                     "https://kusto.kusto.windows.net", http, token_getter)
        for row in rows:
            event = json.loads(row["event"]) if isinstance(row["event"], str) else row["event"]
            clean = collector._event(event, run_id, expected)
            if clean is not None:
                if event.get("execution_id", execution_id) != execution_id:
                    raise ValueError("Telemetry belongs to a different execution")
                telemetry.append({key: value for key, value in clean.items() if not key.startswith("measurement_")})
                if "data" in event:
                    telemetry[-1].update(synthetic=True, data=event["data"])
    platform = []
    platform_status = "UNAVAILABLE"
    try:
        platform = [{"time": collector._timestamp(row["time"]), "reason": collector._safe_label(row["reason"]),
                     "scope": "JOB", "execution_linkage": "NOT_PROVEN"} for row in logs(system=True)]
        platform_status = "RETRIEVED" if platform else "NO_RECORDS"
    except ValueError:
        platform_status = "QUERY_FAILED"
    source = {"schema_version": "azure-live-test-acquisition.v1", "job_resource_id": job_resource_id,
              "execution_id": execution_id, "run_id": run_id, "log_workspace_id": log_workspace_id,
              "created_at": created_at, "request_id_source": "LOCAL_EXPORT_UUID", "contract_validation": "NOT_PERFORMED", "input_status": "UNAVAILABLE",
              "image_source": "EXECUTION_TEMPLATE", "digest_status": "AVAILABLE" if assets and all(
                  "image_digest" in asset for asset in assets) else "UNAVAILABLE_OR_PARTIAL",
              "diagnostic_scope": "RESOURCE_JOB_RUN; SAME_RUN_RETRIES_NOT_DISTINGUISHABLE",
              "telemetry_status": ("RETRIEVED" if telemetry else "NO_RECORDS") if kusto_endpoint else "NOT_REQUESTED",
              "kusto_endpoint": kusto_endpoint, "database": database, "platform_status": platform_status}
    return {"manifest.json": manifest, "execution.json": execution, "diagnostics.json": diagnostics,
            "telemetry.json": telemetry, "platform.json": platform, "acquisition.json": source}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run-id", "execution-id", "job-resource-id", "log-workspace-id", "output-directory"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--kusto-endpoint")
    parser.add_argument("--database")
    args = vars(parser.parse_args(argv))
    directory = Path(args.pop("output_directory"))
    try:
        if directory.exists() or directory.is_symlink():
            raise ValueError("Output directory must be new")
        files = acquire(**args)
        directory.mkdir(mode=0o700)
        for name, records in files.items():
            with os.fdopen(os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
                json.dump(records, stream, indent=2, allow_nan=False)
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        parser.exit(1, "Export failed; verify identifiers, login/read permissions, log tables and started diagnostic, and a new writable output path. No raw Azure response retained.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())