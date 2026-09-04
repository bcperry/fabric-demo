from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from .engine import ScenarioEngine
from .scenario import load_scenario
from .transports import FileTransport, JsonLinesTransport, KafkaTransport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run synthetic MDA demo emulators")
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=int, default=180)
    parser.add_argument(
        "--transport",
        choices=("stdout", "file", "kafka"),
        default="stdout",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bootstrap-servers")
    parser.add_argument("--managed-identity-client-id")
    parser.add_argument(
        "--manifest-output",
        type=Path,
        help="Optional JSON file path used to persist the deterministic run manifest before events are published.",
    )
    parser.add_argument(
        "--start-time-utc",
        help="Shared RFC 3339 UTC run start. Defaults to the current UTC time.",
    )
    parser.add_argument(
        "--run-id",
        help="Shared unique run ID. Defaults to one derived from scenario and start time.",
    )
    parser.add_argument(
        "--source-system",
        action="append",
        choices=(
            "TPY2",
            "PATRIOT",
            "THAAD",
            "BATTLE_MANAGEMENT",
            "ARMY_INTEGRATION",
            "TARGET_RANGE",
            "INTERCEPTOR_RANGE",
            "RANGE_RECEIVER",
            "OPTICAL_TRACKER",
            "GROUND_TRUTH",
            "ENVIRONMENT",
            "INSTRUMENTATION_MONITOR",
            "NETWORK_MONITOR",
            "READINESS_CONTROLLER",
            "OPERATOR_CONTROL",
            "SAFETY_MONITOR",
            "SUSTAINMENT",
        ),
        help="Publish only events from the selected source system; repeat as needed.",
    )
    parser.add_argument("--realtime", action="store_true")
    return parser


def create_transport(args: argparse.Namespace):
    if args.transport == "stdout":
        return JsonLinesTransport()
    if args.transport == "file":
        if not args.output:
            raise ValueError("--output is required with file transport")
        return FileTransport(args.output)

    bootstrap = args.bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    if not bootstrap:
        raise ValueError(
            "--bootstrap-servers or KAFKA_BOOTSTRAP_SERVERS is required"
        )
    client_id = args.managed_identity_client_id or os.getenv(
        "AZURE_CLIENT_ID"
    )
    return KafkaTransport(bootstrap, client_id=client_id)


def main() -> None:
    args = build_parser().parse_args()
    scenario = load_scenario(args.scenario)
    start_time = None
    if args.start_time_utc:
        start_time = datetime.fromisoformat(
            args.start_time_utc.replace("Z", "+00:00")
        )
        if start_time.tzinfo is None:
            raise ValueError("--start-time-utc must include a UTC offset")
    engine = ScenarioEngine(scenario, start_time=start_time, run_id=args.run_id)
    transport = create_transport(args)

    if args.manifest_output:
        args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_output.write_text(
            json.dumps(engine.build_run_manifest(args.duration_seconds), indent=2) + "\n",
            encoding="utf-8",
        )

    try:
        last_event_second = None
        for topic, event in engine.generate(args.duration_seconds):
            if args.source_system and event["source_system"] not in args.source_system:
                continue
            if args.realtime:
                current_second = event["event_time_utc"]
                if last_event_second and current_second != last_event_second:
                    time.sleep(1 / scenario["time_scale"])
                last_event_second = current_second
            transport.publish(topic, event)
    finally:
        transport.close()


if __name__ == "__main__":
    main()
