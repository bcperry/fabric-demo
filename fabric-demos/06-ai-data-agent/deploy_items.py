import argparse
import base64
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parent
WORKSPACE = "10327698-2b0d-446f-9b1b-beabe18a4bda"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["agent", "ontology"])
    args = parser.parse_args()
    token = subprocess.check_output(
        ["az", "account", "get-access-token", "--resource", "https://api.fabric.microsoft.com", "--query", "accessToken", "-o", "tsv"], text=True
    ).strip()
    base = f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE}"

    def request(path, payload=None):
        message = urllib.request.Request(
            base + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(message, timeout=120) as response:
                body = response.read()
                return response.status, json.loads(body) if body else None, response.headers.get("Location")
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Fabric HTTP {error.code}: {error.read().decode()}") from None

    _, listing, _ = request("/items")
    items = listing["value"]
    if listing.get("continuationToken"):
        raise RuntimeError("Workspace inventory is paginated; resolve all items before provisioning")

    def item_id(name, kind):
        return next(item["id"] for item in items if item["displayName"] == name and item["type"] == kind)

    if args.kind == "agent":
        name, kind, collection = "MDA Evidence Review Agent", "DataAgent", "dataAgents"
        directory = ROOT / "fabric-items" / (name + ".DataAgent")
        definition = {"parts": [
            {"path": path.relative_to(directory).as_posix(), "payload": base64.b64encode(path.read_bytes()).decode(), "payloadType": "InlineBase64"}
            for path in directory.rglob("*.json")
        ]}
    else:
        from fabricontology import generate_definition_from_package

        name, kind, collection = "mda_test_ontology", "Ontology", "ontologies"
        definition, entities, relationships, bindings, contexts = generate_definition_from_package(
            ontology_package_path=str(ROOT / "Ontology/mda_test_ontology.iq"),
            ontology_name=name,
            binding_workspace_id=WORKSPACE,
            binding_lakehouse_item_id=item_id("IntegratedTestLakehouse", "Lakehouse"),
            binding_lakehouse_schema_name="",
            binding_eventhouse_item_id=item_id("eh_mda_test", "Eventhouse"),
            binding_eventhouse_cluster_uri="https://trd-a9m8t1hz02fkh7c6k4.z9.kusto.fabric.microsoft.com",
            binding_eventhouse_database_name=item_id("kqldb_mda_test", "KQLDatabase"),
        )
        print(json.dumps({"entities": len(entities), "relationships": len(relationships), "bindings": len(bindings), "contextualizations": len(contexts)}))
    existing = [item for item in items if item["displayName"] == name and item["type"] == kind]
    if existing:
        status, result, operation = request(f"/{collection}/{existing[0]['id']}/updateDefinition", {"definition": definition})
    else:
        status, result, operation = request(f"/{collection}", {"displayName": name, "definition": definition})
    print(json.dumps({"status": status, "result": result, "operation": operation}))


if __name__ == "__main__":
    main()