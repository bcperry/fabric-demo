import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "live_test_contracts", ROOT / "fabric-demos/04-real-time-ingestion/scripts/live_test_contracts.py"
)
contracts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contracts)
CATALOG_PATH = ROOT / "shared/integrated-test-data/01-contracts/examples/live-test-catalog.json"
RUN_ID = "454be496-3c5e-4c6c-a836-234d61d49cb0"
CREATED_AT = "2026-09-18T01:00:00Z"


def asset_record():
    return {
        "schema_version": "live-test-asset.v1",
        "asset_id": "synthetic-producer", "version": "1.0.0",
        "owner": "local-fixture-owner", "steward": "local-fixture-steward",
        "publisher": "local-fixture-publisher", "description": "Non-deployable test descriptor",
        "permitted_use": "LOCAL_CONTRACT_TEST_ONLY", "classification": "SYNTHETIC_UNCLASS",
        "synthetic": True, "deployable": False,
        "image_digest": "sha256:" + "1" * 64, "digest_kind": "SYNTHETIC_PLACEHOLDER",
        "input_contract": "synthetic-scenario.v1", "output_contract": "live-test-events.v1",
        "parameter_bounds": {name: {"min": limits[0], "max": limits[1]}
                             for name, limits in contracts.PARAMETER_LIMITS.items()},
        "runtime": {"cpu_cores": 1, "memory_mb": 512, "timeout_seconds": 3600},
        "publication_status": "LOCAL_ONLY",
    }


