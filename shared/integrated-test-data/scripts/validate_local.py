from __future__ import annotations

import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


DEMO_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = DEMO_ROOT.parents[1]
EMULATOR_ROOT = DEMO_ROOT / "02-emulators"
SCENARIO = DEMO_ROOT / "01-contracts/examples/scenario.integrated-defense.json"
SUPPORT_SCRIPT = DEMO_ROOT / "generate.py"
STALE_AZURE_SQL_PATTERNS = (
    re.compile(r"\bazure sql\b", re.IGNORECASE),
    re.compile(r"microsoft\.sql/servers", re.IGNORECASE),
    re.compile(r"\bsql server\b", re.IGNORECASE),
)


def run(
    command: list[str], *, cwd: Path = DEMO_ROOT, quiet: bool = False
) -> None:
    print("+", " ".join(command))
    subprocess.run(
        command,
        cwd=cwd,
        check=True,
        stdout=subprocess.DEVNULL if quiet else None,
    )


def validate_json() -> None:
    for path in sorted(DEMO_ROOT.rglob("*.json")):
        with path.open(encoding="utf-8") as handle:
            json.load(handle)
    print("JSON syntax: OK")


def validate_python() -> None:
    run([sys.executable, "-m", "compileall", "-q", str(EMULATOR_ROOT / "src")])
    run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=EMULATOR_ROOT,
    )


def validate_event_stream() -> None:
    demo_manifest = json.loads((DEMO_ROOT / "RELEASE_MANIFEST.json").read_text())
    expected_topics = demo_manifest["observed_event_topics"]
    expected_rows = demo_manifest["observed_event_count"]
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "events.jsonl"
        manifest = Path(directory) / "run-manifest.json"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(EMULATOR_ROOT / "src")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "mda_emulators.cli",
                "--scenario",
                str(SCENARIO),
                "--duration-seconds",
                "180",
                "--transport",
                "file",
                "--manifest-output",
                str(manifest),
                "--output",
                str(output),
            ],
            cwd=DEMO_ROOT,
            env=environment,
            check=True,
        )
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        topics = collections.Counter(row["topic"] for row in rows)
        persisted_manifest = json.loads(manifest.read_text())
        delayed = sum(
            row["event"].get("status") == "DELAYED" for row in rows
        )
        if persisted_manifest["simulation_run_id"] == "":
            raise RuntimeError("Run manifest was not persisted correctly")
        if len(rows) != expected_rows or delayed != 1 or dict(topics) != expected_topics:
            raise RuntimeError(
                "Unexpected deterministic stream: "
                f"events={len(rows)}, delayed={delayed}, topics={dict(topics)}"
            )
        print(f"Event stream: OK ({len(rows)} events; {dict(topics)})")


def validate_bicep() -> None:
    if not shutil.which("az"):
        print("Bicep: SKIPPED (Azure CLI not installed)")
        return
    run(
        [
            "az",
            "bicep",
            "build",
            "--file",
            str(DEMO_ROOT / "00-infrastructure/main.bicep"),
            "--stdout",
        ],
        quiet=True,
    )
    print("Bicep: OK")


def validate_helm() -> None:
    helm = shutil.which("helm")
    if not helm:
        local_helm = Path.home() / ".local/bin/helm"
        helm = str(local_helm) if local_helm.exists() else None
    if not helm:
        print("Helm: BLOCKED (install Helm to render the chart)")
        return
    rendered: dict[str, str] = {}
    for values in ("values-local.yaml", "values-azure.yaml"):
        lint_command = [
            helm,
            "lint",
            str(DEMO_ROOT / "03-kubernetes"),
            "-f",
            str(DEMO_ROOT / "03-kubernetes" / values),
        ]
        print("+", " ".join(lint_command))
        subprocess.run(
            lint_command,
            cwd=DEMO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        command = [
            helm,
            "template",
            "mda-demo",
            str(DEMO_ROOT / "03-kubernetes"),
            "-f",
            str(DEMO_ROOT / "03-kubernetes" / values),
        ]
        print("+", " ".join(command))
        result = subprocess.run(
            command,
            cwd=DEMO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        rendered[values] = result.stdout

    for values, manifest in rendered.items():
        if manifest.count("kind: Deployment") != 6:
            raise RuntimeError(f"{values} did not render six producer deployments")
        if manifest.count("serviceAccountName: mda-emulators") != 6:
            raise RuntimeError(f"{values} has inconsistent service-account names")
        if manifest.count("- --start-time-utc") != 6:
            raise RuntimeError(f"{values} does not inject the shared start time")
        if manifest.count("- --run-id") != 6:
            raise RuntimeError(f"{values} does not inject the shared run ID")
        if manifest.count("- --manifest-output") != 6:
            raise RuntimeError(f"{values} does not inject persisted manifest output")

    if rendered["values-local.yaml"].count("- stdout") != 6:
        raise RuntimeError("Local Helm values must use stdout for every producer")
    if rendered["values-azure.yaml"].count("- kafka") != 6:
        raise RuntimeError("Azure Helm values must use Kafka for every producer")
    if "azure.workload.identity/client-id:" not in rendered["values-azure.yaml"]:
        raise RuntimeError("Azure Helm values are missing workload identity")
    print("Helm: OK")


def validate_forbidden_reference() -> None:
    forbidden = "data" + "bricks"
    matches: list[str] = []
    for path in DEMO_ROOT.rglob("*"):
        if (
            not path.is_file()
            or ".git" in path.parts
            or ".venv" in path.parts
            or "__pycache__" in path.parts
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if forbidden.casefold() in text.casefold():
            matches.append(str(path.relative_to(DEMO_ROOT)))
    if matches:
        raise RuntimeError(f"Forbidden repository references: {matches}")
    print("Forbidden reference scan: OK")


def validate_postgresql_terminology() -> None:
    matches: list[str] = []
    this_file = Path(__file__).resolve()
    for path in DEMO_ROOT.rglob("*"):
        if (
            not path.is_file()
            or path.resolve() == this_file
            or ".git" in path.parts
            or ".venv" in path.parts
            or "__pycache__" in path.parts
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(pattern.search(text) for pattern in STALE_AZURE_SQL_PATTERNS):
            matches.append(str(path.relative_to(DEMO_ROOT)))
    if matches:
        raise RuntimeError(f"Stale Azure SQL references: {matches}")
    print("PostgreSQL terminology scan: OK")


def validate_generated_assets() -> None:
    run([sys.executable, str(SUPPORT_SCRIPT), "validate"])


def main() -> None:
    validate_json()
    validate_python()
    validate_event_stream()
    validate_generated_assets()
    validate_bicep()
    validate_helm()
    validate_forbidden_reference()
    validate_postgresql_terminology()
    print("Local validation complete")


if __name__ == "__main__":
    main()
