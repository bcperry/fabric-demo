import argparse
import base64
import copy
import json
from pathlib import Path
import subprocess
import uuid


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = "10327698-2b0d-446f-9b1b-beabe18a4bda"
FOLDER = "0caa3905-a150-4af9-a722-9b824342d1f1"
STREAM = "f663a572-3ef6-400a-afeb-0c7af0aa3629"
DATABASE = "210c14b4-028c-4db9-91f2-e617cd21a2dc"
CLUSTER = "https://trd-a9m8t1hz02fkh7c6k4.z9.kusto.fabric.microsoft.com"


def api(endpoint, method="get", body=None):
    command = ["fab", "api", endpoint, "-X", method, "--output_format", "json", "--show_headers"]
    if body is not None:
        command.extend(["-i", json.dumps(body)])
    result = json.loads(subprocess.check_output(command, text=True))["result"]["data"][0]
    if result["status_code"] >= 400:
        raise RuntimeError(json.dumps(result["text"]))
    return result


def part(path, value):
    content = value if isinstance(value, str) else json.dumps(value)
    return {"path": path, "payload": base64.b64encode(content.encode()).decode(),
            "payloadType": "InlineBase64"}


def dashboard():
    original = json.loads((ROOT / "fabric-items/MDA Live Test Control.KQLDashboard/RealTimeDashboard.json").read_text())
    result = copy.deepcopy(original)
    page_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "mda-live-test-page"))
    result["pages"] = [{"name": "Live Test", "id": page_id}]
    result["tiles"] = []
    result["queries"] = []
    result["parameters"] = []
    result["baseQueries"] = []
    result["dataSources"][0].update(workspace=WORKSPACE, database=DATABASE,
                                    databaseArtifactId=DATABASE, clusterUri=CLUSTER)
    result["autoRefresh"] = {"enabled": True, "defaultInterval": "10s", "minInterval": "10s"}
    result["changeDetection"] = {"kind": "liveUpdates", "fallbackRefreshRate": "30s", "minRefreshRate": "10s"}
    items = [
        ("Live status", "table", "LiveTargetStatus()", (0, 0, 24, 3)),
        ("Test asset | position and trail", "map",
         "LiveTargetTrail() | extend MarkerSize=1, MarkerLabel=''\n"
         "| union (LiveTargetPosition() | extend MarkerSize=6, MarkerLabel=strcat(Vehicle, ' | ', Mode))\n"
         "| summarize arg_max(MarkerSize, *) by Vehicle, Run, EventTime\n"
         "| order by EventTime asc", (0, 3, 14, 9)),
        ("Recent telemetry | last 2 minutes", "table",
         "LiveTargetEvents() | where EventTime > ago(2m) | top 50 by EventTime desc | project EventTime, Channel, Sequence, Latitude, Longitude, AltitudeM, TemperatureC, ErrorWord", (14, 3, 10, 9)),
        ("Altitude | current flight", "timechart", "LiveTargetTrail() | project EventTime, AltitudeM", (0, 12, 8, 6)),
        ("Internal temperature | last 15 minutes", "timechart",
         "LiveTargetEvents() | where Channel == 'temperature' and EventTime > ago(15m) | project EventTime, TemperatureC, Run | order by EventTime asc", (8, 12, 8, 6)),
        ("Generic error word | last 15 minutes", "timechart",
         "LiveTargetEvents() | where Channel == 'error' and EventTime > ago(15m) | project EventTime, ErrorWord, Run | order by EventTime asc", (16, 12, 8, 6)),
    ]
    for title, visual, query, layout in items:
        query_id = str(uuid.uuid5(uuid.NAMESPACE_URL, title))
        template = next((tile for tile in original["tiles"] if tile["visualType"] == visual), None)
        options = copy.deepcopy(template["visualOptions"]) if template else {}
        if visual == "map":
            options = {"map__latitudeColumn": "Latitude", "map__longitudeColumn": "Longitude",
                       "map__labelColumn": "MarkerLabel", "map__geoType": "numeric",
                       "map__geoPointColumn": None, "map__sizeColumn": None, "map__sizeDisabled": True}
        result["tiles"].append({"id": str(uuid.uuid5(uuid.NAMESPACE_DNS, title)), "title": title,
                                "visualType": visual, "pageId": page_id,
                                "layout": dict(zip(("x", "y", "width", "height"), layout)),
                                "queryRef": {"kind": "query", "queryId": query_id}, "visualOptions": options})
        result["queries"].append({"id": query_id, "text": query, "usedVariables": [],
                                  "dataSource": {"kind": "inline", "dataSourceId": result["dataSources"][0]["id"]}})
    return result


def publish_item(name, item_type, definition):
    items = api(f"workspaces/{WORKSPACE}/items")["text"]["value"]
    existing = next((item for item in items if item["displayName"] == name and item["type"] == item_type), None)
    if existing:
        return api(f"workspaces/{WORKSPACE}/items/{existing['id']}/updateDefinition", "post", {"definition": definition})
    return api(f"workspaces/{WORKSPACE}/items", "post", {
        "displayName": name, "type": item_type, "folderId": FOLDER, "definition": definition,
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("export-stream", "dashboard", "notebook", "validate"))
    args = parser.parse_args()
    if args.action == "export-stream":
        definition = api(f"workspaces/{WORKSPACE}/eventstreams/{STREAM}/getDefinition", "post")["text"]["definition"]
        directory = ROOT / "fabric-items/live_target_telemetry.Eventstream"
        directory.mkdir(exist_ok=True)
        for definition_part in definition["parts"]:
            name = definition_part["path"]
            if name in {"eventstream.json", "eventstreamProperties.json", ".platform"}:
                (directory / name).write_bytes(base64.b64decode(definition_part["payload"]))
        result = {"exported": str(directory)}
    elif args.action == "dashboard":
        result = publish_item("Live Test - Asset Monitor", "KQLDashboard", {"parts": [part("RealTimeDashboard.json", dashboard())]})
    elif args.action == "notebook":
        source = (ROOT / "scripts/start_live_test.py").read_text()
        notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {
            "kernelspec": {"display_name": "Synapse PySpark", "language": "python", "name": "synapse_pyspark"},
            "language_info": {"name": "python"}}, "cells": [{"cell_type": "code", "id": "start-live-test",
            "metadata": {}, "execution_count": None, "outputs": [], "source": source.splitlines(keepends=True)}]}
        result = publish_item("Start Live Test", "Notebook", {"format": "ipynb", "parts": [part("notebook-content.ipynb", notebook)]})
    else:
        content = dashboard()
        assert len(content["tiles"]) == 6
        assert all(query["usedVariables"] == [] for query in content["queries"])
        print("Validated six live dashboard tiles and query bindings")
        return
    print(json.dumps(result))


if __name__ == "__main__":
    main()