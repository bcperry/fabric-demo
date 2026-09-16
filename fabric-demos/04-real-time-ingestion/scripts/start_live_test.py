import msal
import requests


ACTION = "start"
JOB_RESOURCE_ID = "/subscriptions/a679b60b-99ab-4a54-ac23-2523c39342de/resourceGroups/fabric-mda-demo/providers/Microsoft.App/jobs/job-mda-live-test"
API_VERSION = "2024-03-01"
DASHBOARD_URL = "https://app.fabric.microsoft.com/groups/10327698-2b0d-446f-9b1b-beabe18a4bda/kustodashboards/f4b3e1bd-a1c1-4bd3-a581-98fc9a6912f0"


def control(action, token):
    if action not in {"start", "status", "stop"}:
        raise ValueError("ACTION must be start, status, or stop")
    base = "https://management.azure.com" + JOB_RESOURCE_ID
    with requests.Session() as session:
        session.headers["Authorization"] = "Bearer " + token
        response = session.get(base + "/executions", params={"api-version": API_VERSION}, timeout=60)
        response.raise_for_status()
        executions = response.json()["value"]
        active = [execution for execution in executions
                  if execution["properties"]["status"] in {"Running", "Processing", "Pending"}]
        if action == "start" and not active:
            response = session.post(base + "/start", params={"api-version": API_VERSION}, timeout=60)
            response.raise_for_status()
            print("Flight start accepted:", response.json().get("name", "starting"))
        elif action == "stop":
            for execution in active:
                response = session.post(base + f"/executions/{execution['name']}/stop",
                                        params={"api-version": API_VERSION}, timeout=60)
                response.raise_for_status()
                print("Stop accepted:", execution["name"])
        else:
            print("A flight is already active." if active else "No active flight.")
        print("Monitor:", DASHBOARD_URL)


if __name__ == "__main__":
    if "launcher_auth" not in globals():
        launcher_auth = msal.PublicClientApplication(
            "04b07795-8ddb-461a-bbee-02f9e1bf7b46",
            authority="https://login.microsoftonline.com/a9077aab-55ce-4dac-8343-89d30aeaa786")
    scopes = ["https://management.azure.com/.default"]
    accounts = launcher_auth.get_accounts()
    result = launcher_auth.acquire_token_silent(scopes, account=accounts[0]) if accounts else None
    if not result or "access_token" not in result:
        flow = launcher_auth.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            raise RuntimeError("Could not initiate Azure sign-in.")
        print(flow["message"], flush=True)
        result = launcher_auth.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError("Azure sign-in failed or expired. Run the cell again.")
    control(ACTION, result["access_token"])