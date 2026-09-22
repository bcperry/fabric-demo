"""Additive Fabric-native, read-only Live Test discovery.

All deployment and retained-evidence metadata is an explicit 2026-09-18 snapshot,
not a live Azure, catalog, approval, or OneLake query. Live observations use only
LiveTargetEvents(), scoped to the last seven days of Eventhouse receipt time.
Native table filtering provides asset/run discovery without dashboard parameters.
The notebook URL opens the existing launcher; selected-asset/run handoff is NOT
IMPLEMENTED. Opening it does not launch a job; interactive sign-in is unverified.
Return to this dashboard manually after using the notebook. No review, ownership,
authorization enforcement, or input issuance is implemented by this dashboard.

Run with action 'validate' (the default) for offline definition checks, or
'publish' to create/update only Live Test - Catalog and Run History in Live Test.
A 202 response is pending, not completed publication or browser verification.
"""

import argparse
import copy
import json
import uuid

import publish_live_test


NAME = "Live Test - Catalog and Run History"
SNAPSHOT_DATE = "2026-09-18"
VERSION = "live-test-v2"
IMAGE_DIGEST = "sha256:eaf4c24c901b7546520f329b3e9e482508956066d573b59564cfc26090cfc1ba"
VERIFIED_RUN = "408335e6-e1bc-41c6-ae08-e106e1c3aab0"
EXECUTION = "job-mda-live-test-b6ut3my"
BUNDLE_SHA256 = "aa8f4433f0dd65a0a8471954910928a963c515fb78027a1a171d7056b21611f7"
LAKEHOUSE = "20efb687-f88b-4c10-8aac-a97974b5bdfe"
BUNDLE_URI = (
    f"https://onelake.dfs.fabric.microsoft.com/{publish_live_test.WORKSPACE}/"
    f"{LAKEHOUSE}/Files/live-test-evidence/{VERIFIED_RUN}/{BUNDLE_SHA256}/bundle.json"
)
NOTEBOOK_URL = (
    f"https://app.fabric.microsoft.com/groups/{publish_live_test.WORKSPACE}/"
    "synapsenotebooks/0025467b-0c80-4b3d-ae03-241016221e19"
)
_TEMPLATE = publish_live_test.dashboard()


def _datatable(columns, rows):
    values = ",\n    ".join(", ".join(json.dumps(value) for value in row) for row in rows)
    return f"datatable({columns})[\n    {values}\n]"


def _queries():
    assets = _datatable(
        "Asset:string, Kind:string, Producer:string, Version:string, ImageDigest:string, "
        "Synthetic:bool, PermittedUse:string, Owner:string, Review:string, "
        "InputProvenance:string, MetadataScope:string, SnapshotDate:string, NotebookURL:string",
        [["target-01", "Deployed synthetic target", "job-mda-live-test", VERSION, IMAGE_DIGEST,
          True, "visualization", "UNASSIGNED", "NOT_REVIEWED",
          "Legacy cloud run: NOT_CATALOG_ISSUED", "Configured deployment; not live query",
          SNAPSHOT_DATE, NOTEBOOK_URL]],
    ) + "\n" + (
        "| join kind=leftouter (\n"
        "    LiveTargetEvents()\n"
        "    | where ReceivedAt > ago(7d) and ReceivedAt <= now()\n"
        "    | summarize arg_max(ReceivedAt, Run) by Vehicle\n"
        "    | project Asset=Vehicle, LastReceivedUTC=ReceivedAt, LatestRun=Run\n"
        ") on Asset\n"
        "| project Asset, Kind, LastReceivedUTC, LatestRun, Producer, Version, ImageDigest, "
        "Synthetic, PermittedUse, Owner, Review, InputProvenance, MetadataScope, "
        "SnapshotDate, NotebookURL"
    )
    history = (
        "LiveTargetEvents()\n"
        "| where ReceivedAt > ago(7d) and ReceivedAt <= now()\n"
        "| summarize FirstEventUTC=min(EventTime), LastEventUTC=max(EventTime), "
        "FirstReceivedUTC=min(ReceivedAt), LastReceivedUTC=max(ReceivedAt), "
        "ReceivedSamples=count(), TSPI=countif(Channel == 'tspi'), "
        "Temperature=countif(Channel == 'temperature'), Errors=countif(Channel == 'error') "
        "by Run, Vehicle\n"
        "| extend ObservationScope='Deduplicated received events; not execution or evidence status', "
        "Owner='UNASSIGNED', Review='NOT_REVIEWED', "
        f"InputProvenance=iff(Run == '{VERIFIED_RUN}', 'NOT_CATALOG_ISSUED', 'UNVERIFIED')\n"
        "| order by LastReceivedUTC desc"
    )
    evidence = _datatable(
        "Run:string, Execution:string, SnapshotDate:string, Provenance:string, "
        "AzureResultSnapshot:string, AzureStartUTC:string, AzureEndUTC:string, Seed:long, "
        "DurationOverrideSeconds:long, TSPISnapshot:long, TemperatureSnapshot:long, "
        "ErrorSnapshot:long, ReceivedSamplesSnapshot:long, LifecycleSnapshot:string, "
        "CollectionSnapshot:string, RetainedFilesSnapshot:long, BundleURI:string, "
        "BundleSHA256:string, InputProvenance:string, Review:string, Owner:string, Limits:string",
        [[VERIFIED_RUN, EXECUTION, SNAPSHOT_DATE, "DEMO_BRIEF.md#retained-run-evidence; retained snapshot, not live query",
          "Succeeded", "2026-09-18T14:05:02Z", "2026-09-18T14:05:42Z", 42, 10,
          200, 20, 10, 230,
          "Console started 14:05:27.879462Z; completed 14:05:37.879867Z; retrieved post-exit",
          "After recovery: no duplicates, missing or unexpected samples; both lifecycle records. "
          "Earlier zero-receipt revision retained separately.",
          5, BUNDLE_URI, BUNDLE_SHA256, "NOT_CATALOG_ISSUED", "NOT_REVIEWED", "UNASSIGNED",
          "Five sanitized files byte-verified on snapshot date; measurement hashes, not full payloads. "
          "Integrity hashes are not signatures or approval. Same-run retry attribution unresolved. "
          "Platform-log export QUERY_FAILED; authenticated run request absent."]],
    )
    access = _datatable(
        "Scope:string, Owner:string, Review:string, PermittedUse:string, InputProvenance:string, "
        "AccessVerification:string, NotebookHandoff:string, SnapshotDate:string",
        [["Discovery only; provenance and ownership missing, not approved", "UNASSIGNED",
          "NOT_REVIEWED", "Synthetic visualization only; not operational readiness",
          "Legacy cloud input NOT_CATALOG_ISSUED; other runs UNVERIFIED",
          "Existing Fabric permissions; non-admin allow/deny and review enforcement UNVERIFIED",
          "Selected-asset/run handoff NOT_IMPLEMENTED; notebook sign-in UNVERIFIED",
          SNAPSHOT_DATE]],
    )
    return assets, access, history, evidence


