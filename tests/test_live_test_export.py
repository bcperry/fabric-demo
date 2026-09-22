import importlib.util
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "fabric-demos/04-real-time-ingestion/scripts/export_live_test_evidence.py"
SPEC = importlib.util.spec_from_file_location("export_live_test_evidence", SCRIPT)
exporter = importlib.util.module_from_spec(SPEC)
with patch.object(sys, "path", [str(SCRIPT.parent), *sys.path]):
    SPEC.loader.exec_module(exporter)
RUN_ID = "36adf728-d3b8-44ac-97e2-e3823d453b11"
JOB = f"/subscriptions/{RUN_ID}/resourceGroups/demo/providers/Microsoft.App/jobs/job-demo"
ENVIRONMENT = JOB.replace("jobs/job-demo", "managedEnvironments/env-demo")
TIME = "2026-09-18T12:00:00Z"


def table(column, rows):
    return {"tables": [{"columns": [{"name": column}], "rows": [[row] for row in rows]}]}


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.started = {"schema_version": "live-test-diagnostic.v1", "kind": "started", "run_id": RUN_ID,
                        "vehicle_id": "target-01", "seed": 17, "event_time_utc": TIME,
                        "duration_seconds": 1, "rates": {"tspi": 2, "temperature": 1, "error": 1}}
        self.execution = {"id": JOB + "/executions/job-demo-123", "properties": {"status": "Succeeded",
                          "template": {"containers": [{"name": "producer", "image": "registry/image@sha256:" + "a" * 64,
                                                        "env": [{"name": "SECRET", "value": "do-not-retain"}]}]}}}
        self.cli = Mock(side_effect=lambda *arguments: ENVIRONMENT if "--query" in arguments else self.execution)
        self.http = Mock(side_effect=lambda url, **kwargs: Mock(status_code=200, json=lambda: table(
            "record", [] if "ContainerAppSystemLogs" in kwargs["json"].get("query", "") else [self.started])))
        self.tokens = Mock(return_value="private-token")

    def acquire(self, **kwargs):
        return exporter.acquire(RUN_ID, "job-demo-123", JOB, RUN_ID, cli=self.cli, http=self.http,
                                token_getter=self.tokens, **kwargs)

    def test_acquisition_is_read_only_and_uses_execution_digest(self):
        files = self.acquire()
        manifest = files["manifest.json"]
        self.assertEqual(manifest["assets"], [{"asset_id": "producer", "image_digest": "sha256:" + "a" * 64}])
        self.assertEqual(manifest["seed"], 17)
        self.assertEqual(manifest["input"], {})
        self.assertEqual(files["acquisition.json"]["platform_status"], "NO_RECORDS")
        for call in self.cli.call_args_list:
            self.assertIn("get", call.args)
            self.assertIn("api-version=2024-03-01", call.args[4])
        for call in self.http.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 60)
            self.assertFalse(call.kwargs["allow_redirects"])
            self.assertIn(ENVIRONMENT, call.kwargs["json"]["query"])
        self.assertNotIn("private-token", json.dumps(files))
        self.assertNotIn("do-not-retain", json.dumps(files))
        summary = exporter.collector.collect_evidence(manifest, [], files["diagnostics.json"], files["execution.json"])
        self.assertEqual(summary["evidence_state"], "INCOMPLETE")

    def test_missing_diagnostics_are_not_fabricated(self):
        self.http.side_effect = None
        self.http.return_value = Mock(status_code=200, json=lambda: table("record", []))
        with self.assertRaisesRegex(ValueError, "started diagnostic"):
            self.acquire()

    def test_tagged_or_absent_execution_images_remain_unavailable(self):
        for template in ({"containers": [{"name": "producer", "image": "registry/image:latest"}]}, {}):
            self.execution["properties"]["template"] = template
            files = self.acquire()
            self.assertNotIn("image_digest", json.dumps(files["manifest.json"]["assets"]))
            self.assertEqual(files["acquisition.json"]["digest_status"], "UNAVAILABLE_OR_PARTIAL")

    def test_foreign_execution_and_ambiguous_starts_fail(self):
        self.execution["id"] += "-other"
        with self.assertRaisesRegex(ValueError, "different execution"):
            self.acquire()
        self.http.assert_not_called()
        self.execution["id"] = JOB + "/executions/job-demo-123"
        self.http.side_effect = lambda *args, **kwargs: Mock(status_code=200, json=lambda: table(
            "record", [self.started, dict(self.started, seed=18)]))
        with self.assertRaisesRegex(ValueError, "distinct started"):
            self.acquire()

    def test_dedicated_queries_are_scoped_without_missing_table_union(self):
        query = exporter.log_query(JOB, "job-demo-123", ENVIRONMENT, RUN_ID)
        self.assertTrue(query.startswith("ContainerAppConsoleLogs |"))
        self.assertNotIn("union", query)
        for text in (
                     "coalesce(", 'column_ifexists("Log_s", "")', 'column_ifexists("JobName_s", "")',
                     f"_ResourceId in~ ('{JOB}', '{ENVIRONMENT}')", "job in ('job-demo', 'job-demo-123')",
                     "isempty(execution) or execution == 'job-demo-123'", f"tostring(record.run_id) == '{RUN_ID}'"):
            self.assertIn(text, query)

    def test_log_analytics_timestamp_preserves_microsecond_value(self):
        self.assertEqual(exporter.collector._timestamp("2026-09-18T14:05:27.8794620Z"),
                         "2026-09-18T14:05:27.879462Z")

    def test_acquired_manifest_does_not_claim_catalog_contract(self):
        files = self.acquire()
        self.assertEqual(files["manifest.json"]["schema_version"], "live-test-acquired-run.v1")
        exporter.collector._context(files["manifest.json"], files["execution.json"])

    def test_kusto_json_and_dynamic_events_keep_only_safe_measurements(self):
        event = {"schema_version": "target-vehicle.v1", "run_id": RUN_ID, "vehicle_id": "target-01",
                 "event_id": RUN_ID + ":1", "sequence_number": 1, "channel": "temperature",
                 "event_time_utc": TIME, "startup_seed": 17, "synthetic": True,
                 "data": {"temperature_c": 12.5}, "measurement_sha256": "secret-value", "extra": "private"}
        logs_http = self.http.side_effect
        for encoded in (event, json.dumps(event)):
            def respond(url, **kwargs):
                if url.endswith("/v2/rest/query"):
                    self.assertEqual(kwargs["json"], {"db": "live-test", "csl":
                        f"RawTargetVehicleEvents | where tostring(event.run_id) == '{RUN_ID}' | project event"})
                    return Mock(status_code=200, json=lambda: [{"TableKind": "PrimaryResult",
                                "Columns": [{"ColumnName": "event"}], "Rows": [[encoded]]},
                                {"FrameType": "DataSetCompletion", "HasErrors": False}])
                return logs_http(url, **kwargs)
            self.http.side_effect = respond
            files = self.acquire(kusto_endpoint="https://demo.z9.kusto.fabric.microsoft.com", database="live-test")
            self.assertEqual(files["telemetry.json"][0]["data"], {"temperature_c": 12.5})
            self.assertNotIn("secret-value", json.dumps(files))
            self.assertNotIn("private", json.dumps(files))
            self.tokens.assert_any_call("https://kusto.kusto.windows.net")
            summary = exporter.collector.collect_evidence(files["manifest.json"], files["telemetry.json"],
                                                          files["diagnostics.json"], files["execution.json"])
            self.assertEqual(summary["counts"]["invalid_telemetry"], 0)

    def test_unsafe_or_unpaired_kusto_arguments_fail_before_cloud_access(self):
        for arguments in ({"database": "demo"}, {"kusto_endpoint": "https://demo.kusto.windows.net"},
                          {"database": "demo", "kusto_endpoint": "https://example.org"},
                          {"database": "demo", "kusto_endpoint": "https://demo.kusto.windows.net@evil.example"},
                          {"database": "demo", "kusto_endpoint": "https://demo.kusto.windows.net/query"},
                          {"database": "demo' | take 1", "kusto_endpoint": "https://demo.kusto.windows.net"}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.acquire(**arguments)
        self.cli.assert_not_called()
        self.tokens.assert_not_called()

    def test_platform_records_are_separate_sanitized_and_not_execution_proof(self):
        logs_http = self.http.side_effect
        def respond(url, **kwargs):
            if "ContainerAppSystemLogs" in kwargs["json"].get("query", ""):
                return Mock(status_code=200, json=lambda: {"tables": [{"columns": [
                    {"name": "time"}, {"name": "reason"}, {"name": "Log"}],
                    "rows": [[TIME, "password secret", "raw private log"]]}]})
            return logs_http(url, **kwargs)
        self.http.side_effect = respond
        files = self.acquire()
        self.assertEqual(files["platform.json"], [{"time": TIME, "reason": "REDACTED", "scope": "JOB",
                                                  "execution_linkage": "NOT_PROVEN"}])
        self.assertEqual(files["acquisition.json"]["platform_status"], "RETRIEVED")
        self.assertNotIn("raw private log", json.dumps(files))
        self.assertEqual(len(files["diagnostics.json"]), 1)

    def test_unavailable_platform_logs_do_not_claim_attachment(self):
        logs_http = self.http.side_effect
        self.http.side_effect = lambda url, **kwargs: (Mock(status_code=403)
            if "ContainerAppSystemLogs" in kwargs["json"].get("query", "") else logs_http(url, **kwargs))
        files = self.acquire()
        self.assertEqual(files["platform.json"], [])
        self.assertEqual(files["acquisition.json"]["platform_status"], "QUERY_FAILED")

    def test_http_and_cli_failures_do_not_expose_secrets(self):
        for status in (302, 401, 403, 429, 500):
            response = Mock(status_code=status, text="private-token")
            with self.assertRaisesRegex(ValueError, f"HTTP {status}") as error:
                exporter.query("https://example", {}, "audience", Mock(return_value=response), self.tokens)
            response.json.assert_not_called()
            self.assertNotIn("private-token", str(error.exception))
        with patch.object(exporter.subprocess, "run", side_effect=subprocess.CalledProcessError(
                1, ["az"], output="private-token", stderr="private-token")):
            with self.assertRaisesRegex(ValueError, "Azure CLI read failed") as error:
                exporter.access_token("https://api.loganalytics.io")
            self.assertNotIn("private-token", str(error.exception))

    def test_token_capture_is_private_and_has_a_timeout(self):
        with patch.object(exporter.subprocess, "run", return_value=Mock(stdout='"private-token"')) as process:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(exporter.access_token("https://api.loganalytics.io"), "private-token")
            self.assertEqual(stdout.getvalue(), "")
            self.assertTrue(process.call_args.kwargs["capture_output"])
            self.assertEqual(process.call_args.kwargs["timeout"], 90)
            self.assertIn("get-access-token", process.call_args.args[0])

    def test_files_are_private_new_and_compatible_with_collector_bundle(self):
        files = self.acquire()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "export"
            arguments = ["--run-id", RUN_ID, "--execution-id", "job-demo-123", "--job-resource-id", JOB,
                         "--log-workspace-id", RUN_ID, "--output-directory", str(output)]
            with patch.object(exporter, "acquire", return_value=files) as acquire:
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(exporter.main(arguments), 0)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(output.stat().st_mode & 0o777, 0o700)
                self.assertEqual({path.name for path in output.iterdir()}, set(files))
                for name, value in files.items():
                    self.assertEqual((output / name).stat().st_mode & 0o777, 0o600)
                    self.assertEqual(json.loads((output / name).read_text()), value)
                acquire.reset_mock()
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    exporter.main(arguments)
                acquire.assert_not_called()
                alias = root / "alias"
                alias.symlink_to(root / "absent")
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    exporter.main([*arguments[:-1], str(alias)])
                acquire.assert_not_called()
            exporter.collector.write_bundle(files["manifest.json"], files["telemetry.json"],
                                            files["diagnostics.json"], files["execution.json"], root / "bundle")
            projected = json.loads((root / "bundle" / "manifest.json").read_text())
            self.assertEqual(projected["projection"]["contract_validation"], "not_performed")
            self.assertIsNone(projected["input"]["sha256"])

    def test_identifiers_reject_query_and_path_injection(self):
        exporter.validate_ids(RUN_ID, "job-demo-123", JOB, RUN_ID)
        for position, value in ((0, "' or true"), (1, "../job"), (1, "x" * 65),
                                (2, JOB + "/executions/other"), (2, JOB + "?query=x"), (2, JOB.replace("Microsoft.App", "MicrosoftXApp")),
                                (3, "/subscriptions/workspace")):
            arguments = [RUN_ID, "job-demo-123", JOB, RUN_ID]
            arguments[position] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                exporter.validate_ids(*arguments)

    def test_logs_and_kusto_tables(self):
        logs = {"tables": [{"columns": [{"name": "event", "type": "dynamic"}], "rows": [[{"run_id": RUN_ID}]]}]}
        kusto = [{"FrameType": "DataTable", "TableKind": "PrimaryResult",
                  "Columns": [{"ColumnName": "event"}], "Rows": [[{"run_id": RUN_ID}]]},
                 {"FrameType": "DataSetCompletion", "HasErrors": False}]
        self.assertEqual(exporter.table_rows(logs), exporter.table_rows(kusto))
        for payload in ({"error": {"message": "private"}, **logs},
                        kusto + [{"HasErrors": True}], {}, {"tables": [{"columns": []}]},
                        {"tables": [{"columns": [{"name": "event"}]}]},
                        {"tables": [{"columns": [{"name": "event"}], "rows": ["x"]}]}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                exporter.table_rows(payload)