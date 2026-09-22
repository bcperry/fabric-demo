import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "fabric-demos/04-real-time-ingestion/scripts/rehearse_live_test.py"
SPEC = importlib.util.spec_from_file_location("rehearse_live_test", SCRIPT)
rehearsal = importlib.util.module_from_spec(SPEC)
with patch.object(sys, "path", [str(SCRIPT.parent), *sys.path]):
    SPEC.loader.exec_module(rehearsal)
RUN_ID = "454be496-3c5e-4c6c-a836-234d61d49cb0"
TIME = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)


class RehearsalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.output = self.directory / "run"
        clock = patch.object(rehearsal, "datetime", wraps=datetime)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.clock.now.return_value = TIME

    def run_local(self, **kwargs):
        return rehearsal.rehearse(self.output, run_id=RUN_ID, seed=42, **kwargs)

    def write_catalog(self, mutate):
        catalog = rehearsal.live_test_contracts.load_catalog(rehearsal.DEFAULT_CATALOG)
        mutate(catalog)
        path = self.directory / "catalog.json"
        path.write_text(json.dumps(catalog), encoding="utf-8")
        return path

    def read_json(self, name):
        return json.loads((self.output / name).read_bytes())

    def test_actual_producer_completes_and_preserves_identity_and_pins(self):
        with patch.object(rehearsal.subprocess, "run", wraps=subprocess.run) as launch:
            result = self.run_local(requester="local:test")
        self.assertEqual(result, {"run_id": RUN_ID, "evidence_state": "COMPLETE", "source": "local"})
        launch.assert_called_once()
        command = launch.call_args.args[0]
        for flag, value in (("--run-id", RUN_ID), ("--seed", "42"), ("--duration", "1"),
                            ("--tspi-hz", "20"), ("--temperature-hz", "2"), ("--error-hz", "1"),
                            ("--transport", "stdout")):
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn("--fast", command)
        self.assertEqual(command[1], str(rehearsal.PRODUCER))
        self.assertFalse(any(name.startswith(("AZURE", "KAFKA")) for name in launch.call_args.kwargs["env"]))
        request = self.read_json("request-manifest.json")
        rehearsal.live_test_contracts.validate_run_manifest(request)
        self.assertEqual(request["schema_version"], "live-test-run.v1")
        self.assertEqual(request["state"], "REQUESTED")
        self.assertEqual(request["requester_kind"], "LOCAL_DECLARED")
        self.assertFalse(request["deployable"])
        self.assertEqual(request["parameters"], self.read_json("input.json"))
        self.assertEqual(request["input"]["sha256"], hashlib.sha256((self.output / "input.json").read_bytes()).hexdigest())
        self.assertEqual(request["provenance"]["source"]["sha256"], request["input"]["sha256"])
        self.assertEqual(request["assets"][0]["digest_kind"], "SYNTHETIC_PLACEHOLDER")
        self.assertEqual(request["assets"][0]["image_digest"], "sha256:" + "1" * 64)
        events = [json.loads(line)["event"] for line in (self.output / "stdout.jsonl").read_text().splitlines()]
        logs = [json.loads(line) for line in (self.output / "stderr.jsonl").read_text().splitlines()]
        self.assertEqual(len(events), 23)
        self.assertEqual([event["sequence_number"] for event in events], list(range(1, 24)))
        self.assertTrue(all(event["run_id"] == RUN_ID and event["startup_seed"] == 42 for event in events))
        self.assertTrue(all(event["schema_version"] == "target-vehicle.v1" for event in events))
        self.assertEqual([log["kind"] for log in logs], ["started", "completed"])
        self.assertTrue(all(log["run_id"] == RUN_ID and log["seed"] == 42 for log in logs))
        self.assertEqual(logs[-1]["emitted_counts"], {"tspi": 20, "temperature": 2, "error": 1})
        summary = self.read_json("evidence/summary.json")
        self.assertEqual(summary["sequence"]["missing"], 0)
        self.assertEqual(summary["counts"]["telemetry_records"], 23)
        self.assertEqual(summary["counts"]["diagnostic_records"], 2)
        execution = self.read_json("local-execution.json")
        self.assertEqual(execution["execution_id"], f"local-run-{RUN_ID}")
        self.assertEqual(summary["execution"]["execution_id"], execution["execution_id"])
        self.assertEqual(execution["request_id"], request["request_id"])
        self.assertEqual(execution["source"], "local")
        self.assertEqual(execution["returncode"], 0)
        self.assertEqual(execution["producer"]["sha256"], hashlib.sha256(rehearsal.PRODUCER.read_bytes()).hexdigest())
        self.assertEqual(execution["producer"]["digest_kind"], "LOCAL_SOURCE_SHA256")
        self.assertEqual(execution["image_digest_kind"], "SYNTHETIC_PLACEHOLDER")
        self.assertFalse(execution["image_resolved"])
        self.assertFalse(execution["telemetry_delivery_verified"])
        bundle = self.read_json("bundle.json")
        self.assertEqual(bundle["execution_id"], execution["execution_id"])
        self.assertEqual(bundle["run_id"], RUN_ID)
        expected_files = {path.relative_to(self.output).as_posix() for path in self.output.rglob("*")
                          if path.is_file() and path != self.output / "bundle.json"}
        self.assertEqual(set(bundle["files"]), expected_files)
        for name, metadata in bundle["files"].items():
            content = (self.output / name).read_bytes()
            self.assertEqual(metadata, {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)})
        inner = self.read_json("evidence/bundle.json")
        for name, metadata in inner["files"].items():
            self.assertEqual(metadata, bundle["files"][f"evidence/{name}"])

    def test_bad_hash_fails_before_subprocess(self):
        def mutate(catalog):
            catalog["products"][0]["sha256"] = "0" * 64
            for field in ("source", "output"):
                catalog["provenance"][0][field]["sha256"] = "0" * 64
        catalog = self.write_catalog(mutate)
        with patch.object(rehearsal.subprocess, "run") as launch:
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                self.run_local(catalog=catalog)
        launch.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_mismatched_parameters_fail_before_subprocess(self):
        catalog = self.write_catalog(lambda record: record["presets"][0]["parameters"].update(tspi_hz=21))
        with patch.object(rehearsal.subprocess, "run") as launch:
            with self.assertRaisesRegex(ValueError, "parameters do not match"):
                self.run_local(catalog=catalog)
        launch.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_deployable_asset_rejected_before_subprocess(self):
        catalog = self.write_catalog(lambda record: record["assets"][0].update(deployable=True))
        with patch.object(rehearsal.subprocess, "run") as launch:
            with self.assertRaisesRegex(ValueError, "deployable:false"):
                self.run_local(catalog=catalog)
        launch.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_retry_never_launches_or_overwrites(self):
        self.run_local()
        original = {path: path.read_bytes() for path in self.output.rglob("*") if path.is_file()}
        with patch.object(rehearsal.subprocess, "run") as launch:
            with self.assertRaisesRegex(ValueError, "already exists"):
                self.run_local()
        launch.assert_not_called()
        self.assertEqual(original, {path: path.read_bytes() for path in self.output.rglob("*") if path.is_file()})

    def test_timeout_preserves_partial_bytes_without_bundle_and_rejects_retry(self):
        stdout = b'{"event":"secret-stdout",\xff'
        stderr = b'{"diagnostic":"secret-stderr",\xfe'
        timeout = subprocess.TimeoutExpired(["secret-command"], 1, output=stdout, stderr=stderr)
        with patch.object(rehearsal.subprocess, "run", side_effect=timeout) as launch:
            with self.assertRaises(RuntimeError) as failure:
                self.run_local()
        launch.assert_called_once()
        self.assertEqual(str(failure.exception), "Local producer timed out; captured evidence retained")
        self.assertTrue(failure.exception.__suppress_context__)
        self.assertIsNone(failure.exception.__cause__)
        self.assertEqual((self.output / "stdout.jsonl").read_bytes(), stdout)
        self.assertEqual((self.output / "stderr.jsonl").read_bytes(), stderr)
        self.assertEqual(self.read_json("request-manifest.json")["state"], "REQUESTED")
        self.assertEqual({path.name for path in self.output.iterdir()},
                         {"request-manifest.json", "input.json", "stdout.jsonl", "stderr.jsonl"})
        for name in ("stdout.jsonl", "stderr.jsonl"):
            self.assertEqual((self.output / name).stat().st_mode & 0o777, 0o600)
        original = {path: path.read_bytes() for path in self.output.rglob("*") if path.is_file()}
        with patch.object(rehearsal.subprocess, "run") as launch:
            with self.assertRaisesRegex(ValueError, "already exists"):
                self.run_local()
        launch.assert_not_called()
        self.assertEqual(original, {path: path.read_bytes() for path in self.output.rglob("*") if path.is_file()})

    def test_timeout_without_output_preserves_empty_streams(self):
        timeout = subprocess.TimeoutExpired(["secret-command"], 1)
        with patch.object(rehearsal.subprocess, "run", side_effect=timeout):
            with self.assertRaisesRegex(RuntimeError, "Local producer timed out"):
                self.run_local()
        self.assertEqual((self.output / "stdout.jsonl").read_bytes(), b"")
        self.assertEqual((self.output / "stderr.jsonl").read_bytes(), b"")
        self.assertFalse((self.output / "bundle.json").exists())
        self.assertFalse((self.output / "evidence").exists())
        self.assertFalse((self.output / "local-execution.json").exists())

    def test_cli_timeout_exits_nonzero_with_sanitized_failure(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        timeout = subprocess.TimeoutExpired(["secret-command"], 1,
                                            output=b"secret-stdout", stderr=b"secret-stderr")
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with patch.object(rehearsal.subprocess, "run", side_effect=timeout) as launch:
                with self.assertRaises(SystemExit) as failure:
                    rehearsal.main(["--output-directory", str(self.output), "--run-id", RUN_ID])
        launch.assert_called_once()
        self.assertEqual(failure.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(),
                         "Local rehearsal failed: check pinned input, parameters, freshness, and a new output directory.\n")
        self.assertEqual((self.output / "stdout.jsonl").read_bytes(), b"secret-stdout")
        self.assertEqual((self.output / "stderr.jsonl").read_bytes(), b"secret-stderr")
        self.assertFalse((self.output / "bundle.json").exists())
        self.assertFalse((self.output / "evidence").exists())
        self.assertFalse((self.output / "local-execution.json").exists())

    def test_existing_empty_directory_and_symlink_are_rejected(self):
        self.output.mkdir()
        for path in (self.output, self.directory / "link"):
            if path != self.output:
                path.symlink_to(self.directory / "missing", target_is_directory=True)
            with self.subTest(path=path), patch.object(rehearsal.subprocess, "run") as launch:
                with self.assertRaisesRegex(ValueError, "already exists"):
                    rehearsal.rehearse(path)
                launch.assert_not_called()

    def test_cli_prints_only_sanitized_local_summary(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.dict(os.environ, {"KAFKA_TOPIC": "secret-value"}):
            status = rehearsal.main(["--output-directory", str(self.output), "--run-id", RUN_ID,
                                     "--seed", "42", "--requester", "local:test"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue()),
                         {"run_id": RUN_ID, "evidence_state": "COMPLETE", "source": "local"})
        self.assertNotIn("secret-value", (self.output / "stdout.jsonl").read_text())


if __name__ == "__main__":
    unittest.main()