def dashboard():
    """Return a deterministic definition without I/O or mutation of the template."""
    result = copy.deepcopy(_TEMPLATE)
    table_options = copy.deepcopy(next(
        tile["visualOptions"] for tile in result["tiles"] if tile["visualType"] == "table"
    ))
    result["pages"] = [
        {"name": name, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NAME}/{name}"))}
        for name in ("Catalog", "Run History")
    ]
    result["tiles"] = []
    result["queries"] = []
    result["parameters"] = []
    result["baseQueries"] = []
    items = (
        ("Assets", 0, "Configured deployment: 2026-09-18. Latest receipt: last 7 days UTC; null means no observation."),
        ("Access and Review", 0, "2026-09-18 snapshot. Discovery does not grant access or approval."),
        ("Run History", 1, "Last 7 days by receipt time UTC. Received counts do not establish job success or completeness."),
        ("Retained Evidence", 1, "One verified run; 2026-09-18 snapshot. Not a live storage or execution query."),
    )
    for index, ((title, page_index, description), query) in enumerate(zip(items, _queries())):
        query_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NAME}/query/{title}"))
        result["queries"].append({
            "id": query_id, "text": query, "usedVariables": [],
            "dataSource": {"kind": "inline", "dataSourceId": result["dataSources"][0]["id"]},
        })
        result["tiles"].append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NAME}/tile/{title}")),
            "title": title, "description": description, "visualType": "table",
            "pageId": result["pages"][page_index]["id"],
            "layout": {"x": 0, "y": (index % 2) * 9, "width": 24, "height": 9},
            "queryRef": {"kind": "query", "queryId": query_id},
            "visualOptions": copy.deepcopy(table_options),
        })
    return result


def validate_definition(content):
    """Check local schema bindings; does not claim service-side KQL validation."""
    if content["schema_version"] != 82 or len(content["tiles"]) != 4:
        raise ValueError("Expected schema 82 and four native tables")
    for collection in ("pages", "tiles", "queries", "dataSources"):
        identifiers = [item["id"] for item in content[collection]]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError(f"Duplicate {collection} IDs")
    if [page["name"] for page in content["pages"]] != ["Catalog", "Run History"]:
        raise ValueError("Expected Catalog and Run History pages")
    if content["parameters"] or content["baseQueries"]:
        raise ValueError("Unsupported parameter or base-query binding")
    source = content["dataSources"]
    if len(source) != 1 or source[0]["database"] != publish_live_test.DATABASE:
        raise ValueError("Expected the existing Live Test database")
    page_ids = {page["id"] for page in content["pages"]}
    query_ids = {query["id"] for query in content["queries"]}
    references = []
    for tile in content["tiles"]:
        references.append(tile["queryRef"]["queryId"])
        if tile["pageId"] not in page_ids or tile["visualType"] != "table":
            raise ValueError("Invalid native tile or page reference")
    if set(references) != query_ids or len(references) != len(query_ids):
        raise ValueError("Invalid or reused query references")
    for query in content["queries"]:
        if query["usedVariables"] or query["dataSource"] != {
            "kind": "inline", "dataSourceId": source[0]["id"]
        }:
            raise ValueError("Invalid query variable or data-source binding")
    json.dumps(content, allow_nan=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "publish"), nargs="?", default="validate")
    args = parser.parse_args(argv)
    content = dashboard()
    validate_definition(content)
    if args.action == "validate":
        print(json.dumps({"status": "validated_locally", "tiles": 4, "cloudCalls": 0,
                          "selectedAssetHandoff": "NOT_IMPLEMENTED"}))
        return 0
    response = publish_live_test.publish_item(NAME, "KQLDashboard", {
        "parts": [publish_live_test.part("RealTimeDashboard.json", content)]
    })
    status_code = response["status_code"]
    if not 200 <= status_code < 300:
        raise RuntimeError(f"Unexpected publication status: {status_code}")
    print(json.dumps({
        "status": "pending" if status_code == 202 else "definition_published",
        "status_code": status_code, "browserVerification": "NOT_PERFORMED",
        "selectedAssetHandoff": "NOT_IMPLEMENTED", "response": response,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())