class AssetContractTests(unittest.TestCase):
    def test_valid_local_asset(self):
        self.assertIsNone(contracts.validate_asset_version(asset_record()))

    def test_invalid_asset_fields(self):
        for field, value in (
            ("schema_version", "live-test-asset.v2"), ("owner", " "),
            ("version", "latest"), ("image_digest", "image:latest"),
            ("deployable", True), ("synthetic", False), ("input_contract", "unknown.v1"),
        ):
            with self.subTest(field=field):
                asset = asset_record()
                asset[field] = value
                with self.assertRaises(ValueError):
                    contracts.validate_asset_version(asset)

    def test_unknown_and_missing_fields(self):
        for field in ("owner", "steward", "version"):
            asset = asset_record()
            del asset[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                contracts.validate_asset_version(asset)
        asset = asset_record()
        asset["approved"] = True
        with self.assertRaises(ValueError):
            contracts.validate_asset_version(asset)

    def test_nonfinite_boolean_and_reversed_bounds(self):
        for value in (float("nan"), float("inf"), -1, True, 101, 10 ** 1000):
            asset = asset_record()
            asset["parameter_bounds"]["tspi_hz"]["max"] = value
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                contracts.validate_asset_version(asset)
        asset = asset_record()
        asset["parameter_bounds"]["tspi_hz"] = {"min": 2, "max": 1}
        with self.assertRaises(ValueError):
            contracts.validate_asset_version(asset)


class CatalogAndRunTests(unittest.TestCase):
    def setUp(self):
        self.catalog = contracts.load_catalog(CATALOG_PATH)

    def create(self, **overrides):
        arguments = dict(run_id=RUN_ID, requester="local:test-analyst", seed=42, created_at=CREATED_AT)
        arguments.update(overrides)
        return contracts.create_run_manifest(self.catalog, "normal-collection", **arguments)

    def test_fixture_source_hash_and_provenance(self):
        product = self.catalog["products"][0]
        source = ROOT / product["uri"].removeprefix("repo://")
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), product["sha256"])
        self.assertEqual(product["contract_version"], "live-test-input.v1")
        self.assertEqual(json.loads(source.read_text()), self.catalog["presets"][0]["parameters"])
        self.assertEqual(json.loads(source.read_text()),
                 {"duration_seconds": 1, "tspi_hz": 20, "temperature_hz": 2, "error_hz": 1})
        provenance = self.catalog["provenance"][0]
        self.assertEqual(provenance["output"]["sha256"], product["sha256"])
        self.assertEqual(provenance["source"]["sha256"], product["sha256"])

    def test_create_identity_linkage_and_initial_state(self):
        before = copy.deepcopy(self.catalog)
        manifest = self.create()
        self.assertIsNone(contracts.validate_run_manifest(manifest))
        self.assertEqual(self.catalog, before)
        self.assertEqual(manifest["run_id"], RUN_ID)
        self.assertEqual(str(UUID(manifest["request_id"])), manifest["request_id"])
        self.assertNotEqual(manifest["request_id"], self.create()["request_id"])
        self.assertEqual(manifest["requester"], "local:test-analyst")
        self.assertEqual(manifest["requester_kind"], "LOCAL_DECLARED")
        self.assertEqual(manifest["schema_version"], "live-test-run.v1")
        self.assertEqual(manifest["state"], "REQUESTED")
        self.assertEqual(manifest["evidence_state"], "NOT_COLLECTED")
        self.assertFalse(manifest["deployable"])
        self.assertTrue(manifest["synthetic"])
        self.assertEqual(manifest["input"], before["products"][0])
        self.assertEqual(manifest["assets"], before["assets"])
        self.assertEqual(manifest["provenance"], before["provenance"][0])
        for name in ("executions", "telemetry", "logs", "outputs", "collector_errors"):
            self.assertEqual(manifest[name], [])
        self.catalog["products"][0]["version"] = "2.0.0"
        self.catalog["assets"][0]["image_digest"] = "sha256:" + "2" * 64
        self.assertIsNone(contracts.validate_run_manifest(manifest))

    def test_roundtrip(self):
        manifest = self.create()
        restored = json.loads(json.dumps(manifest, allow_nan=False))
        self.assertEqual(restored, manifest)
        self.assertIsNone(contracts.validate_run_manifest(restored))

    def test_all_record_schema_versions_missing_owners_and_unknown_fields(self):
        for collection in ("assets", "products", "presets", "provenance"):
            for mutation in ("schema_version", "owner", "extra"):
                catalog = copy.deepcopy(self.catalog)
                record = catalog[collection][0]
                if mutation == "owner":
                    del record["owner"]
                else:
                    record[mutation] = "unsupported"
                with self.subTest(collection=collection, mutation=mutation), self.assertRaises(ValueError):
                    contracts.validate_catalog(catalog)
        for version in ("1.0.0", "live-test-catalog.v2", None):
            self.catalog["schema_version"] = version
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "schema_version"):
                contracts.validate_catalog(self.catalog)

    def test_catalog_cross_record_rejections(self):
        mutations = [
            ("products", "sha256", "bad"),
            ("products", "version", "latest"),
            ("products", "contract_version", "live-test-events.v1"),
            ("products", "review_state", "APPROVED"),
            ("products", "endorsement_state", "CERTIFIED"),
            ("products", "uri", "https://example.com/customer-data"),
            ("products", "received_at", "2026-09-17T00:00:00Z"),
            ("presets", "input", {"product_id": "live-test-input"}),
            ("presets", "input", {"product_id": "live-test-input", "version": "2.0.0"}),
            ("presets", "assets", [{"asset_id": "missing", "version": "1.0.0"}]),
            ("presets", "expected_outputs", ["live-test-output.v1"]),
            ("presets", "compatibility_rule", "IGNORE_VERSION"),
            ("provenance", "rule_version", "local-source-pin.v2"),
        ]
        for collection, field, value in mutations:
            catalog = copy.deepcopy(self.catalog)
            catalog[collection][0][field] = value
            with self.subTest(collection=collection, field=field), self.assertRaises(ValueError):
                contracts.validate_catalog(catalog)
        catalog = copy.deepcopy(self.catalog)
        catalog["provenance"][0]["output"]["sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            contracts.validate_catalog(catalog)

    def test_duplicate_and_empty_collections(self):
        for collection in ("assets", "products", "presets", "provenance"):
            for records in ([], self.catalog[collection] * 2):
                catalog = copy.deepcopy(self.catalog)
                catalog[collection] = records
                with self.subTest(collection=collection, empty=not records), self.assertRaises(ValueError):
                    contracts.validate_catalog(catalog)

    def test_parameter_bounds_and_values(self):
        for name in contracts.PARAMETER_LIMITS:
            for value in (False, 0, -1, float("inf"), float("nan"), "1", 4000):
                catalog = copy.deepcopy(self.catalog)
                catalog["presets"][0]["parameters"][name] = value
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    contracts.validate_catalog(catalog)
        self.catalog["assets"][0]["parameter_bounds"]["tspi_hz"]["max"] = 49
        with self.assertRaisesRegex(ValueError, "incompatible tspi_hz"):
            contracts.validate_catalog(self.catalog)

    def test_internal_rates_must_be_strictly_below_tspi(self):
        for channel in ("temperature_hz", "error_hz"):
            for rate in (2, 3):
                catalog = copy.deepcopy(self.catalog)
                catalog["presets"][0]["parameters"].update({"tspi_hz": 2, channel: rate})
                with self.subTest(channel=channel, rate=rate), self.assertRaisesRegex(ValueError, "internal channel rates"):
                    contracts.validate_catalog(catalog)
        manifest = self.create()
        manifest["parameters"]["temperature_hz"] = manifest["parameters"]["tspi_hz"] = 2
        with self.assertRaisesRegex(ValueError, "internal channel rates"):
            contracts.validate_run_manifest(manifest)

    def test_create_rejects_invalid_identity_seed_and_time(self):
        for field, value in (
            ("run_id", "not-a-uuid"), ("run_id", "00000000-0000-0000-0000-000000000000"),
            ("requester", " "), ("requester", {}), ("seed", True), ("seed", 1.5),
            ("seed", -1), ("seed", 2 ** 63), ("created_at", "2026-09-18T01:00:00"),
            ("created_at", "2026-09-18T01:00:00+01:00"), ("created_at", "2026-02-30T01:00:00Z"),
            ("created_at", "2026-09-17T01:00:00Z"), ("created_at", "2026-09-20T01:00:00Z"),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.create(**{field: value})
        manifest = self.create(created_at="2026-09-18T01:00:00.123456+00:00", seed=0)
        self.assertIsNone(contracts.validate_run_manifest(manifest))

    def test_unknown_preset(self):
        with self.assertRaisesRegex(ValueError, "preset_id"):
            contracts.create_run_manifest(self.catalog, "missing", run_id=RUN_ID,
                                          requester="local:test", seed=1, created_at=CREATED_AT)

    def test_manifest_mutations(self):
        mutations = [
            (("schema_version",), "live-test-run.v2"), (("request_id",), "bad"),
            (("preset_id",), "missing"), (("requester_kind",), "AUTHENTICATED"),
            (("deployable",), True), (("state",), "APPROVED"), (("evidence_state",), "APPROVED"),
            (("parameters", "tspi_hz"), 2), (("input", "version"), "2.0.0"),
            (("input", "sha256"), "f" * 64), (("assets", 0, "deployable"), True),
            (("assets", 0, "version"), "2.0.0"), (("assets", 0, "image_digest"), "tag:latest"),
            (("assets", 0, "input_contract"), "live-test-output.v1"),
            (("provenance", "output", "version"), "2.0.0"),
        ]
        for path, value in mutations:
            manifest = self.create()
            target = manifest
            for field in path[:-1]:
                target = target[field]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                contracts.validate_run_manifest(manifest)
        for field in ("request_id", "requester", "deployable", "provenance"):
            manifest = self.create()
            del manifest[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                contracts.validate_run_manifest(manifest)
        manifest = self.create()
        manifest["authorization"] = "approved"
        with self.assertRaises(ValueError):
            contracts.validate_run_manifest(manifest)

    def test_strict_json_loading(self):
        for content in ('{"schema_version":"live-test-catalog.v1","schema_version":"live-test-catalog.v1"}',
                        '{"value":NaN}', '{"value":Infinity}', '[]', '{'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "catalog.json"
                path.write_text(content, encoding="utf-8")
                with self.subTest(content=content), self.assertRaises(ValueError):
                    contracts.load_catalog(path)

    def completed_manifest(self):
        manifest = self.create()
        manifest["state"] = "SUCCEEDED"
        manifest["evidence_state"] = "COLLECTED"
        manifest["executions"] = [{"execution_id": "synthetic-execution-001", "status": "SUCCEEDED"}]
        linkage = {"run_id": manifest["run_id"], "request_id": manifest["request_id"],
                   "execution_id": manifest["executions"][0]["execution_id"]}
        manifest["telemetry"] = [{**linkage, "uri": "repo://synthetic-results/events.jsonl",
                                  "contract_version": "live-test-events.v1"}]
        manifest["logs"] = [{**linkage, "uri": f"repo://synthetic-results/{kind.lower()}.jsonl", "kind": kind}
                            for kind in ("STDOUT", "STDERR", "PLATFORM")]
        output = {"product_id": "synthetic-output", "version": "1.0.0",
                  "sha256": hashlib.sha256(b'{"synthetic":true,"samples":60}\n').hexdigest(),
                  "uri": "repo://synthetic-results/output.json"}
        provenance = copy.deepcopy(manifest["provenance"])
        provenance.update({
            "provenance_id": "synthetic-output-pin",
            "description": "Synthetic test-only output link; no retained artifact or cloud execution claim.",
            "source": {field: manifest["input"][field] for field in ("uri", "version", "sha256")},
            "output": copy.deepcopy(output), "recorded_at": "2026-09-18T01:01:00Z",
        })
        manifest["outputs"] = [{**linkage, **output, "provenance": provenance}]
        return manifest

    def test_lossless_catalog_run_execution_event_log_output_join(self):
        manifest = self.completed_manifest()
        self.assertIsNone(contracts.validate_run_manifest(manifest))
        restored = json.loads(json.dumps(manifest, allow_nan=False))
        self.assertEqual(restored, manifest)
        self.assertIsNone(contracts.validate_run_manifest(restored))
        synthetic_event = {"schema_version": "live-test-events.v1", "synthetic": True,
                           **{field: manifest["telemetry"][0][field]
                              for field in ("run_id", "request_id", "execution_id")}}
        self.assertEqual(synthetic_event["run_id"], RUN_ID)
        self.assertEqual(manifest["preset"]["input"]["version"], self.catalog["products"][0]["version"])
        self.assertEqual(manifest["assets"][0]["image_digest"], self.catalog["assets"][0]["image_digest"])
        for reference in manifest["telemetry"] + manifest["logs"] + manifest["outputs"]:
            for identity in ("run_id", "request_id", "execution_id"):
                self.assertEqual(reference[identity], synthetic_event[identity])
        provenance = manifest["outputs"][0]["provenance"]
        self.assertEqual(provenance["source"]["sha256"], manifest["input"]["sha256"])
        self.assertEqual(provenance["output"]["version"], manifest["outputs"][0]["version"])
        self.assertEqual(provenance["output"]["sha256"], manifest["outputs"][0]["sha256"])

    def test_broken_evidence_identity_links(self):
        for collection in ("telemetry", "logs", "outputs"):
            for field, value in (("run_id", "a-different-run"), ("request_id", "a-different-request"),
                                 ("execution_id", "unknown-execution"), ("uri", "repo://../escape")):
                manifest = self.completed_manifest()
                manifest[collection][0][field] = value
                with self.subTest(collection=collection, field=field), self.assertRaises(ValueError):
                    contracts.validate_run_manifest(manifest)
            manifest = self.completed_manifest()
            manifest[collection].append(copy.deepcopy(manifest[collection][0]))
            with self.subTest(duplicate=collection), self.assertRaises(ValueError):
                contracts.validate_run_manifest(manifest)

    def test_output_provenance_and_evidence_contract_rejections(self):
        for path, value in (
            (("outputs", 0, "version"), "latest"),
            (("outputs", 0, "sha256"), "0" * 64),
            (("outputs", 0, "provenance", "source", "sha256"), "0" * 64),
            (("outputs", 0, "provenance", "recorded_at"), "2026-09-18T00:00:00Z"),
            (("telemetry", 0, "contract_version"), "live-test-output.v1"),
            (("logs", 0, "kind"), "TELEMETRY"),
        ):
            manifest = self.completed_manifest()
            target = manifest
            for field in path[:-1]:
                target = target[field]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                contracts.validate_run_manifest(manifest)

    def test_valid_execution_and_collection_states(self):
        for state, status, evidence, errors in (
            ("RUNNING", "PENDING", "NOT_COLLECTED", []),
            ("RUNNING", "RUNNING", "COLLECTING", []),
            ("SUCCEEDED", "SUCCEEDED", "NOT_COLLECTED", []),
            ("FAILED", "FAILED", "FAILED", ["synthetic collector failure"]),
            ("CANCELLED", "CANCELLED", "COLLECTING", []),
        ):
            manifest = self.create()
            manifest.update({"state": state, "evidence_state": evidence, "collector_errors": errors,
                             "executions": [{"execution_id": "synthetic-execution", "status": status}]})
            with self.subTest(state=state, evidence=evidence):
                self.assertIsNone(contracts.validate_run_manifest(manifest))

    def test_inconsistent_execution_and_collection_states(self):
        for field, value in (
            ("state", "REQUESTED"), ("state", "RUNNING"), ("state", "FAILED"),
            ("state", "CANCELLED"), ("evidence_state", "NOT_COLLECTED"), ("evidence_state", "FAILED"),
            ("collector_errors", ["unexpected error"]), ("executions", []), ("telemetry", []),
            ("logs", []), ("outputs", []),
            ("executions", [{"execution_id": "synthetic-execution-001", "status": "RUNNING"}]),
            ("executions", [{"execution_id": "synthetic-execution-001", "status": "Unknown"}]),
        ):
            manifest = self.completed_manifest()
            manifest[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                contracts.validate_run_manifest(manifest)
        manifest = self.completed_manifest()
        manifest["executions"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate execution_id"):
            contracts.validate_run_manifest(manifest)

    def test_compatible_asset_chain_and_order(self):
        consumer = copy.deepcopy(self.catalog["assets"][0])
        consumer.update({"asset_id": "synthetic-consumer", "image_digest": "sha256:" + "2" * 64,
                         "input_contract": "live-test-events.v1", "output_contract": "live-test-output.v1"})
        self.catalog["assets"].append(consumer)
        self.catalog["presets"][0]["assets"].append({"asset_id": consumer["asset_id"], "version": consumer["version"]})
        self.catalog["presets"][0]["expected_outputs"].append("live-test-output.v1")
        manifest = self.create()
        self.assertIsNone(contracts.validate_run_manifest(manifest))
        self.assertEqual(len(manifest["assets"]), 2)
        manifest["assets"].reverse()
        with self.assertRaisesRegex(ValueError, "pin/order"):
            contracts.validate_run_manifest(manifest)
        self.catalog["presets"][0]["assets"].reverse()
        with self.assertRaisesRegex(ValueError, "incompatible input/output"):
            contracts.validate_catalog(self.catalog)

    def test_wrong_record_and_field_types_raise_value_error(self):
        for validator in (contracts.validate_catalog, contracts.validate_asset_version,
                          contracts.validate_product_version, contracts.validate_preset,
                          contracts.validate_provenance, contracts.validate_run_manifest):
            for value in (None, False, [], "record", 1):
                with self.subTest(validator=validator.__name__, value=value), self.assertRaises(ValueError):
                    validator(value)
        manifest = self.create()
        for field in manifest:
            for value in (None, [], {}):
                if field in ("executions", "telemetry", "logs", "outputs", "collector_errors") and value == []:
                    continue
                mutated = copy.deepcopy(manifest)
                mutated[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    contracts.validate_run_manifest(mutated)


if __name__ == "__main__":
    unittest.main()