"""Strict, synthetic-only local Live Test records; validation is not authorization.

Version 1 rejects unknown fields and mutable version labels. Image digests are
synthetic placeholders, never evidence of a published or deployable image.
"""

import copy
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import re
from uuid import UUID, uuid4


PARAMETER_LIMITS = {
    "duration_seconds": (1, 3600),
    "tspi_hz": (0.01, 100),
    "temperature_hz": (0.01, 100),
    "error_hz": (0.01, 100),
}
CONTRACTS = {"synthetic-scenario.v1", "live-test-input.v1", "live-test-events.v1", "live-test-output.v1"}
METADATA = {"owner", "steward", "description", "permitted_use", "classification", "synthetic"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _fields(record, fields, label):
    _require(isinstance(record, dict), f"{label}: expected an object")
    _require(set(record) == set(fields), f"{label}: missing or unknown fields")


def _record(record, fields, schema):
    _require(isinstance(record, dict), f"{schema}: expected an object")
    _require(record.get("schema_version") == schema, f"unsupported schema_version; expected {schema}")
    _fields(record, set(fields) | {"schema_version"}, schema)


def _text(value, label):
    _require(isinstance(value, str) and bool(value.strip()), f"{label}: expected nonempty text")


def _matches(value, pattern, label):
    _require(isinstance(value, str) and re.fullmatch(pattern, value) is not None, f"invalid {label}")


def _version(value):
    _matches(value, r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", "pinned version")


def _number(value, lower, upper, label):
    _require(type(value) in (int, float), f"{label}: expected a number, not a boolean")
    _require(lower <= value <= upper and math.isfinite(value), f"{label}: outside finite bounds")


def _metadata(record):
    for field in ("owner", "steward", "description"):
        _text(record[field], field)
    _require(record["synthetic"] is True, "only synthetic records are supported")
    _require(record["classification"] == "SYNTHETIC_UNCLASS", "unsupported classification")
    _require(record["permitted_use"] == "LOCAL_CONTRACT_TEST_ONLY", "unsupported permitted_use")


def _bounds(bounds):
    _fields(bounds, PARAMETER_LIMITS, "parameter_bounds")
    for name, (lower, upper) in PARAMETER_LIMITS.items():
        _fields(bounds[name], {"min", "max"}, name)
        _number(bounds[name]["min"], lower, upper, name)
        _number(bounds[name]["max"], lower, upper, name)
        _require(bounds[name]["min"] <= bounds[name]["max"], f"{name}: reversed bounds")


def _contract(value):
    _require(isinstance(value, str) and value in CONTRACTS, "unsupported contract version")


def validate_asset_version(asset: dict) -> None:
    """Validate a non-deployable asset descriptor, raising ValueError on failure."""
    _record(asset, METADATA | {
        "asset_id", "version", "publisher", "image_digest", "digest_kind", "deployable",
        "input_contract", "output_contract", "parameter_bounds", "runtime", "publication_status",
    }, "live-test-asset.v1")
    _metadata(asset)
    _text(asset["asset_id"], "asset_id")
    _text(asset["publisher"], "publisher")
    _version(asset["version"])
    _matches(asset["image_digest"], r"sha256:[0-9a-f]{64}", "image_digest")
    _require(asset["deployable"] is False, "local asset must have deployable:false")
    _require(asset["digest_kind"] == "SYNTHETIC_PLACEHOLDER", "unsupported digest_kind")
    _require(asset["publication_status"] == "LOCAL_ONLY", "unsupported publication_status")
    _contract(asset["input_contract"])
    _contract(asset["output_contract"])
    _bounds(asset["parameter_bounds"])
    _fields(asset["runtime"], {"cpu_cores", "memory_mb", "timeout_seconds"}, "runtime")
    for name, limits in {"cpu_cores": (0.25, 4), "memory_mb": (128, 8192), "timeout_seconds": (1, 3600)}.items():
        _number(asset["runtime"][name], *limits, name)
    _require(asset["runtime"]["timeout_seconds"] >= asset["parameter_bounds"]["duration_seconds"]["max"],
             "runtime timeout does not cover duration bounds")


def _utc(value):
    _matches(value, r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?(Z|\+00:00)", "UTC timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("invalid UTC timestamp") from error


def _uuid(value, label):
    _text(value, label)
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError(f"invalid {label} UUID") from error
    _require(str(parsed) == value and parsed.int != 0, f"{label}: expected canonical nonzero UUID")


def _sha256(value):
    _matches(value, r"[0-9a-f]{64}", "sha256")


def _local_uri(value):
    _matches(value, r"repo://[A-Za-z0-9_./-]+", "local repo URI")
    parts = value[len("repo://"):].split("/")
    _require(all(part not in ("", ".", "..") for part in parts), "local URI must be repository-relative")


def _list(value, label, nonempty=False):
    _require(isinstance(value, list) and (not nonempty or bool(value)), f"{label}: expected {'nonempty ' if nonempty else ''}list")


def _pin(pin, id_field):
    _fields(pin, {id_field, "version"}, "version pin")
    _text(pin[id_field], id_field)
    _version(pin["version"])


def _snapshot(snapshot, product=False):
    fields = {"uri", "version", "sha256"} | ({"product_id"} if product else set())
    _fields(snapshot, fields, "snapshot")
    _local_uri(snapshot["uri"])
    _version(snapshot["version"])
    _sha256(snapshot["sha256"])
    if product:
        _text(snapshot["product_id"], "product_id")


def _product_snapshot(product):
    return {field: product[field] for field in ("product_id", "version", "sha256", "uri")}


def validate_product_version(product: dict) -> None:
    """Validate metadata for a pinned local synthetic input; does not fetch bytes."""
    _record(product, METADATA | {
        "product_id", "version", "source", "uri", "sha256", "contract_version",
        "effective_at", "received_at", "freshness_sla_seconds", "retention_days",
        "access_request_path", "quality_state", "review_state", "endorsement_state",
    }, "live-test-product.v1")
    _metadata(product)
    _snapshot(_product_snapshot(product), product=True)
    _text(product["source"], "source")
    _text(product["access_request_path"], "access_request_path")
    _contract(product["contract_version"])
    _require(_utc(product["effective_at"]) <= _utc(product["received_at"]), "received_at precedes effective_at")
    _number(product["freshness_sla_seconds"], 1, 31536000, "freshness_sla_seconds")
    _number(product["retention_days"], 1, 3650, "retention_days")
    _require(product["quality_state"] == "LOCAL_FIXTURE", "unsupported quality_state")
    _require(product["review_state"] == "NOT_REVIEWED", "local records cannot claim review approval")
    _require(product["endorsement_state"] == "NONE", "local records cannot claim endorsement")


def _parameters(parameters, bounds):
    _fields(parameters, PARAMETER_LIMITS, "parameters")
    for name in PARAMETER_LIMITS:
        _number(parameters[name], bounds[name]["min"], bounds[name]["max"], name)
    _require(type(parameters["duration_seconds"]) is int, "duration_seconds must be an integer")
    _require(max(parameters["temperature_hz"], parameters["error_hz"]) < parameters["tspi_hz"],
             "internal channel rates must be below tspi_hz")


def validate_preset(preset: dict) -> None:
    """Validate a pinned ordered asset chain and its bounded default parameters."""
    _record(preset, METADATA | {
        "preset_id", "version", "input", "assets", "parameter_bounds", "parameters",
        "expected_outputs", "compatibility_rule",
    }, "live-test-preset.v1")
    _metadata(preset)
    _text(preset["preset_id"], "preset_id")
    _version(preset["version"])
    _pin(preset["input"], "product_id")
    _list(preset["assets"], "assets", nonempty=True)
    for asset in preset["assets"]:
        _pin(asset, "asset_id")
    _require(len({asset["asset_id"] for asset in preset["assets"]}) == len(preset["assets"]), "duplicate preset asset")
    _bounds(preset["parameter_bounds"])
    _parameters(preset["parameters"], preset["parameter_bounds"])
    _list(preset["expected_outputs"], "expected_outputs", nonempty=True)
    for contract in preset["expected_outputs"]:
        _contract(contract)
    _require(len(set(preset["expected_outputs"])) == len(preset["expected_outputs"]), "duplicate expected output")
    _require(preset["compatibility_rule"] == "EXACT_CONTRACT_CHAIN", "unsupported compatibility_rule")


def validate_provenance(provenance: dict) -> None:
    """Validate exact source/output pins, not an approval or an authenticity claim."""
    _record(provenance, METADATA | {
        "provenance_id", "version", "source", "output", "rule_version", "recorded_at",
    }, "live-test-provenance.v1")
    _metadata(provenance)
    _text(provenance["provenance_id"], "provenance_id")
    _version(provenance["version"])
    _require(provenance["rule_version"] == "local-source-pin.v1", "unsupported provenance rule_version")
    _snapshot(provenance["source"])
    _snapshot(provenance["output"], product=True)
    _utc(provenance["recorded_at"])


def _index(records, id_field, validator, label):
    _list(records, label, nonempty=True)
    indexed = {}
    for record in records:
        validator(record)
        key = (record[id_field], record["version"])
        _require(key not in indexed, f"duplicate {label} version")
        indexed[key] = record
    return indexed


def _resolve(indexed, pin, id_field):
    key = (pin[id_field], pin["version"])
    _require(key in indexed, f"unresolved {id_field} version: {key}")
    return indexed[key]


def _compatible(preset, product, assets):
    _require(preset["input"] == {field: product[field] for field in ("product_id", "version")}, "input pin mismatch")
    _require(preset["assets"] == [{field: asset[field] for field in ("asset_id", "version")} for asset in assets], "asset pin/order mismatch")
    incoming = product["contract_version"]
    for asset in assets:
        _require(asset["input_contract"] == incoming, "incompatible input/output contracts")
        incoming = asset["output_contract"]
        for name, bounds in preset["parameter_bounds"].items():
            allowed = asset["parameter_bounds"][name]
            _require(allowed["min"] <= bounds["min"] <= bounds["max"] <= allowed["max"], f"incompatible {name} bounds")
    _require(set(preset["expected_outputs"]) <= {asset["output_contract"] for asset in assets}, "incompatible expected outputs")


def _input_provenance(product, records):
    matches = [record for record in records if record["output"] == _product_snapshot(product)]
    _require(len(matches) == 1, "input requires exactly one matching provenance record")
    return matches[0]


def validate_catalog(catalog: dict) -> None:
    """Validate all records and exact-version compatibility, without network I/O."""
    _record(catalog, {"catalog_id", "assets", "products", "presets", "provenance"}, "live-test-catalog.v1")
    _text(catalog["catalog_id"], "catalog_id")
    assets = _index(catalog["assets"], "asset_id", validate_asset_version, "assets")
    products = _index(catalog["products"], "product_id", validate_product_version, "products")
    _index(catalog["presets"], "preset_id", validate_preset, "presets")
    _index(catalog["provenance"], "provenance_id", validate_provenance, "provenance")
    _require(len({preset["preset_id"] for preset in catalog["presets"]}) == len(catalog["presets"]), "preset_id must select exactly one version")
    for product in catalog["products"]:
        provenance = _input_provenance(product, catalog["provenance"])
        _require(_utc(provenance["recorded_at"]) >= _utc(product["received_at"]), "provenance precedes receipt")
    for record in catalog["provenance"]:
        product = _resolve(products, record["output"], "product_id")
        _require(record["output"] == _product_snapshot(product), "provenance output pin mismatch")
    for preset in catalog["presets"]:
        product = _resolve(products, preset["input"], "product_id")
        selected = [_resolve(assets, pin, "asset_id") for pin in preset["assets"]]
        _compatible(preset, product, selected)


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def load_catalog(path: str | Path) -> dict:
    """Read UTF-8 JSON and validate it; no source fetching or launch authorization."""
    catalog = json.loads(Path(path).read_text(encoding="utf-8"),
                         object_pairs_hook=_json_object, parse_constant=_invalid_constant)
    validate_catalog(catalog)
    return catalog


def create_run_manifest(catalog: dict, preset_id: str, *, run_id: str,
                        requester: str, seed: int, created_at: str) -> dict:
    """Create a detached REQUESTED record. Persist it to reuse its request_id.

    Requester is declared local identity, not an authenticated principal. Input,
    assets and preset retain their full validated metadata as offline snapshots.
    This function does not reserve IDs, establish idempotency, or authorize Azure.
    """
    validate_catalog(catalog)
    _text(preset_id, "preset_id")
    selected = [preset for preset in catalog["presets"] if preset["preset_id"] == preset_id]
    _require(len(selected) == 1, "unknown preset_id")
    preset = selected[0]
    products = {(product["product_id"], product["version"]): product for product in catalog["products"]}
    assets = {(asset["asset_id"], asset["version"]): asset for asset in catalog["assets"]}
    product = _resolve(products, preset["input"], "product_id")
    manifest = copy.deepcopy({
        "schema_version": "live-test-run.v1", "catalog_id": catalog["catalog_id"],
        "run_id": run_id, "request_id": str(uuid4()), "preset_id": preset_id,
        "requester": requester, "requester_kind": "LOCAL_DECLARED",
        "synthetic": True, "deployable": False,
        "input": product, "assets": [_resolve(assets, pin, "asset_id") for pin in preset["assets"]],
        "preset": preset, "provenance": _input_provenance(product, catalog["provenance"]),
        "parameters": copy.deepcopy(preset["parameters"]), "seed": seed, "state": "REQUESTED", "created_at": created_at,
        "executions": [], "telemetry": [], "logs": [], "outputs": [],
        "evidence_state": "NOT_COLLECTED", "collector_errors": [],
    })
    validate_run_manifest(manifest)
    return manifest


def _evidence(manifest, executions):
    for collection in ("telemetry", "logs", "outputs"):
        _list(manifest[collection], collection)
        seen = set()
        for reference in manifest[collection]:
            fields = {"run_id", "request_id", "execution_id", "uri"}
            if collection == "telemetry":
                fields |= {"contract_version"}
            elif collection == "logs":
                fields |= {"kind"}
            else:
                fields |= {"product_id", "version", "sha256", "provenance"}
            _fields(reference, fields, f"{collection} reference")
            for identity in ("run_id", "request_id"):
                _require(reference[identity] == manifest[identity], f"{collection}: {identity} mismatch")
            _text(reference["execution_id"], "execution_id")
            _require(reference["execution_id"] in executions, "unlinked evidence execution_id")
            _local_uri(reference["uri"])
            _require(reference["uri"] not in seen, "duplicate evidence URI")
            seen.add(reference["uri"])
            if collection == "telemetry":
                _contract(reference["contract_version"])
                _require(reference["contract_version"] in manifest["preset"]["expected_outputs"], "unexpected telemetry contract")
            elif collection == "logs":
                _require(reference["kind"] in ("STDOUT", "STDERR", "PLATFORM"), "unsupported log kind")
            else:
                _snapshot(_product_snapshot(reference), product=True)
                validate_provenance(reference["provenance"])
                _require(reference["provenance"]["output"] == _product_snapshot(reference), "output provenance mismatch")
                source = {field: manifest["input"][field] for field in ("uri", "version", "sha256")}
                _require(reference["provenance"]["source"] == source, "output source pin mismatch")
                _require(_utc(reference["provenance"]["recorded_at"]) >= _utc(manifest["created_at"]), "output provenance predates run")


def validate_run_manifest(manifest: dict) -> None:
    """Validate offline consistency, not authenticity or historical transitions.

    Full input/asset/preset snapshots are intentional: their owners, contracts,
    bounds and exact pins remain inspectable without mutable catalog lookups.
    Self-consistent edits cannot be detected without trusted persistence/signing.
    """
    _record(manifest, {
        "catalog_id", "run_id", "request_id", "preset_id", "requester", "requester_kind",
        "synthetic", "deployable", "input", "assets", "preset", "provenance", "parameters",
        "seed", "state", "created_at", "executions", "telemetry", "logs", "outputs",
        "evidence_state", "collector_errors",
    }, "live-test-run.v1")
    _text(manifest["catalog_id"], "catalog_id")
    _uuid(manifest["run_id"], "run_id")
    _uuid(manifest["request_id"], "request_id")
    _text(manifest["requester"], "requester")
    _require(manifest["requester_kind"] == "LOCAL_DECLARED", "requester is not authenticated authorization")
    _require(manifest["synthetic"] is True and manifest["deployable"] is False, "run must be synthetic and non-deployable")
    _require(type(manifest["seed"]) is int and 0 <= manifest["seed"] <= 2 ** 63 - 1, "seed must be an integer in [0, 2**63-1]")
    created = _utc(manifest["created_at"])
    validate_product_version(manifest["input"])
    _index(manifest["assets"], "asset_id", validate_asset_version, "assets")
    validate_preset(manifest["preset"])
    validate_provenance(manifest["provenance"])
    _input_provenance(manifest["input"], [manifest["provenance"]])
    received = _utc(manifest["input"]["received_at"])
    _require(received <= _utc(manifest["provenance"]["recorded_at"]) <= created, "input provenance timestamps inconsistent with run")
    _require(created - received <= timedelta(seconds=manifest["input"]["freshness_sla_seconds"]), "input is stale at created_at")
    _require(manifest["preset_id"] == manifest["preset"]["preset_id"], "preset_id mismatch")
    _compatible(manifest["preset"], manifest["input"], manifest["assets"])
    _parameters(manifest["parameters"], manifest["preset"]["parameter_bounds"])
    _require(manifest["parameters"] == manifest["preset"]["parameters"], "parameters differ from selected preset")
    _list(manifest["executions"], "executions")
    executions = {}
    for execution in manifest["executions"]:
        _fields(execution, {"execution_id", "status"}, "execution")
        _text(execution["execution_id"], "execution_id")
        _require(execution["execution_id"] not in executions, "duplicate execution_id")
        _require(execution["status"] in ("PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"), "unsupported execution status")
        executions[execution["execution_id"]] = execution["status"]
    state = manifest["state"]
    _require(state in ("REQUESTED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"), "unsupported run state")
    statuses = set(executions.values())
    if state == "REQUESTED":
        _require(not executions, "REQUESTED run cannot have executions")
    elif state == "RUNNING":
        _require(bool(statuses & {"PENDING", "RUNNING"}), "RUNNING run requires an active execution")
    else:
        _require(bool(statuses) and not statuses & {"PENDING", "RUNNING"}, "terminal run requires terminal executions")
        _require(state in statuses, "terminal run state disagrees with executions")
        if state == "SUCCEEDED":
            _require(statuses == {"SUCCEEDED"}, "SUCCEEDED run has unsuccessful executions")
    _evidence(manifest, executions)
    evidence = manifest["evidence_state"]
    _require(evidence in ("NOT_COLLECTED", "COLLECTING", "COLLECTED", "FAILED"), "unsupported evidence_state")
    _list(manifest["collector_errors"], "collector_errors")
    for error in manifest["collector_errors"]:
        _text(error, "collector error")
    if evidence == "NOT_COLLECTED":
        _require(not any(manifest[name] for name in ("telemetry", "logs", "outputs", "collector_errors")), "NOT_COLLECTED run has evidence or errors")
    else:
        _require(bool(executions), "collection requires a linked execution")
    if evidence == "COLLECTED":
        _require(state in ("SUCCEEDED", "FAILED", "CANCELLED"), "collection incomplete while run is active")
        _require(all(manifest[name] for name in ("telemetry", "logs", "outputs")) and not manifest["collector_errors"], "COLLECTED requires telemetry, logs, outputs and no collector errors")
    if evidence == "FAILED":
        _require(bool(manifest["collector_errors"]), "FAILED collection requires errors")