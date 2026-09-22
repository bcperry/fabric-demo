import importlib.util
import contextlib
import copy
import hashlib
import io
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "fabric-demos/04-real-time-ingestion/scripts/collect_live_test.py"
SPEC = importlib.util.spec_from_file_location("collect_live_test", SCRIPT)
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)
RUN_ID = "36adf728-d3b8-44ac-97e2-e3823d453b11"
OTHER_RUN = "6ad51217-7918-4b73-b6e8-8aba26d5a112"
TIME = "2026-09-18T12:00:00Z"
ROOT = SCRIPT.parents[3]
PRODUCER_SPEC = importlib.util.spec_from_file_location(
    "collection_producer", ROOT / "shared/integrated-test-data/02-emulators/src/mda_emulators/target_vehicle.py")
producer = importlib.util.module_from_spec(PRODUCER_SPEC)
PRODUCER_SPEC.loader.exec_module(producer)
CONTRACT_SPEC = importlib.util.spec_from_file_location("collection_contracts", SCRIPT.with_name("live_test_contracts.py"))
contracts = importlib.util.module_from_spec(CONTRACT_SPEC)
CONTRACT_SPEC.loader.exec_module(contracts)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "schema_version": "live-test-run.v1", "run_id": RUN_ID, "request_id": OTHER_RUN,
            "preset_id": "short", "requester": "local", "seed": 17, "created_at": TIME,
            "assets": ["target-01"], "input": {},
            "parameters": {"duration_seconds": 1, "tspi_hz": 2, "temperature_hz": 1, "error_hz": 1},
            "executions": [{"execution_id": "job-01", "status": "Succeeded"}],
            "telemetry": [], "logs": [], "outputs": [], "state": "REQUESTED", "evidence_state": "NOT_COLLECTED",
        }
        self.execution = {"execution_id": "job-01", "status": "Succeeded"}
        self.events = [event for _, event in producer.TargetVehicle(17, 1).events(
            datetime(2026, 9, 18, 12, tzinfo=timezone.utc), RUN_ID, "target-01",
            {"tspi": 2, "temperature": 1, "error": 1})]
        common = {"schema_version": "live-test-diagnostic.v1", "run_id": RUN_ID,
                  "vehicle_id": "target-01", "seed": 17, "event_time_utc": TIME}
        self.logs = [dict(common, kind="started", duration_seconds=1,
                          rates={"tspi": 2, "temperature": 1, "error": 1}),
                     dict(common, kind="completed", emitted_counts={"tspi": 2, "temperature": 1, "error": 1})]

    def collect(self, events=None, logs=None):
        return collector.collect_evidence(self.manifest, self.events if events is None else events,
                                          self.logs if logs is None else logs, self.execution)

    def test_successful_execution_without_evidence_is_incomplete(self):
        summary = self.collect([], [])
        self.assertEqual(summary["execution"]["status"], "SUCCEEDED")
        self.assertEqual(summary["evidence_state"], "INCOMPLETE")
        self.assertEqual(summary["collection_state"], "COLLECTING")
        self.assertEqual(summary["channels"]["tspi"]["missing"], 2)

    def test_complete_evidence_is_independent_of_execution_status(self):
        self.execution["status"] = "Failed"
        summary = self.collect()
        self.assertEqual(summary["evidence_state"], "COMPLETE")
        self.assertEqual(summary["execution"]["status"], "FAILED")
        self.assertFalse(summary["provenance"]["telemetry_delivery_verified"])

    def test_duplicate_and_unrelated_events_do_not_fill_missing_samples(self):
        events = self.events[:-1] + [self.events[0], dict(self.events[-1], run_id=OTHER_RUN)]
        summary = self.collect(({"topic": "target", "key": "target-01", "event": event} for event in events))
        self.assertEqual(summary["channels"]["error"]["duplicates"], 1)
        self.assertEqual(summary["counts"]["unrelated_telemetry"], 1)
        self.assertEqual(summary["channels"]["tspi"]["missing"], 1)
        self.assertEqual(summary["evidence_state"], "INCOMPLETE")

    def test_execution_must_belong_to_manifest(self):
        self.execution["execution_id"] = "different-job"
        with self.assertRaisesRegex(ValueError, "not registered"):
            self.collect()

    def test_either_evidence_source_missing_prevents_completeness(self):
        for events, logs in (([], self.logs), (self.events, []), (self.events, self.logs[:1]),
                             (self.events, self.logs[1:])):
            with self.subTest(events=len(events), logs=len(logs)):
                self.assertEqual(self.collect(events, logs)["evidence_state"], "INCOMPLETE")

    def test_terminal_counts_are_not_receipts(self):
        summary = self.collect([], self.logs)
        self.assertEqual(summary["channels"]["tspi"]["received"], 0)
        self.assertEqual(summary["diagnostics"]["emitted_counts_meaning"], "attempted_enqueues")
        self.assertFalse(summary["provenance"]["raw_stderr_retained"])

    def test_terminal_failures_and_mismatched_counts_are_incomplete(self):
        for kind in ("failed", "canceled"):
            with self.subTest(kind=kind):
                logs = [self.logs[0], dict(self.logs[1], kind=kind)]
                self.assertEqual(self.collect(logs=logs)["evidence_state"], "INCOMPLETE")
        self.logs[1]["emitted_counts"]["tspi"] = 1
        self.assertEqual(self.collect()["evidence_state"], "INCOMPLETE")

    def test_invalid_sequences_ids_and_channels_are_not_counted(self):
        for changes in ({"sequence_number": 0}, {"sequence_number": True}, {"sequence_number": 5},
                        {"sequence_number": 3}, {"event_id": "arbitrary"}, {"channel": "other"},
                        {"startup_seed": 18}, {"event_time_utc": "not a timestamp"},
                        {"execution_id": "other-job"}):
            with self.subTest(changes=changes):
                events = self.events[:-1] + [dict(self.events[-1], **changes)]
                summary = self.collect(events)
                self.assertEqual(summary["counts"]["invalid_telemetry"], 1)
                self.assertEqual(summary["sequence"]["missing"], 1)
                self.assertEqual(summary["evidence_state"], "INCOMPLETE")

    def test_conflicting_identity_is_order_independent_and_excluded(self):
        events = self.events + [dict(self.events[-1], channel="error", data={"error_word": 0})]
        forward = self.collect(events)
        backward = self.collect(reversed(events))
        self.assertEqual(forward, backward)
        self.assertEqual(forward["counts"]["conflicting_events"], 1)
        self.assertEqual(forward["channels"]["tspi"]["received"], 1)
        self.assertEqual(forward["evidence_state"], "INCOMPLETE")

    def test_changed_measurement_conflicts_without_retaining_payload(self):
        changed = copy.deepcopy(self.events[-1])
        changed["data"]["altitude_m"] += 1
        events = self.events + [changed]
        forward = self.collect(events)
        self.assertEqual(forward, self.collect(reversed(events)))
        self.assertEqual(forward["counts"]["conflicting_events"], 1)
        self.assertEqual(forward["channels"]["tspi"]["duplicates"], 0)
        self.assertEqual(forward["channels"]["tspi"]["received"], 1)
        self.assertEqual(forward["sequence"]["missing"], 1)
        self.assertEqual(forward["evidence_state"], "INCOMPLETE")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "bundle"
            collector.write_bundle(self.manifest, events, self.logs, self.execution, directory)
            retained = json.loads((directory / "telemetry.json").read_bytes())
            self.assertEqual(len(retained), 5)
            for event in retained:
                self.assertNotIn("data", event)
                self.assertEqual(event["measurement_status"], "FINITE_SYNTHETIC_SHAPE")
            hashes = {event["measurement_sha256"] for event in retained if event["event_id"] == changed["event_id"]}
            self.assertEqual(len(hashes), 2)
            self.assertNotIn(b"altitude_m", (directory / "telemetry.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                collector.write_bundle(self.manifest, self.events, self.logs, self.execution, directory)

    def test_measurement_hash_is_canonical_and_ignores_unretained_metadata(self):
        reordered = dict(self.events[-1], data=dict(reversed(list(self.events[-1]["data"].items()))),
                         arbitrary="not-retained")
        summary = self.collect(self.events + [reordered])
        self.assertEqual(summary["channels"]["tspi"]["duplicates"], 1)
        self.assertEqual(summary["counts"]["conflicting_events"], 0)
        self.assertEqual(summary["evidence_state"], "COMPLETE")
        canonical = json.dumps(self.events[-1]["data"], sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("utf-8")
        self.assertEqual(collector._measurement_hash(reordered), hashlib.sha256(canonical).hexdigest())

    def test_invalid_measurement_shapes_and_non_synthetic_events_are_rejected(self):
        for changes in ({"data": None}, {"data": []}, {"data": {}}, {"data": {"password": "private"}},
                        {"synthetic": False}, {"synthetic": 1}, {"synthetic": None},
                        *({"data": dict(self.events[-1]["data"], altitude_m=value)} for value in
                          (float("nan"), float("inf"), -float("inf"), True, "2", None, [], {}, 10 ** 1000))):
            with self.subTest(changes=changes):
                summary = self.collect(self.events[:-1] + [dict(self.events[-1], **changes)])
                self.assertEqual(summary["counts"]["invalid_telemetry"], 1)
                self.assertEqual(summary["evidence_state"], "INCOMPLETE")
        missing_synthetic = dict(self.events[-1])
        del missing_synthetic["synthetic"]
        self.assertEqual(self.collect(self.events[:-1] + [missing_synthetic])["counts"]["invalid_telemetry"], 1)
        for value in (-1, 1.5, True):
            with self.subTest(error_word=value):
                events = [dict(self.events[0], data={"error_word": value}), *self.events[1:]]
                self.assertEqual(self.collect(events)["counts"]["invalid_telemetry"], 1)

    def test_legacy_events_have_unavailable_hashes_and_cannot_prove_completeness(self):
        events = [{key: value for key, value in event.items() if key not in ("data", "synthetic")}
                  for event in self.events]
        summary = self.collect(events)
        self.assertEqual(summary["evidence_state"], "INCOMPLETE")
        self.assertEqual(summary["counts"]["unavailable_measurements"], 4)
        self.assertEqual(summary["sequence"]["missing"], 0)
        clean = collector._event(events[0], RUN_ID, {"tspi": 2, "temperature": 1, "error": 1})
        self.assertIsNone(clean["measurement_sha256"])
        self.assertEqual(clean["measurement_status"], "UNAVAILABLE")
        self.assertEqual(self.collect(self.events + [events[0]])["counts"]["conflicting_events"], 1)

    def test_bad_diagnostics_and_foreign_runs_cannot_establish_completion(self):
        for changes in ({"run_id": OTHER_RUN}, {"seed": 18}, {"kind": "arbitrary"},
                        {"schema_version": "unknown"}, {"emitted_counts": {"tspi": True}},
                        {"execution_id": "other-job"}, {"vehicle_id": "target-02"},
                        {"event_time_utc": "2026-09-17T12:00:00Z"}):
            with self.subTest(changes=changes):
                logs = [self.logs[0], dict(self.logs[1], **changes)]
                self.assertEqual(self.collect(logs=logs)["evidence_state"], "INCOMPLETE")

    def test_duplicate_diagnostics_do_not_duplicate_terminal_records(self):
        summary = self.collect(logs=self.logs + self.logs)
        self.assertEqual(summary["evidence_state"], "COMPLETE")
        self.assertEqual(summary["counts"]["duplicate_diagnostics"], 2)
        self.assertEqual(summary["diagnostics"]["terminal"], 1)

    def test_fractional_duration_expected_count(self):
        self.manifest["parameters"]["duration_seconds"] = 1.25
        summary = self.collect([], [])
        self.assertEqual(summary["channels"]["tspi"]["expected"], 3)
        self.assertEqual(summary["channels"]["error"]["expected"], 2)

    def test_expected_counts_match_real_producer_float_boundary(self):
        path = SCRIPT.parents[3] / "shared/integrated-test-data/02-emulators/src/mda_emulators/target_vehicle.py"
        spec = importlib.util.spec_from_file_location("collection_target_vehicle_fixture", path)
        producer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(producer)
        self.manifest["seed"] = -17
        self.manifest["parameters"] = {"duration_seconds": 0.07, "tspi_hz": 100,
                                       "temperature_hz": 10, "error_hz": 1}
        rates = {"tspi": 100, "temperature": 10, "error": 1}
        events = [event for _, event in producer.TargetVehicle(-17, 0.07).events(
            datetime(2026, 9, 18, tzinfo=timezone.utc), RUN_ID, "target-01", rates)]
        observed = Counter(event["channel"] for event in events)
        self.logs[0].update(seed=-17, duration_seconds=0.07, rates=rates)
        self.logs[1].update(seed=-17, emitted_counts=dict(observed))
        summary = self.collect(events)
        self.assertEqual(summary["channels"]["tspi"]["expected"], observed["tspi"])
        self.assertEqual(summary["evidence_state"], "COMPLETE")

    def test_invalid_manifest_parameters_fail_closed(self):
        for value in (0, -1, float("nan"), float("inf"), True, "2", 10 ** 1000, 1e308):
            with self.subTest(value=value):
                self.manifest["parameters"]["tspi_hz"] = value
                with self.assertRaises(ValueError):
                    self.collect()

    def test_expected_counts_are_bounded_and_overflow_fails_closed(self):
        self.assertEqual(collector._expected_count(3600, 100), collector.MAX_EXPECTED_PER_CHANNEL)
        for duration, rate in ((3600.01, 100), (1e308, 1e308), (10 ** 1000, 1),
                               (1, 10 ** 1000), (1e-300, 1e-300), (True, 1), (1, "2")):
            with self.subTest(duration=duration, rate=rate), self.assertRaises(ValueError):
                collector._expected_count(duration, rate)

    def test_execution_run_mismatch_and_duplicate_membership_are_rejected(self):
        self.execution["run_id"] = OTHER_RUN
        with self.assertRaises(ValueError):
            self.collect()
        del self.execution["run_id"]
        self.manifest["executions"].append(dict(self.execution))
        with self.assertRaises(ValueError):
            self.collect()

    def test_unknown_status_is_not_copied(self):
        self.execution["status"] = "exception with credentials"
        self.assertEqual(self.collect()["execution"]["status"], "UNKNOWN")

    def test_bundle_is_deterministic_idempotent_hashed_and_sanitized(self):
        original = copy.deepcopy(self.manifest)
        sentinel = "Bearer DO-NOT-RETAIN?sig=private"
        self.manifest["input"] = {"password": sentinel}
        self.manifest["logs"] = [{"url": sentinel}]
        self.manifest["assets"] = [{"vehicle_id": "target-01", "secret": sentinel}]
        self.manifest["requester"] = sentinel
        self.execution["exception"] = sentinel
        for log in self.logs:
            log.update(exception={"message": sentinel}, stderr=sentinel, authorization=sentinel)
        for event in self.events:
            event["authorization"] = sentinel
        snapshot = copy.deepcopy((self.manifest, self.events, self.logs, self.execution))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "bundle"
            result = collector.write_bundle(self.manifest, iter(self.events), iter(self.logs), self.execution, directory)
            self.assertEqual(result, directory)
            before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in directory.iterdir()}
            collector.write_bundle(self.manifest, reversed(self.events), reversed(self.logs), self.execution, directory)
            after = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in directory.iterdir()}
            self.assertEqual(before, after)
            second = Path(temporary) / "another-revision"
            collector.write_bundle(self.manifest, self.events, self.logs, self.execution, second)
            self.assertEqual({path.name: path.read_bytes() for path in second.iterdir()},
                             {name: content for name, (content, _) in before.items()})
            self.assertEqual(set(before), {"manifest.json", "summary.json", "telemetry.json", "diagnostics.json", "bundle.json"})
            for content, _ in before.values():
                self.assertNotIn(sentinel.encode(), content)
            index = json.loads(before["bundle.json"][0])
            for name, metadata in index["files"].items():
                self.assertEqual(metadata, {"sha256": hashlib.sha256(before[name][0]).hexdigest(),
                                            "size_bytes": len(before[name][0])})
                self.assertEqual((directory / name).stat().st_mode & 0o777, 0o600)
            retained = json.loads(before["manifest.json"][0])
            self.assertEqual(retained["state"], original["state"])
            self.assertEqual(retained["input"], dict.fromkeys(collector.INPUT_PINS))
            self.assertIn("input.sha256", retained["projection"]["unavailable_pins"])
            self.assertIsNone(retained["deployable"])
            self.assertIsNone(retained["requester_kind"])
            self.assertEqual(retained["requester"], "REDACTED")
            self.assertEqual(retained["evidence_state"], "COLLECTED")
        self.assertEqual(snapshot, (self.manifest, self.events, self.logs, self.execution))

    def contract_manifest(self):
        catalog = contracts.load_catalog(ROOT / "shared/integrated-test-data/01-contracts/examples/live-test-catalog.json")
        return contracts.create_run_manifest(catalog, "normal-collection", run_id=RUN_ID, requester="local",
                                             seed=17, created_at=TIME)

    def test_real_contract_projection_preserves_exact_pins_under_distinct_schema(self):
        manifest = self.contract_manifest()
        contracts.validate_run_manifest(manifest)
        original = copy.deepcopy(manifest)
        summary = self.collect()
        sentinel = "private-metadata-must-not-leak"
        for record in (manifest, manifest["input"], *manifest["assets"]):
            record["owner"] = sentinel
            record["extra"] = {"secret": sentinel}
        projected = collector._manifest_projection(manifest, summary)
        self.assertEqual(projected["schema_version"], "live-test-collector-manifest.v1")
        self.assertEqual(projected["input"], {key: original["input"][key] for key in collector.INPUT_PINS})
        self.assertEqual(projected["assets"], [{key: asset[key] for key in collector.ASSET_PINS}
                                              for asset in original["assets"]])
        for key in ("catalog_id", "requester_kind", "deployable", "synthetic"):
            self.assertEqual(projected[key], original[key])
        self.assertEqual(projected["requester_kind"], "LOCAL_DECLARED")
        self.assertIs(projected["deployable"], False)
        self.assertEqual(projected["projection"], {"scope": "whitelisted_subset", "contract_validation": "not_performed",
                                                 "pin_validation": "shape_only", "unavailable_pins": []})
        self.assertNotIn(sentinel, json.dumps(projected))
        self.assertNotIn("preset", projected)
        self.assertNotIn("provenance", projected)
        self.assertEqual(projected["state"], "REQUESTED")
        self.assertEqual(projected["evidence_state"], "COLLECTED")
        self.assertEqual(summary["evidence_state"], "COMPLETE")
        self.assertEqual(collector._manifest_projection(manifest, self.collect([], []))["evidence_state"], "COLLECTING")
        with self.assertRaises(ValueError):
            contracts.validate_run_manifest(projected)

    def test_invalid_present_pins_are_rejected_not_redacted_or_fabricated(self):
        original = self.contract_manifest()
        for section, field, value in (
            ("root", "catalog_id", {}), ("root", "requester_kind", "AUTHENTICATED"),
            ("root", "deployable", True), ("root", "deployable", 0), ("root", "synthetic", 1),
            ("input", "product_id", []), ("input", "version", "latest"), ("input", "version", "01.0.0"),
            ("input", "sha256", "a" * 63), ("input", "sha256", None),
            ("input", "uri", "https://example.test/?sig=private"), ("input", "uri", "repo://../private"),
            ("input", "uri", "repo://folder//file"), ("input", "contract_version", {}),
            ("asset", "asset_id", "bad/id"), ("asset", "version", "1.0"),
            ("asset", "image_digest", "sha256:" + "G" * 64), ("asset", "digest_kind", "PUBLISHED"),
            ("asset", "deployable", True), ("asset", "input_contract", "unknown.v1"),
            ("asset", "output_contract", ["live-test-events.v1"]),
        ):
            with self.subTest(section=section, field=field, value=value):
                manifest = copy.deepcopy(original)
                record = manifest if section == "root" else manifest["input"] if section == "input" else manifest["assets"][0]
                record[field] = value
                with self.assertRaises(ValueError):
                    collector._manifest_projection(manifest, self.collect())
        for field, value in (("input", []), ("input", None), ("assets", {}), ("assets", [None])):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                collector._manifest_projection(dict(original, **{field: value}), self.collect())

    def test_conflicting_bundle_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "bundle"
            collector.write_bundle(self.manifest, self.events, self.logs, self.execution, directory)
            original = (directory / "summary.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "revision"):
                collector.write_bundle(self.manifest, [], [], self.execution, directory)
            self.assertEqual((directory / "summary.json").read_bytes(), original)

    def test_partial_write_failure_never_publishes_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "bundle"
            with patch.object(collector.os, "fsync", side_effect=OSError("fixture failure")):
                with self.assertRaises(OSError):
                    collector.write_bundle(self.manifest, self.events, self.logs, self.execution, directory)
            self.assertFalse(directory.exists())
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_competing_identical_writers_converge(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "bundle"
            barrier = threading.Barrier(2)
            rename = collector.os.rename

            def synchronized_rename(source, destination):
                barrier.wait(timeout=5)
                return rename(source, destination)

            with patch.object(collector.os, "rename", side_effect=synchronized_rename), ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(collector.write_bundle, self.manifest, self.events, self.logs,
                                       self.execution, directory) for _ in range(2)]
                self.assertEqual([future.result(timeout=10) for future in futures], [directory, directory])
            self.assertEqual(list(Path(temporary).iterdir()), [directory])
            self.assertEqual(json.loads((directory / "summary.json").read_text())["evidence_state"], "COMPLETE")

    def test_tampered_bundle_and_symlink_destination_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "bundle"
            collector.write_bundle(self.manifest, self.events, self.logs, self.execution, directory)
            alias = Path(temporary) / "alias"
            alias.symlink_to(directory, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                collector.write_bundle(self.manifest, self.events, self.logs, self.execution, alias)
            (directory / "summary.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                collector.write_bundle(self.manifest, self.events, self.logs, self.execution, directory)
            self.assertEqual((directory / "summary.json").read_text(), "{}")

    def test_cli_jsonl_and_json_array_inputs_and_safe_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "manifest.json").write_text(json.dumps(self.manifest))
            (root / "execution.json").write_text(json.dumps(self.execution))
            (root / "telemetry.jsonl").write_text("\n".join(json.dumps(event) for event in self.events))
            (root / "diagnostics.json").write_text(json.dumps(self.logs))
            args = ["--manifest", str(root / "manifest.json"), "--execution", str(root / "execution.json"),
                    "--telemetry", str(root / "telemetry.jsonl"), "--diagnostics", str(root / "diagnostics.json"),
                    "--output-directory", str(root / "bundle")]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(collector.main(args), 0)
            self.assertEqual(json.loads((root / "bundle/summary.json").read_text())["evidence_state"], "COMPLETE")
            (root / "telemetry.jsonl").write_text("raw secret exception")
            error = io.StringIO()
            with contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as raised:
                collector.main(args)
            self.assertEqual(raised.exception.code, 2)
            self.assertNotIn("raw secret exception", error.getvalue())


if __name__ == "__main__":
    unittest.main()