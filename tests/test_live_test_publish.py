import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

import requests


SCRIPT = Path(__file__).resolve().parents[1] / "fabric-demos/04-real-time-ingestion/scripts/publish_live_test_bundle.py"
SPEC = importlib.util.spec_from_file_location("publish_live_test_bundle", SCRIPT)
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)
COLLECTOR_SPEC = importlib.util.spec_from_file_location("publish_collector", SCRIPT.with_name("collect_live_test.py"))
collector = importlib.util.module_from_spec(COLLECTOR_SPEC)
COLLECTOR_SPEC.loader.exec_module(collector)
WORKSPACE = "36adf728-d3b8-44ac-97e2-e3823d453b11"
LAKEHOUSE = "6ad51217-7918-4b73-b6e8-8aba26d5a112"
RUN_ID = "e2cbfc6a-bfd3-4020-9e42-90d55d5429e1"
SECRET = "private-test-token"


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


class Response:
    def __init__(self, status, content=b"", code=None):
        self.status_code = status
        self.headers = {"x-ms-error-code": code} if code else {}
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset:offset + chunk_size]


class OneLake:
    def __init__(self):
        self.files = {}
        self.directories = set()
        self.flushed = set()
        self.calls = []
        self.renamed = []
        self.race = None
        self.failure = None
        self.cleanup_failure = False

    def request(self, method, url, **kwargs):
        path = urlsplit(url).path
        self.calls.append((method, url, kwargs))
        params, headers = kwargs["params"] or {}, kwargs["headers"]
        if self.failure:
            result = self.failure(method, path, params, headers)
            if result is not None:
                return result
        if method == "GET":
            return Response(200, self.files[path]) if path in self.files else Response(404)
        if method == "DELETE":
            if self.cleanup_failure:
                return Response(403, SECRET.encode())
            existed = self.files.pop(path, None) is not None
            return Response(200 if existed else 404)
        if method == "PUT" and params.get("resource") == "directory":
            if path in self.directories:
                return Response(409, code="PathAlreadyExists")
            self.directories.add(path)
            return Response(201)
        if method == "PUT" and params.get("resource") == "file":
            assert headers["If-None-Match"] == "*"
            assert path.endswith(".tmp")
            if path in self.files:
                return Response(412)
            self.files[path] = b""
            return Response(201)
        if method == "PATCH" and params["action"] == "append":
            assert params["position"] == "0"
            self.files[path] = kwargs["data"]
            return Response(202)
        if method == "PATCH" and params["action"] == "flush":
            assert int(params["position"]) == len(self.files[path])
            self.flushed.add(path)
            return Response(200)
        if method == "PUT" and "x-ms-rename-source" in headers:
            source = headers["x-ms-rename-source"]
            assert headers["If-None-Match"] == "*"
            assert source in self.flushed
            assert not params
            if self.race:
                status, equal = self.race
                self.files[path] = self.files[source] if equal else b"conflict"
                self.race = None
                return Response(status)
            if path in self.files:
                return Response(412)
            self.files[path] = self.files.pop(source)
            self.renamed.append(path)
            return Response(201)
        raise AssertionError((method, path, params))


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "bundle"
        manifest = {
            "schema_version": "live-test-run.v1", "run_id": RUN_ID, "request_id": LAKEHOUSE,
            "preset_id": "short", "requester": "local", "seed": 17, "created_at": "2026-09-18T12:00:00Z",
            "assets": ["target-01"], "input": {},
            "parameters": {"duration_seconds": 1, "tspi_hz": 2, "temperature_hz": 1, "error_hz": 1},
            "executions": [{"execution_id": "job-01", "status": "Succeeded"}],
            "telemetry": [], "logs": [], "outputs": [], "state": "REQUESTED", "evidence_state": "NOT_COLLECTED",
        }
        collector.write_bundle(manifest, [], [], manifest["executions"][0], self.directory)
        self.index = json.loads((self.directory / "bundle.json").read_bytes())
        self.original = {entry.name: entry.read_bytes() for entry in self.directory.iterdir()}
        self.remote = OneLake()

    def publish(self):
        return publisher.publish_bundle(self.directory, WORKSPACE, LAKEHOUSE, session=self.remote, token=SECRET)

    def index_path(self):
        digest = hashlib.sha256((self.directory / "bundle.json").read_bytes()).hexdigest()
        return f"/{WORKSPACE}/{LAKEHOUSE}/Files/live-test-evidence/{RUN_ID}/{digest}/bundle.json"

    def write_index(self, index):
        (self.directory / "bundle.json").write_bytes(canonical(index))

    def test_collector_bundle_published_index_last_and_exact_bytes_verified(self):
        result = self.publish()
        self.assertEqual(result["bundle_uri"], publisher.HOST + self.index_path())
        self.assertEqual(result["manifest_uri"], result["directory_uri"] + "manifest.json")
        self.assertEqual(result["run_id"], RUN_ID)
        self.assertEqual(result["execution_id"], "job-01")
        self.assertEqual(result["bundle_sha256"], hashlib.sha256(self.original["bundle.json"]).hexdigest())
        self.assertEqual([Path(path).name for path in self.remote.renamed], [*publisher.FILES, "bundle.json"])
        self.assertEqual(len(self.remote.files), 5)
        for path, content in self.remote.files.items():
            self.assertEqual(content, self.original[Path(path).name])
            self.assertGreaterEqual(sum(method == "GET" and url == publisher.HOST + path
                                        for method, url, _ in self.remote.calls), 2)
        for _, url, kwargs in self.remote.calls:
            self.assertEqual(urlsplit(url).scheme, "https")
            self.assertEqual(urlsplit(url).netloc, "onelake.dfs.fabric.microsoft.com")
            self.assertFalse(kwargs["allow_redirects"])
            self.assertEqual(kwargs["timeout"], publisher.TIMEOUT)
            self.assertTrue(kwargs["stream"])

    def test_identical_retry_only_reads_files_and_checks_directories(self):
        first = self.publish()
        self.remote.calls.clear()
        self.assertEqual(self.publish(), first)
        self.assertEqual([method for method, _, _ in self.remote.calls], ["PUT"] * 3 + ["GET"] * 5)

    def test_conflicting_final_is_not_overwritten(self):
        path = self.index_path().replace("bundle.json", "manifest.json")
        self.remote.files[path] = b"conflict"
        with self.assertRaisesRegex(publisher.PublishError, "Conflicting final file"):
            self.publish()
        self.assertEqual(self.remote.files, {path: b"conflict"})

    def test_rename_races_verify_content_for_both_conflict_statuses(self):
        for status in (409, 412):
            for equal in (True, False):
                with self.subTest(status=status, equal=equal):
                    self.remote = OneLake()
                    self.remote.race = (status, equal)
                    if equal:
                        self.publish()
                        self.assertIn(self.index_path(), self.remote.files)
                    else:
                        with self.assertRaisesRegex(publisher.PublishError, "Conflicting final file"):
                            self.publish()
                        self.assertNotIn(self.index_path(), self.remote.files)
                    self.assertFalse(any(path.endswith(".tmp") for path in self.remote.files))

    def test_staging_failures_leave_no_marker_and_same_bundle_can_retry(self):
        for operation in ("create", "append", "flush", "rename", "verify"):
            with self.subTest(operation=operation):
                self.remote = OneLake()

                def fail(method, path, params, headers):
                    if ((operation == "create" and params.get("resource") == "file")
                            or (operation in ("append", "flush") and params.get("action") == operation)
                            or (operation == "rename" and "x-ms-rename-source" in headers)):
                        return Response(500, SECRET.encode())
                    if operation == "verify" and method == "GET" and path.endswith(".tmp"):
                        return Response(200, b"bad staged bytes")
                    return None

                self.remote.failure = fail
                with self.assertRaises(publisher.PublishError):
                    self.publish()
                self.assertNotIn(self.index_path(), self.remote.files)
                self.remote.failure = None
                self.publish()
                self.assertIn(self.index_path(), self.remote.files)

    def test_cleanup_error_does_not_hide_conflict_or_prevent_retry(self):
        self.remote.race = (412, False)
        self.remote.cleanup_failure = True
        with self.assertRaisesRegex(publisher.PublishError, "Conflicting final file"):
            self.publish()
        self.assertNotIn(self.index_path(), self.remote.files)

    def test_successful_rename_does_not_require_delete_permission(self):
        self.remote.cleanup_failure = True
        self.publish()
        self.assertFalse(any(method == "DELETE" for method, _, _ in self.remote.calls))

    def test_committed_payload_survives_later_failure_and_retry(self):
        self.remote.failure = lambda method, path, params, headers: (
            Response(500) if params.get("action") == "append" and ".summary.json." in path else None)
        with self.assertRaises(publisher.PublishError):
            self.publish()
        self.assertNotIn(self.index_path(), self.remote.files)
        manifest_path = self.index_path().replace("bundle.json", "manifest.json")
        self.assertEqual(self.remote.files[manifest_path], self.original["manifest.json"])
        self.remote.failure = None
        self.publish()
        self.assertEqual(self.remote.renamed.count(manifest_path), 1)

    def test_lost_rename_response_can_retry_without_overwriting(self):
        def lose_response(method, path, params, headers):
            if "x-ms-rename-source" in headers:
                self.remote.files[path] = self.remote.files.pop(headers["x-ms-rename-source"])
                raise requests.Timeout(SECRET)
            return None

        self.remote.failure = lose_response
        with self.assertRaisesRegex(publisher.PublishError, "transport failed"):
            self.publish()
        self.assertNotIn(self.index_path(), self.remote.files)
        self.remote.failure = None
        self.publish()
        self.assertIn(self.index_path(), self.remote.files)

    def test_final_get_mismatch_or_missing_prevents_completion_marker(self):
        for response in (Response(200, b"corrupt"), Response(404), Response(307)):
            with self.subTest(status=response.status_code):
                self.remote = OneLake()
                self.remote.failure = lambda method, path, params, headers: (
                    response if method == "GET" and path in self.remote.renamed else None)
                with self.assertRaises(publisher.PublishError):
                    self.publish()
                self.assertNotIn(self.index_path(), self.remote.files)

    def test_remote_size_limit_is_enforced(self):
        path = self.index_path().replace("bundle.json", "manifest.json")
        self.remote.files[path] = b"x" * (publisher.MAX_FILE_BYTES + 1)
        with self.assertRaisesRegex(publisher.PublishError, "16 MiB"):
            self.publish()
        self.assertNotIn(self.index_path(), self.remote.files)

    def test_failed_append_and_cleanup_leave_only_ignored_staging_file(self):
        self.remote.cleanup_failure = True
        self.remote.failure = lambda method, path, params, headers: (
            Response(500) if params.get("action") == "append" else None)
        with self.assertRaisesRegex(publisher.PublishError, "append failed"):
            self.publish()
        self.assertTrue(all(path.endswith(".tmp") for path in self.remote.files))
        self.remote.cleanup_failure = False
        self.remote.failure = None
        self.publish()
        self.assertIn(self.index_path(), self.remote.files)

    def test_directory_conflicts_redirects_and_http_errors_fail_closed(self):
        for status, code in ((409, None), (409, "AuthorizationFailure"), (403, None), (307, None)):
            with self.subTest(status=status, code=code):
                self.remote = OneLake()
                self.remote.failure = lambda *args: Response(status, SECRET.encode(), code)
                with self.assertRaises(publisher.PublishError) as raised:
                    self.publish()
                self.assertNotIn(SECRET, str(raised.exception))
                self.assertEqual(len(self.remote.calls), 1)
                self.assertFalse(self.remote.files)

    def test_malformed_indices_rejected_before_authentication_or_cloud(self):
        variants = []
        for key, value in (("schema_version", "wrong"), ("run_id", "../escape"),
                           ("execution_id", "../escape"), ("execution_id", ""), ("files", [])):
            variants.append(dict(self.index, **{key: value}))
        for files in ({}, {**self.index["files"], "../escape": {}},
                      {**self.index["files"], "bundle.json": {}},
                      {**self.index["files"], "manifest.json": {"sha256": "0" * 64, "size_bytes": 1}},
                      {**self.index["files"], "manifest.json": {"sha256": "0" * 64, "size_bytes": True}}):
            variants.append(dict(self.index, files=files))
        for index in variants:
            with self.subTest(index=index):
                self.write_index(index)
                with patch.object(publisher, "_access_token") as token:
                    with self.assertRaises(publisher.PublishError):
                        publisher.publish_bundle(self.directory, WORKSPACE, LAKEHOUSE, session=self.remote)
                    token.assert_not_called()
        self.assertFalse(self.remote.calls)

    def test_noncanonical_or_corrupt_index_rejected(self):
        for content in (b"invalid json", b"\xff", json.dumps(self.index).encode(), b"[]",
                        self.original["bundle.json"].replace(b'"schema_version":', b'"run_id": "duplicate", "schema_version":')):
            (self.directory / "bundle.json").write_bytes(content)
            with self.assertRaises(publisher.PublishError):
                self.publish()
        self.assertFalse(self.remote.calls)

    def test_extra_missing_symlink_directory_and_modified_payload_rejected(self):
        manifest = self.directory / "manifest.json"
        extra = self.directory / "extra.json"
        extra.write_bytes(b"{}")
        with self.assertRaises(publisher.PublishError):
            self.publish()
        extra.unlink()
        manifest.unlink()
        with self.assertRaises(publisher.PublishError):
            self.publish()
        manifest.symlink_to(self.directory / "summary.json")
        with self.assertRaises(publisher.PublishError):
            self.publish()
        manifest.unlink()
        manifest.mkdir()
        with self.assertRaises(publisher.PublishError):
            self.publish()
        manifest.rmdir()
        manifest.write_bytes(b"{}")
        with self.assertRaises(publisher.PublishError):
            self.publish()
        self.assertFalse(self.remote.calls)

    def test_symlink_bundle_and_parent_rejected(self):
        link = Path(self.temporary.name) / "linked"
        link.symlink_to(self.directory, target_is_directory=True)
        parent_link = Path(self.temporary.name) / "parent"
        parent_link.symlink_to(self.temporary.name, target_is_directory=True)
        for path in (link, parent_link / "bundle"):
            with self.assertRaisesRegex(publisher.PublishError, "symlink"):
                publisher.publish_bundle(path, WORKSPACE, LAKEHOUSE, session=self.remote, token=SECRET)
        self.assertFalse(self.remote.calls)

    def test_local_file_size_limit_and_nonregular_file(self):
        path = self.directory / "telemetry.json"
        with path.open("wb") as stream:
            stream.truncate(publisher.MAX_FILE_BYTES + 1)
        with self.assertRaisesRegex(publisher.PublishError, "16 MiB"):
            self.publish()
        path.unlink()
        os.mkfifo(path)
        with self.assertRaisesRegex(publisher.PublishError, "regular files"):
            self.publish()
        self.assertFalse(self.remote.calls)

    def test_invalid_destination_and_token_rejected(self):
        for workspace, lakehouse in (("../escape", LAKEHOUSE), (WORKSPACE, "https://evil.example")):
            with self.assertRaises(publisher.PublishError):
                publisher.publish_bundle(self.directory, workspace, lakehouse, session=self.remote, token=SECRET)
        for token in ("", "secret\r\nInjected: header"):
            with self.assertRaises(publisher.PublishError):
                publisher.publish_bundle(self.directory, WORKSPACE, LAKEHOUSE, session=self.remote, token=token)
        self.assertFalse(self.remote.calls)

    def test_cli_token_is_captured_privately_and_output_contains_only_result(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(publisher.requests, "Session", return_value=self.remote), \
                patch.object(self.remote, "close", create=True) as close, \
                patch.object(publisher.subprocess, "run", return_value=Mock(stdout=SECRET + "\n")) as run, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(publisher.main(["--workspace-id", WORKSPACE, "--lakehouse-id", LAKEHOUSE,
                                             "--bundle-directory", str(self.directory)]), 0)
        arguments, options = run.call_args
        self.assertEqual(arguments[0], ["az", "account", "get-access-token", "--resource",
                                        "https://storage.azure.com/", "--query", "accessToken", "--output", "tsv"])
        self.assertTrue(options["capture_output"])
        self.assertTrue(options["check"])
        self.assertEqual(options["timeout"], 60)
        close.assert_called_once()
        self.assertEqual(json.loads(output.getvalue())["run_id"], RUN_ID)
        self.assertNotIn(SECRET, output.getvalue() + errors.getvalue())

    def test_token_and_transport_errors_never_expose_secrets(self):
        for error in (subprocess.CalledProcessError(1, "az", output=SECRET, stderr=SECRET),
                      subprocess.TimeoutExpired("az", 60, output=SECRET), OSError(SECRET)):
            with patch.object(publisher.subprocess, "run", side_effect=error):
                with self.assertRaises(publisher.PublishError) as raised:
                    publisher._access_token()
                self.assertNotIn(SECRET, str(raised.exception))
                self.assertTrue(raised.exception.__suppress_context__)
        with patch.object(self.remote, "request", side_effect=requests.ConnectionError(SECRET)):
            with self.assertRaises(publisher.PublishError) as raised:
                self.publish()
            self.assertNotIn(SECRET, str(raised.exception))
            self.assertTrue(raised.exception.__suppress_context__)


if __name__ == "__main__":
    unittest.main()