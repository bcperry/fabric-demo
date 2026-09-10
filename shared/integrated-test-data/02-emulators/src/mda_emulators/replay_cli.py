from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .replay import load_json_lines, paced_records, parse_rfc3339, rebase_event_times
from .transports import JsonLinesTransport, KafkaTransport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay synthetic MDA JSONL events to stdout or Event Hubs Kafka"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--topic", default="mda-test-events")
    parser.add_argument(
        "--transport", choices=("stdout", "kafka"), default="stdout"
    )
    parser.add_argument("--bootstrap-servers")
    parser.add_argument("--managed-identity-client-id")
    parser.add_argument("--run-id", help="Explicit replay identity; omit for a unique rehearsal run.")
    parser.add_argument(
        "--speed",
        type=float,
        default=10.0,
        help="Replay speed multiplier; 10 sends ten event seconds per wall-clock second.",
    )
    parser.add_argument(
        "--keep-event-times",
        action="store_true",
        help="Retain checked-in timestamps instead of shifting the latest event to playback start.",
    )
    return parser


def create_transport(args: argparse.Namespace):
    if args.transport == "stdout":
        return JsonLinesTransport()
    bootstrap = args.bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    if not bootstrap:
        raise ValueError(
            "--bootstrap-servers or KAFKA_BOOTSTRAP_SERVERS is required"
        )
    client_id = args.managed_identity_client_id or os.getenv("AZURE_CLIENT_ID")
    return KafkaTransport(bootstrap, client_id=client_id)


def main() -> None:
    args = build_parser().parse_args()
    records = load_json_lines(args.input)
    if not args.keep_event_times:
        event_times = [parsed for event in records if (parsed := parse_rfc3339(event.get("event_time_utc"))) is not None]
        if not event_times:
            raise ValueError("At least one valid event_time_utc is required for rebasing")
        replay_start = datetime.now(timezone.utc) - (max(event_times) - min(event_times))
        records = rebase_event_times(records, replay_start)
    replay_run_id = args.run_id or f"replay-{uuid4()}"
    for event in records:
        event["recorded_simulation_run_id"] = event.get("simulation_run_id")
        event["simulation_run_id"] = replay_run_id
        event["transport_mode"] = "recorded_replay"
        event["replay_speed"] = args.speed
    transport = create_transport(args)
    published = 0
    try:
        for delay, event in paced_records(records, args.speed):
            if delay:
                time.sleep(delay)
            transport.publish(args.topic, event)
            published += 1
    finally:
        transport.close()
    print(f"Published {published} synthetic records to {args.topic}; replay run {replay_run_id}")


if __name__ == "__main__":
    main()