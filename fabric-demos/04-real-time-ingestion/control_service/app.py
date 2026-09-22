import hashlib
import json
import os
import re
from uuid import UUID, uuid4

import jwt
import requests
from azure.identity import DefaultAzureCredential
from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from store import Store


PARAMETERS = {"duration": 10, "tspi_hz": 20, "temperature_hz": 2, "error_hz": 1, "seed": 42}
ACTIVE = {"REQUESTED", "STARTING", "RUNNING", "START_UNKNOWN"}
TERMINAL_STATES = {"Succeeded": "SUCCEEDED", "Failed": "FAILED", "Canceled": "CANCELLED", "Cancelled": "CANCELLED"}
VERSION = "2024-03-01"


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: UUID
    preset_id: str


class Arm:
    def __init__(self, resource, image, credential):
        self.resource, self.image, self.credential = resource, image, credential

    def request(self, method, suffix, body=None):
        token = self.credential.get_token("https://management.azure.com/.default").token
        response = requests.request(method, "https://management.azure.com" + self.resource + suffix,
                                    params={"api-version": VERSION}, json=body, timeout=30,
                                    headers={"Authorization": "Bearer " + token}, allow_redirects=False)
        if response.status_code not in {200, 201, 202, 204}:
            raise ValueError("ARM request failed")
        return response

    def execution_suffix(self, execution):
        prefix = self.resource + "/executions/"
        if not execution.startswith(prefix) or not re.fullmatch(r"[A-Za-z0-9_-]+", execution[len(prefix):]):
            raise ValueError("Unbound execution")
        return execution[len(self.resource):]

    def start(self, run_id):
        job = self.request("GET", "").json()
        containers = job["properties"]["template"]["containers"]
        if job["id"].lower() != self.resource.lower() or len(containers) != 1:
            raise ValueError("Unexpected job")
        container = containers[0]
        if container["image"] != self.image or container.get("command"):
            raise ValueError("Job must use the approved image entrypoint")
        args = ["--transport", "kafka", "--event-hubs", "--run-id", run_id]
        for name, value in PARAMETERS.items():
            args.extend(["--" + name.replace("_", "-"), str(value)])
        override = {key: container[key] for key in ("name", "image", "resources", "env") if key in container}
        override["args"] = args
        result = self.request("POST", "/start", {"containers": [override]}).json()
        execution = result["id"]
        self.execution_suffix(execution)
        return execution

    def status(self, execution):
        result = self.request("GET", self.execution_suffix(execution)).json()
        if result["id"] != execution:
            raise ValueError("Execution mismatch")
        return result["properties"]["status"]

    def stop(self, execution):
        self.request("POST", self.execution_suffix(execution) + "/stop")


