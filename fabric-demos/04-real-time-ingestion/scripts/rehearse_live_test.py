"""Rehearse the pinned synthetic input with the actual local stdout producer.

API: rehearse(output_directory, *, catalog=DEFAULT_CATALOG, run_id=None,
              seed=42, requester="local-rehearsal") -> sanitized summary.
The output directory is reserved exclusively before launch. Every retry needs a
new directory, including after failure; partial directories have no bundle.json.
request-manifest.json is the unchanged validated REQUESTED snapshot. evidence/
is written by collect_live_test.write_bundle. Raw streams, actual input bytes,
and local execution/source provenance are indexed by the outer bundle.json.
No Azure, broker, image resolution, review approval, or delivery claim is made.
"""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

import collect_live_test
import live_test_contracts


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG = ROOT / "shared/integrated-test-data/01-contracts/examples/live-test-catalog.json"
INPUT_URI = "repo://shared/integrated-test-data/01-contracts/examples/live-test-input.json"
PRODUCER = ROOT / "shared/integrated-test-data/02-emulators/src/mda_emulators/target_vehicle.py"


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _write(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)


def _input(manifest):
    product = manifest["input"]
    if product["uri"] != INPUT_URI or product["contract_version"] != "live-test-input.v1":
        raise ValueError("Rehearsal requires the pinned local live-test-input fixture")
    path = ROOT / INPUT_URI.removeprefix("repo://")
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError("Input must remain inside the repository")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != product["sha256"]:
        raise ValueError("Input SHA256 mismatch")
    parameters = json.loads(content, object_pairs_hook=live_test_contracts._json_object,
                            parse_constant=live_test_contracts._invalid_constant)
    if not isinstance(parameters, dict) or set(parameters) != set(manifest["parameters"]):
        raise ValueError("Input parameters do not match manifest parameters")
    if any(type(parameters[name]) not in (int, float) or parameters[name] != value
           for name, value in manifest["parameters"].items()):
        raise ValueError("Input parameters do not match manifest parameters")
    if type(parameters["duration_seconds"]) is not int:
        raise ValueError("Input duration_seconds must be an integer")
    return content, parameters


def rehearse(output_directory, *, catalog=DEFAULT_CATALOG, run_id=None, seed=42,
             requester="local-rehearsal"):
    """Run once locally; reject existing output paths without launching or writing."""
    directory = Path(output_directory).absolute()
    if directory.exists() or directory.is_symlink():
        raise ValueError("Output directory already exists; choose a new directory")
    if not isinstance(requester, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,127}", requester):
        raise ValueError("Requester must be a bounded local label, not credentials")
    manifest = live_test_contracts.create_run_manifest(
        live_test_contracts.load_catalog(catalog), "normal-collection",
        run_id=str(uuid4()) if run_id is None else run_id, requester=requester, seed=seed,
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    if len(manifest["assets"]) != 1 or manifest["assets"][0]["asset_id"] != "synthetic-producer":
        raise ValueError("Local rehearsal supports only the synthetic-producer asset")
    input_bytes, parameters = _input(manifest)
    source_hash = hashlib.sha256(PRODUCER.read_bytes()).hexdigest()
    execution_id = f"local-run-{manifest['run_id']}"
    command = [sys.executable, str(PRODUCER), "--transport", "stdout", "--fast",
               "--run-id", manifest["run_id"], "--seed", str(manifest["seed"]),
               "--vehicle-id", "local-target", "--topic", "local-target-telemetry"]
    for parameter, flag in (("duration_seconds", "--duration"), ("tspi_hz", "--tspi-hz"),
                            ("temperature_hz", "--temperature-hz"), ("error_hz", "--error-hz")):
        command.extend((flag, str(parameters[parameter])))
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    _write(directory / "request-manifest.json", _json_bytes(manifest))
    _write(directory / "input.json", input_bytes)
    try:
        completed = subprocess.run(
            command, cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, check=False,
            timeout=manifest["assets"][0]["runtime"]["timeout_seconds"],
            env={"PATH": os.defpath, "PYTHONIOENCODING": "utf-8", "PYTHONNOUSERSITE": "1"},
        )
    except subprocess.TimeoutExpired as error:
        _write(directory / "stdout.jsonl", error.stdout or b"")
        _write(directory / "stderr.jsonl", error.stderr or b"")
        raise RuntimeError("Local producer timed out; captured evidence retained") from None
    _write(directory / "stdout.jsonl", completed.stdout)
    _write(directory / "stderr.jsonl", completed.stderr)
    if hashlib.sha256(PRODUCER.read_bytes()).hexdigest() != source_hash:
        raise ValueError("Producer source changed during rehearsal; provenance cannot be confirmed")
    telemetry = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    diagnostics = [json.loads(line) for line in completed.stderr.splitlines() if line.strip()]
    status = "SUCCEEDED" if completed.returncode == 0 else "FAILED"
    execution = {"execution_id": execution_id, "status": status}
    collected_manifest = copy.deepcopy(manifest)
    collected_manifest.update(state=status, executions=[execution])
    live_test_contracts.validate_run_manifest(collected_manifest)
    collect_live_test.write_bundle(collected_manifest, telemetry, diagnostics, execution, directory / "evidence")
    summary = json.loads((directory / "evidence/summary.json").read_bytes())
    _write(directory / "local-execution.json", _json_bytes({
        "schema_version": "local-live-test-execution.v1", "source": "local",
        "run_id": manifest["run_id"], "request_id": manifest["request_id"],
        **execution, "returncode": completed.returncode,
        "producer": {"uri": "repo://" + PRODUCER.relative_to(ROOT).as_posix(),
                     "sha256": source_hash, "digest_kind": "LOCAL_SOURCE_SHA256"},
        "image_digest": manifest["assets"][0]["image_digest"],
        "image_digest_kind": manifest["assets"][0]["digest_kind"], "image_resolved": False,
        "deployable": False, "transport": "stdout", "fast": True,
        "parameters": parameters, "seed": manifest["seed"],
        "stdout_acquired": True, "stderr_acquired": True,
        "telemetry_delivery_verified": False,
    }))
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            content = path.read_bytes()
            files[path.relative_to(directory).as_posix()] = {
                "sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content),
            }
    _write(directory / "bundle.json", _json_bytes({
        "schema_version": "local-live-test-rehearsal.v1", "source": "local",
        "run_id": manifest["run_id"], "request_id": manifest["request_id"],
        "execution_id": execution_id, "files": files,
    }))
    if status != "SUCCEEDED":
        raise RuntimeError("Local producer failed; captured evidence retained")
    return {"run_id": manifest["run_id"], "evidence_state": summary["evidence_state"], "source": "local"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-directory", required=True)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--run-id")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--requester", default="local-rehearsal", help="Local declared label, not authenticated identity")
    args = parser.parse_args(argv)
    try:
        summary = rehearse(args.output_directory, catalog=args.catalog, run_id=args.run_id,
                           seed=args.seed, requester=args.requester)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError):
        parser.exit(2, "Local rehearsal failed: check pinned input, parameters, freshness, and a new output directory.\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["evidence_state"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())