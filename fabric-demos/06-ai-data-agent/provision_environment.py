import argparse
import json
from pathlib import Path
import subprocess

import requests


WORKSPACE = "10327698-2b0d-446f-9b1b-beabe18a4bda"
NAME = "MDA Ontology Dependencies"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    token = subprocess.check_output(
        ["az", "account", "get-access-token", "--resource", "https://api.fabric.microsoft.com",
         "--query", "accessToken", "-o", "tsv"], text=True
    ).strip()
    session = requests.Session()
    session.headers["Authorization"] = "Bearer " + token
    base = f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE}/environments"
    response = session.get(base, timeout=120)
    response.raise_for_status()
    listing = response.json()
    if listing.get("continuationToken"):
        raise RuntimeError("Resolve all environment pages before provisioning")
    matches = [item for item in listing["value"] if item["displayName"] == NAME]
    if len(matches) > 1:
        raise RuntimeError("Multiple ontology dependency environments found")
    if not matches:
        if not args.publish:
            print(json.dumps({"environment": NAME, "status": "NOT_CREATED"}))
            return
        response = session.post(base, json={"displayName": NAME}, timeout=120)
        response.raise_for_status()
        if response.status_code == 202:
            print(json.dumps({"operation": response.headers.get("Location"), "status": "CREATING"}))
            return
        matches = [response.json()]
    environment_id = matches[0]["id"]
    url = f"{base}/{environment_id}"
    response = session.get(url, timeout=120)
    response.raise_for_status()
    details = response.json().get("properties", {}).get("publishDetails", {})
    print(json.dumps({"environment_id": environment_id, "publish_details": details}))
    if not args.publish or details.get("state") in {"Running", "Waiting", "Cancelling"}:
        return
    response = session.get(url + "/libraries?beta=false", timeout=120)
    if response.status_code == 404 and response.json().get("errorCode") == "EnvironmentLibrariesNotFound":
        libraries = []
    else:
        response.raise_for_status()
        libraries = response.json().get("libraries", [])
    if any(item.get("name") == "rdflib" and item.get("version") == "7.1.4" for item in libraries):
        print("Required rdflib version is already published")
        return
    with Path(__file__).with_name("environment.yml").open("rb") as library_file:
        response = session.post(
            url + "/staging/libraries/importExternalLibraries",
            data=library_file, headers={"Content-Type": "application/octet-stream"}, timeout=120
        )
    response.raise_for_status()
    response = session.post(url + "/staging/publish?beta=false", timeout=120)
    response.raise_for_status()
    print(json.dumps({"status": response.status_code, "operation": response.headers.get("Location")}))


if __name__ == "__main__":
    main()