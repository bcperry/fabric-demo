import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient


DIRECTORY = Path(__file__).resolve().parents[1] / "fabric-demos/04-real-time-ingestion/control_service"
TENANT, AUDIENCE, OWNER, OTHER, REVIEWER = [str(uuid4()) for _ in range(5)]
JOB = f"/subscriptions/{uuid4()}/resourceGroups/demo/providers/Microsoft.App/jobs/live"
IMAGE = "registry.azurecr.io/target-vehicle@sha256:" + "a" * 64
ENV = {"CONTROL_TENANT_ID": TENANT, "CONTROL_AUDIENCE": AUDIENCE, "CONTROL_IMAGE": IMAGE,
    "CONTROL_IDENTITY_CLIENT_ID": str(uuid4()), "PGUSER": "control-runtime",
       "CONTROL_JOB_RESOURCE_ID": JOB, "CONTROL_ROLE_MAP_JSON": json.dumps(
           {OWNER: ["operator"], OTHER: ["consumer"], REVIEWER: ["consumer", "reviewer"]})}


class MemoryStore:
    def __init__(self):
        self.rows, self.history = {}, []

    def reserve(self, manifest, digest):
        for row in self.rows.values():
            if (row["actor"], row["manifest"]["input"]) == (manifest["actor"], manifest["input"]):
                return row, False
        if any(row["state"] in {"REQUESTED", "STARTING", "RUNNING", "START_UNKNOWN"} for row in self.rows.values()):
            raise HTTPException(409, "Launch unavailable")
        row = dict(run_id=manifest["run_id"], actor=manifest["actor"], manifest=manifest,
                   manifest_sha256=digest, image=manifest["image"], state="REQUESTED", execution_id=None)
        self.rows[row["run_id"]] = row
        self.history.append("REQUESTED")
        return row, True

    def transition(self, run_id, previous, state, execution=None):
        row = self.rows[run_id]
        assert row["state"] == previous
        row.update(state=state, execution_id=execution or row["execution_id"])
        self.history.append(state)
        return row

    def get(self, run_id):
        return self.rows.get(run_id)

    def list(self, actor):
        return [row for row in self.rows.values() if actor is None or actor == row["actor"]]


class ControlTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, ENV)
        environment.start()
        self.addCleanup(environment.stop)
        for target in ("azure.identity.DefaultAzureCredential", "requests.request", "psycopg.connect"):
            blocked = patch(target, side_effect=AssertionError("External access forbidden"))
            if target.endswith("DefaultAzureCredential"):
                blocked = patch(target, return_value=MagicMock())
            blocked.start()
            self.addCleanup(blocked.stop)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        public.update(kid="test", use="sig", alg="RS256")
        keys = patch.object(jwt.PyJWKClient, "fetch_data", return_value={"keys": [public]})
        keys.start()
        self.addCleanup(keys.stop)
        store_spec = importlib.util.spec_from_file_location("control_store", DIRECTORY / "store.py")
        self.store_module = importlib.util.module_from_spec(store_spec)
        store_spec.loader.exec_module(self.store_module)
        spec = importlib.util.spec_from_file_location("control_app", DIRECTORY / "app.py")
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"store": self.store_module}):
            spec.loader.exec_module(self.module)
        self.store, self.arm = MemoryStore(), MagicMock()
        self.arm.start.return_value = JOB + "/executions/known"
        self.client = TestClient(self.module.create_app(self.store, self.arm), raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        self.body = {"idempotency_key": str(uuid4()), "preset_id": "normal-collection"}

    def headers(self, actor=OWNER, **changes):
        claims = dict(tid=TENANT, oid=actor, aud=AUDIENCE, iss=f"https://login.microsoftonline.com/{TENANT}/v2.0",
                      exp=int(time.time()) + 300, ver="2.0")
        claims.update(changes)
        claims = {name: value for name, value in claims.items() if value is not None}
        return {"Authorization": "Bearer " + jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "test"})}

    def launch(self, **kwargs):
        return self.client.post("/runs", json=self.body, headers=self.headers(), **kwargs)

    def test_authentication_and_empty_map_deny(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        for claims in ({"exp": 1}, {"exp": None}, {"tid": OTHER}, {"oid": "bad"}, {"oid": None},
                       {"aud": OTHER}, {"iss": "https://attacker.invalid"}, {"ver": "1.0"}):
            self.assertEqual(self.client.get("/catalog", headers=self.headers(**claims)).status_code, 401)
        for token in ("broken", jwt.encode({"oid": OWNER}, "secret", algorithm="HS256"),
                      jwt.encode({"oid": OWNER}, "", algorithm="none")):
            self.assertEqual(self.client.get("/catalog", headers={"Authorization": "Bearer " + token}).status_code, 401)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.assertEqual(self.client.get("/catalog", headers=self.headers()).status_code, 401)
        self.assertEqual(self.client.get("/catalog", headers={"X-MS-CLIENT-PRINCIPAL": OWNER, "roles": "operator"}).status_code, 401)
        self.arm.start.assert_not_called()

    def test_roles_are_server_mapped_and_default_deny(self):
        self.assertEqual(self.client.get("/catalog", headers=self.headers(str(uuid4()), roles=["operator"])).status_code, 403)
        self.assertEqual(self.client.post("/runs", json=self.body, headers=self.headers(OTHER, roles=["operator"])).status_code, 403)
        with patch.dict(os.environ, {"CONTROL_ROLE_MAP_JSON": "{}"}):
            with TestClient(self.module.create_app(self.store, self.arm)) as client:
                for path in ("/catalog", "/runs"):
                    self.assertEqual(client.get(path, headers=self.headers()).status_code, 403)
                for path in ("/runs", f"/runs/{uuid4()}/stop", f"/runs/{uuid4()}/reconcile"):
                    self.assertEqual(client.post(path, json=self.body, headers=self.headers()).status_code, 403)

    def test_reviewer_requires_explicit_read_role_and_cannot_operate(self):
        run = self.launch().json()
        for assigned, expected in ((["reviewer"], 403), (["consumer", "reviewer"], 200)):
            with self.subTest(assigned=assigned), patch.dict(os.environ, {
                "CONTROL_ROLE_MAP_JSON": json.dumps({REVIEWER: assigned})
            }):
                with TestClient(self.module.create_app(self.store, self.arm)) as client:
                    for path in ("/catalog", "/runs"):
                        response = client.get(path, headers=self.headers(REVIEWER))
                        self.assertEqual(response.status_code, expected)
                        if path == "/runs" and expected == 200:
                            self.assertEqual(response.json(), [run])
                    for path in ("/runs", f"/runs/{run['run_id']}/stop", f"/runs/{run['run_id']}/reconcile"):
                        self.assertEqual(client.post(path, json=self.body, headers=self.headers(REVIEWER)).status_code, 403)

    def test_service_principal_requires_explicit_oid_mapping(self):
        self.assertEqual(self.client.get("/catalog", headers=self.headers(idtyp="app")).status_code, 200)
        self.assertEqual(self.client.get("/catalog", headers=self.headers(
            str(uuid4()), idtyp="app", roles=["operator"])).status_code, 403)
        self.assertEqual(self.client.get("/catalog", headers=self.headers(idtyp="app", oid=None)).status_code, 401)

    def test_reservation_precedes_network_and_retry_never_starts(self):
        def start(run_id):
            self.assertEqual(self.store.history, ["REQUESTED", "STARTING"])
            row = self.store.get(run_id)
            self.assertEqual(row["manifest_sha256"], hashlib.sha256(json.dumps(
                row["manifest"], sort_keys=True, separators=(",", ":")).encode()).hexdigest())
            self.assertEqual(row["manifest"]["actor"], OWNER)
            return JOB + "/executions/known"
        self.arm.start.side_effect = start
        first = self.launch().json()
        self.assertEqual(first["state"], "RUNNING")
        self.assertEqual(self.launch().json(), first)
        self.arm.start.assert_called_once()
        self.body["idempotency_key"] = str(uuid4())
        self.assertEqual(self.launch().status_code, 409)
        self.assertEqual(self.client.get("/runs", headers=self.headers(OTHER)).json(), [])
        self.assertEqual(len(self.client.get("/runs", headers=self.headers(REVIEWER)).json()), 1)
        with patch.dict(os.environ, {"CONTROL_ROLE_MAP_JSON": json.dumps({OTHER: ["operator"]})}):
            with TestClient(self.module.create_app(self.store, self.arm)) as client:
                for action in ("stop", "reconcile"):
                    self.assertEqual(client.post(f"/runs/{first['run_id']}/{action}", headers=self.headers(OTHER)).status_code, 404)

    def test_unknown_is_reserved_and_never_reconciled_by_guessing(self):
        self.arm.start.side_effect = RuntimeError("secret-network-body")
        response = self.launch()
        self.assertNotIn("secret", response.text)
        run = response.json()
        self.assertEqual(run["state"], "START_UNKNOWN")
        self.launch()
        self.arm.start.assert_called_once()
        for action in ("stop", "reconcile"):
            self.assertEqual(self.client.post(f"/runs/{run['run_id']}/{action}", headers=self.headers()).status_code, 409)
        self.arm.status.assert_not_called()
        self.arm.stop.assert_not_called()

    def test_only_confirmed_terminal_execution_releases(self):
        run = self.launch().json()
        path = f"/runs/{run['run_id']}"
        self.assertEqual(self.client.post(path + "/stop", headers=self.headers()).status_code, 200)
        self.arm.stop.assert_called_once_with(JOB + "/executions/known")
        self.arm.status.return_value = "Stopped"
        self.assertEqual(self.client.post(path + "/reconcile", headers=self.headers()).json()["state"], "RUNNING")
        self.arm.status.side_effect = RuntimeError("secret-error")
        response = self.client.post(path + "/reconcile", headers=self.headers())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)
        self.arm.status.side_effect = None
        self.arm.status.return_value = "Succeeded"
        self.assertEqual(self.client.post(path + "/reconcile", headers=self.headers()).json()["state"], "SUCCEEDED")
        self.body["idempotency_key"] = str(uuid4())
        self.assertEqual(self.launch().status_code, 200)

    def test_unapproved_inputs_rejected(self):
        for changes in ({"preset_id": "feed-pause"}, {"idempotency_key": "bad"}, {"actor": OTHER},
                        {"duration": 999}, {"image": "arbitrary"}, {"command": ["secret"]}):
            response = self.client.post("/runs", json=self.body | changes, headers=self.headers())
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("secret", response.text)
        self.arm.start.assert_not_called()

    def test_cancelled_executions_release_the_active_reservation(self):
        for status in ("Canceled", "Cancelled", "Failed"):
            with self.subTest(status=status):
                self.body["idempotency_key"] = str(uuid4())
                response = self.launch()
                self.assertEqual(response.status_code, 200, response.text)
                run = response.json()
                self.arm.status.return_value = status
                response = self.client.post(f"/runs/{run['run_id']}/reconcile", headers=self.headers())
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["state"], "FAILED" if status == "Failed" else "CANCELLED")
                self.assertEqual(self.launch().json(), response.json())
        self.body["idempotency_key"] = str(uuid4())
        self.assertEqual(self.launch().status_code, 200)
        self.assertEqual(self.arm.start.call_count, 4)

    def test_running_transition_failure_is_not_misclassified_as_start_failure(self):
        for committed in (False, True):
            with self.subTest(committed=committed):
                self.store.rows.clear()
                self.store.history.clear()
                self.arm.start.reset_mock()
                transition = self.store.transition

                def fail_running(run_id, previous, state, execution=None):
                    if state == "RUNNING":
                        if committed:
                            transition(run_id, previous, state, execution)
                        raise RuntimeError("secret-database-error")
                    return transition(run_id, previous, state, execution)

                with patch.object(self.store, "transition", side_effect=fail_running) as calls:
                    response = self.launch()
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("secret", response.text)
                self.assertEqual([call.args[2] for call in calls.call_args_list], ["STARTING", "RUNNING"])
                self.assertEqual(self.launch().json()["state"], "RUNNING" if committed else "STARTING")
                self.arm.start.assert_called_once()

    def test_unknown_transition_failure_remains_unavailable_and_reserved(self):
        self.arm.start.side_effect = RuntimeError("secret-arm-error")
        transition = self.store.transition

        def fail_unknown(run_id, previous, state, execution=None):
            if state == "START_UNKNOWN":
                raise RuntimeError("secret-database-error")
            return transition(run_id, previous, state, execution)

        with patch.object(self.store, "transition", side_effect=fail_unknown):
            response = self.launch()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)
        self.assertEqual(self.launch().json()["state"], "STARTING")
        self.arm.start.assert_called_once()

    def test_configuration_validates_complete_identifiers_and_image(self):
        changes = [
            {name: "not-a-uuid"} for name in ("CONTROL_TENANT_ID", "CONTROL_AUDIENCE", "CONTROL_IDENTITY_CLIENT_ID")
        ] + [
            {"CONTROL_JOB_RESOURCE_ID": JOB.replace(JOB.split("/")[2], "-" * 36)},
            {"CONTROL_JOB_RESOURCE_ID": JOB + "/executions/other"},
            {"CONTROL_JOB_RESOURCE_ID": JOB + "\n"},
            {"CONTROL_IMAGE": IMAGE + "\n"},
            {"CONTROL_IMAGE": IMAGE[:-1]},
            {"CONTROL_IMAGE": IMAGE.replace("/target-vehicle", "//target-vehicle")},
            {"CONTROL_IMAGE": IMAGE.replace("/target-vehicle", "/../target-vehicle")},
            {"CONTROL_IMAGE": IMAGE.replace("@sha256:", ":latest@sha256:")},
            {"CONTROL_IMAGE": "target-vehicle@sha256:" + "a" * 64},
            {"PGUSER": " "},
            {"CONTROL_ROLE_MAP_JSON": "[]"},
            {"CONTROL_ROLE_MAP_JSON": json.dumps({OWNER: ["admin"]})},
            {"CONTROL_ROLE_MAP_JSON": json.dumps({OWNER: [{}]})},
            {"CONTROL_ROLE_MAP_JSON": json.dumps({OWNER: "operator"})},
            {"CONTROL_ROLE_MAP_JSON": json.dumps({"not-a-uuid": ["operator"]})},
        ]
        for values in changes:
            with self.subTest(values=values), patch.dict(os.environ, values), self.assertRaises(ValueError):
                self.module.create_app(self.store, self.arm)
        self.arm.start.assert_not_called()

    def test_arm_allowlist_payload_and_exact_binding(self):
        credential = MagicMock()
        credential.get_token.return_value.token = "token"
        arm = self.module.Arm(JOB, IMAGE, credential)
        container = dict(name="target-vehicle", image=IMAGE, resources={"cpu": 0.25, "memory": "0.5Gi"}, env=[])
        job = dict(id=JOB, properties={"template": {"containers": [container], "initContainers": [{"image": "bad"}]}})
        replies = [MagicMock(status_code=200), MagicMock(status_code=202)]
        replies[0].json.return_value = job
        replies[1].json.return_value = {"id": JOB + "/executions/known"}
        with patch.object(self.module.requests, "request", side_effect=replies) as network:
            run_id = str(uuid4())
            self.assertEqual(arm.start(run_id), JOB + "/executions/known")
            body = network.call_args.kwargs["json"]
            self.assertEqual(set(body), {"containers"})
            self.assertEqual(body["containers"][0]["args"], ["--transport", "kafka", "--event-hubs", "--run-id", run_id,
                             "--duration", "10", "--tspi-hz", "20", "--temperature-hz", "2", "--error-hz", "1", "--seed", "42"])
            self.assertEqual(network.call_args.kwargs["params"], {"api-version": "2024-03-01"})
            self.assertFalse(network.call_args.kwargs["allow_redirects"])
        with patch.object(arm, "request") as network:
            arm.stop(JOB + "/executions/known")
            network.assert_called_once_with("POST", "/executions/known/stop")
        with patch.object(arm, "request", return_value=replies[1]):
            replies[1].json.return_value = {"id": JOB + "/executions/other", "properties": {"status": "Succeeded"}}
            with self.assertRaises(ValueError):
                arm.status(JOB + "/executions/known")
        for execution in (JOB + "/executions/../bad", JOB + "evil/executions/known", "/other/executions/known"):
            with self.assertRaises(ValueError):
                arm.stop(execution)
        container["image"] = "unapproved"
        with patch.object(arm, "request", return_value=replies[0]) as network:
            with self.assertRaises(ValueError):
                arm.start(str(uuid4()))
            self.assertEqual(network.call_count, 1)

    def test_sql_concurrency_immutability_and_grant_contract(self):
        sql = (DIRECTORY / "schema.sql").read_text()
        source = inspect.getsource(self.store_module.Store.reserve)
        self.assertIn("pg_advisory_xact_lock", source)
        self.assertLess(source.index("pg_advisory_xact_lock"), source.index("INSERT INTO"))
        for fragment in ("UNIQUE (actor, idempotency_key)", "single_active_run", "((true))", "'START_UNKNOWN'",
                         "BEFORE UPDATE", "to_jsonb(NEW)", "OLD.execution_id", "GRANT UPDATE (state, execution_id)",
                         "REVOKE ALL ON SCHEMA", "A separate nonadmin runtime role is required",
                         "DROP CONSTRAINT IF EXISTS runs_state_check", "DROP CONSTRAINT IF EXISTS runs_check",
                         "NEW.state IN ('SUCCEEDED','FAILED','CANCELLED')",
                         "state NOT IN ('RUNNING','SUCCEEDED','FAILED','CANCELLED') OR execution_id IS NOT NULL",
                         "AND NOT rolreplication AND NOT rolbypassrls"):
            self.assertIn(fragment, sql)
        self.assertNotIn("GRANT ALL", sql)
        self.assertNotRegex(sql, r"(?i)GRANT[^;]+TO\s+PUBLIC")
        predicate = sql.split("CREATE UNIQUE INDEX IF NOT EXISTS single_active_run", 1)[1].split(";", 1)[0]
        self.assertIn("WHERE state IN ('REQUESTED','STARTING','RUNNING','START_UNKNOWN')", predicate)
        self.assertNotIn("CANCELLED", predicate)

    def test_database_uses_entra_token_and_fixed_tls_destination(self):
        credential = MagicMock()
        credential.get_token.return_value.token = "database-token"
        with patch.object(self.store_module.psycopg, "connect") as connect:
            self.store_module.Store(credential).connect()
        credential.get_token.assert_called_once_with("https://ossrdbms-aad.database.windows.net/.default")
        options = connect.call_args.kwargs
        self.assertEqual(options["host"], "pg-mda-demo-4u6mawdzlpyh4.postgres.database.azure.com")
        self.assertEqual(options["dbname"], "mdaoperations")
        self.assertEqual(options["password"], "database-token")
        self.assertEqual((options["sslmode"], options["connect_timeout"]), ("require", 10))

    def test_store_normalizes_real_uuid_rows_on_every_return_path(self):
        run = self.launch().json()
        run["idempotency_key"] = self.body["idempotency_key"]
        store = self.store_module.Store(MagicMock())
        for identifiers in (str, UUID):
            raw = run | {name: identifiers(run[name]) for name in ("run_id", "actor", "idempotency_key")}
            with self.subTest(identifiers=identifiers), patch.object(store, "connect") as connect:
                connection = connect.return_value.__enter__.return_value
                cursor = connection.execute.return_value
                cursor.fetchone.return_value = raw
                cursor.fetchall.return_value = [raw]
                self.assertEqual(store.get(run["run_id"]), run)
                self.assertEqual(store.transition(run["run_id"], "STARTING", "RUNNING"), run)
                self.assertEqual(store.list(OWNER), [run])
                query, parameters = connection.execute.call_args.args
                self.assertIn("WHERE actor=%s", query)
                self.assertNotIn("::text", query)
                self.assertEqual(parameters, (OWNER,))
                self.assertEqual(store.list(None), [run])
                self.assertNotIn("WHERE", connection.execute.call_args.args[0])
                self.assertEqual(store.reserve(run["manifest"], run["manifest_sha256"]), (run, False))
                cursor.fetchone.side_effect = [None, None, raw]
                self.assertEqual(store.reserve(run["manifest"], run["manifest_sha256"]), (run, True))
                cursor.fetchone.side_effect = None
                cursor.fetchone.return_value = None
                self.assertIsNone(store.get(run["run_id"]))
                with self.assertRaises(HTTPException) as failure:
                    store.transition(run["run_id"], "STARTING", "RUNNING")
                self.assertEqual(failure.exception.status_code, 409)

    def test_psycopg_uuid_rows_support_arm_json_and_owner_operations(self):
        store = self.store_module.Store(MagicMock())
        rows = {}

        def execute(query, parameters=None):
            cursor = MagicMock()
            if "INSERT INTO" in query:
                run_id, actor, key, manifest, digest, image = parameters
                rows.update(run_id=UUID(run_id), actor=UUID(actor), idempotency_key=UUID(key),
                            manifest=manifest.obj, manifest_sha256=digest, image=image,
                            state="REQUESTED", execution_id=None)
                cursor.fetchone.return_value = dict(rows)
            elif "UPDATE" in query:
                state, execution, run_id, previous = parameters
                self.assertEqual(run_id, str(rows["run_id"]))
                self.assertEqual(previous, rows["state"])
                rows.update(state=state, execution_id=rows["execution_id"] or execution)
                cursor.fetchone.return_value = dict(rows)
            else:
                cursor.fetchone.return_value = dict(rows) if rows else None
            return cursor

        def start(run_id):
            self.assertIsInstance(run_id, str)
            json.dumps({"args": ["--run-id", run_id]})
            return JOB + "/executions/known"

        self.arm.start.side_effect = start
        with patch.object(store, "connect") as connect:
            connect.return_value.__enter__.return_value.execute.side_effect = execute
            with TestClient(self.module.create_app(store, self.arm), raise_server_exceptions=False) as client:
                response = client.post("/runs", json=self.body, headers=self.headers())
                self.assertEqual(response.status_code, 200, response.text)
                run = response.json()
                self.assertEqual(run["state"], "RUNNING")
                self.assertEqual(client.post("/runs", json=self.body, headers=self.headers()).json(), run)
                self.assertEqual(client.post(f"/runs/{run['run_id']}/stop", headers=self.headers()).status_code, 200)
                self.arm.status.return_value = "Succeeded"
                response = client.post(f"/runs/{run['run_id']}/reconcile", headers=self.headers())
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["state"], "SUCCEEDED")
        self.arm.start.assert_called_once()

    def test_store_retry_preserves_manifest_but_changed_input_conflicts(self):
        run = self.launch().json()
        raw = run | {"run_id": UUID(run["run_id"]), "actor": UUID(OWNER),
                     "idempotency_key": UUID(self.body["idempotency_key"])}
        manifest = run["manifest"] | {
            "run_id": str(uuid4()), "image": IMAGE.replace("a" * 64, "b" * 64),
            "parameters": run["manifest"]["parameters"] | {"duration": 20},
            "job_resource_id": JOB + "-changed",
        }
        store = self.store_module.Store(MagicMock())
        with patch.object(store, "connect") as connect:
            connection = connect.return_value.__enter__.return_value
            connection.execute.return_value.fetchone.return_value = raw
            result, created = store.reserve(manifest, "b" * 64)
            self.assertFalse(created)
            self.assertEqual(result["manifest"], run["manifest"])
            self.assertEqual(result["manifest_sha256"], run["manifest_sha256"])
            self.assertEqual(connection.execute.call_count, 2)
            connection.execute.reset_mock()
            manifest["input"] = manifest["input"] | {"preset_id": "different-preset"}
            with self.assertRaises(HTTPException) as failure:
                store.reserve(manifest, "b" * 64)
            self.assertEqual(failure.exception.status_code, 409)
            self.assertEqual(connection.execute.call_count, 2)

    def test_store_reservation_locks_before_checks_and_insert(self):
        run = self.launch().json()
        store = self.store_module.Store(MagicMock())
        with patch.object(store, "connect") as connect:
            connection = connect.return_value.__enter__.return_value
            connection.execute.return_value.fetchone.side_effect = [None, None, run]
            self.assertEqual(store.reserve(run["manifest"], run["manifest_sha256"]), (run, True))
            queries = [call.args[0] for call in connection.execute.call_args_list]
            self.assertEqual(len(queries), 4)
            self.assertIn("pg_advisory_xact_lock", queries[0])
            self.assertIn("WHERE actor=%s AND idempotency_key=%s", queries[1])
            self.assertIn("state IN ('REQUESTED','STARTING','RUNNING','START_UNKNOWN')", queries[2])
            self.assertIn("INSERT INTO", queries[3])
            connection.execute.reset_mock()
            connection.execute.return_value.fetchone.side_effect = [None, {"state": "START_UNKNOWN"}]
            with self.assertRaises(HTTPException) as failure:
                store.reserve(run["manifest"], run["manifest_sha256"])
            self.assertEqual(failure.exception.status_code, 409)
            self.assertEqual(connection.execute.call_count, 3)


if __name__ == "__main__":
    unittest.main()