def create_app(store=None, arm=None):
    tenant = str(UUID(os.environ["CONTROL_TENANT_ID"]))
    audience = str(UUID(os.environ["CONTROL_AUDIENCE"]))
    roles = json.loads(os.environ.get("CONTROL_ROLE_MAP_JSON", "{}"))
    if not isinstance(roles, dict) or any(
        str(UUID(actor)) != actor or not isinstance(values, list)
        or any(not isinstance(value, str) or value not in {"consumer", "operator", "publisher", "reviewer"}
               for value in values)
        for actor, values in roles.items()
    ):
        raise ValueError("Invalid role configuration")
    image, resource = os.environ["CONTROL_IMAGE"], os.environ["CONTROL_JOB_RESOURCE_ID"]
    repository = r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
    if not re.fullmatch(rf"[a-z0-9]+(?:[.-][a-z0-9]+)*/{repository}(?:/{repository})*@sha256:[0-9a-f]{{64}}", image):
        raise ValueError("A digest-pinned image is required")
    if not re.fullmatch(r"/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[A-Za-z0-9_.()-]+/providers/Microsoft\.App/jobs/[A-Za-z0-9-]+", resource):
        raise ValueError("Invalid job resource")
    UUID(resource.split("/")[2])
    identity = str(UUID(os.environ["CONTROL_IDENTITY_CLIENT_ID"]))
    if not os.environ.get("PGUSER", "").strip():
        raise ValueError("A database runtime principal is required")
    credential = DefaultAzureCredential(
        managed_identity_client_id=identity, exclude_environment_credential=True,
        exclude_workload_identity_credential=True, exclude_shared_token_cache_credential=True,
        exclude_visual_studio_code_credential=True, exclude_cli_credential=True,
        exclude_powershell_credential=True, exclude_developer_cli_credential=True,
        exclude_interactive_browser_credential=True, exclude_broker_credential=True)
    store = store if store is not None else Store(credential)
    arm = arm if arm is not None else Arm(resource, image, credential)
    issuer = f"https://login.microsoftonline.com/{tenant}/v2.0"
    jwks = jwt.PyJWKClient(f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys", timeout=10)
    bearer = HTTPBearer(auto_error=False)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse(status_code=422, content={"detail": "Invalid request"})

    @app.exception_handler(Exception)
    async def unavailable(request, error):
        return JSONResponse(status_code=503, content={"detail": "Control service unavailable"})

    def principal(auth: HTTPAuthorizationCredentials | None = Depends(bearer)):
        try:
            if auth is None or auth.scheme.lower() != "bearer":
                raise ValueError("Missing bearer")
            if jwt.get_unverified_header(auth.credentials).get("alg") != "RS256":
                raise ValueError("Invalid algorithm")
            claims = jwt.decode(auth.credentials, jwks.get_signing_key_from_jwt(auth.credentials).key,
                                algorithms=["RS256"], audience=audience, issuer=issuer,
                                options={"require": ["tid", "oid", "exp", "iss", "aud", "ver"], "strict_aud": True})
            actor = str(UUID(claims["oid"]))
            if claims["tid"] != tenant or claims["ver"] != "2.0":
                raise ValueError("Invalid tenant or token version")
        except Exception:
            raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate": "Bearer"}) from None
        assigned = set(roles.get(actor, []))
        if not assigned:
            raise HTTPException(403, "Access denied")
        return actor, assigned

    def require(principal, allowed):
        if not principal[1] & allowed:
            raise HTTPException(403, "Access denied")

    def owned(run_id, principal):
        require(principal, {"operator"})
        run = store.get(str(run_id))
        if not run or run["actor"] != principal[0]:
            raise HTTPException(404, "Run not found")
        if not run["execution_id"] or run["state"] not in ACTIVE:
            raise HTTPException(409, "No active bound execution; manual review may be required")
        return run

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/catalog")
    def catalog(caller=Depends(principal)):
        require(caller, {"consumer", "operator"})
        return {"presets": [{"preset_id": "normal-collection", "parameters": PARAMETERS}]}

    @app.get("/runs")
    def runs(caller=Depends(principal)):
        require(caller, {"consumer", "operator"})
        return store.list(None if "reviewer" in caller[1] else caller[0])

    @app.post("/runs")
    def start(body: RunRequest, caller=Depends(principal)):
        require(caller, {"operator"})
        if body.preset_id != "normal-collection":
            raise HTTPException(422, "Preset not approved")
        manifest = {"run_id": str(uuid4()), "actor": caller[0], "input": body.model_dump(mode="json"),
                    "parameters": dict(PARAMETERS), "transport": "event-hubs", "image": image, "job_resource_id": resource}
        digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        run, created = store.reserve(manifest, digest)
        if not created:
            return run
        run = store.transition(run["run_id"], "REQUESTED", "STARTING")
        try:
            execution = arm.start(run["run_id"])
        except Exception:
            return store.transition(run["run_id"], "STARTING", "START_UNKNOWN")
        return store.transition(run["run_id"], "STARTING", "RUNNING", execution)

    @app.post("/runs/{run_id}/reconcile")
    def reconcile(run_id: UUID, caller=Depends(principal)):
        run = owned(run_id, caller)
        status = arm.status(run["execution_id"])
        if status in TERMINAL_STATES:
            return store.transition(run["run_id"], run["state"], TERMINAL_STATES[status])
        return run

    @app.post("/runs/{run_id}/stop")
    def stop(run_id: UUID, caller=Depends(principal)):
        run = owned(run_id, caller)
        arm.stop(run["execution_id"])
        return {"run_id": run["run_id"], "state": run["state"], "stop_requested": True}

    return app


app = create_app()