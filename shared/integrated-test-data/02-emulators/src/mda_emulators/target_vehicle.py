"""Standalone synthetic visualization telemetry, not a vehicle-performance model.

Run with uv run target_vehicle.py --help. No dependencies for stdout mode.
Kafka requires confluent-kafka; Event Hubs OAuth also requires azure-identity.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import random
import secrets
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


class CorrelatedNoise:
    def __init__(self, rng, sigma, correlation_seconds):
        self.rng = rng
        self.sigma = sigma
        self.correlation_seconds = correlation_seconds
        self.value = rng.gauss(0, sigma)

    def step(self, elapsed):
        retention = math.exp(-elapsed / self.correlation_seconds)
        self.value = retention * self.value + self.rng.gauss(
            0, self.sigma * math.sqrt(-math.expm1(-2 * elapsed / self.correlation_seconds))
        )
        return self.value


class TargetVehicle:
    def __init__(self, seed, duration=900.0):
        self.seed = seed
        self.duration = duration
        route_rng = random.Random(seed)
        self.latitude_offset = route_rng.uniform(-0.5, 0.5)
        self.longitude_offset = route_rng.uniform(-0.5, 0.5)
        self.arc_height = route_rng.uniform(70000, 90000)
        position_rng = random.Random(f"{seed}:position")
        self.position_noise = [CorrelatedNoise(position_rng, 8, 2) for _ in range(3)]
        self.temperature_noise = CorrelatedNoise(random.Random(f"{seed}:temperature"), 0.6, 8)
        self.error_rng = random.Random(f"{seed}:error")
        self.error_word = sum(
            (1 << bit) for bit in range(4) if self.error_rng.random() < 0.002 / 0.202
        )

    def sample(self, channel, elapsed, delta):
        progress = elapsed / self.duration
        if channel == "tspi":
            north, east, vertical = [noise.step(delta) for noise in self.position_noise]
            latitude = 10 + 8 * progress + self.latitude_offset
            return {
                "latitude_deg": latitude + north / 111320,
                "longitude_deg": -165 + 17 * progress + self.longitude_offset
                + east / (111320 * math.cos(math.radians(latitude))),
                "altitude_m": 20000 + self.arc_height * math.sin(math.pi * progress) ** 2
                + vertical,
            }
        if channel == "temperature":
            return {"temperature_c": 30 + 18 * math.sin(math.pi * progress) ** 2
                    + self.temperature_noise.step(delta)}
        transition = -math.expm1(-0.202 * delta)
        for bit in range(4):
            mask = 1 << bit
            rate = 0.2 if self.error_word & mask else 0.002
            if self.error_rng.random() < rate / 0.202 * transition:
                self.error_word ^= mask
        return {"error_word": self.error_word}

    def events(self, start, run_id, vehicle_id, rates):
        schedule = [(0.0, channel, 0) for channel in rates]
        heapq.heapify(schedule)
        sequence = 0
        while schedule:
            elapsed, channel, sample_index = heapq.heappop(schedule)
            if elapsed >= self.duration:
                continue
            sequence += 1
            yield elapsed, {
                "schema_version": "target-vehicle.v1",
                "synthetic": True,
                "run_id": run_id,
                "vehicle_id": vehicle_id,
                "event_id": f"{run_id}:{sequence}",
                "sequence_number": sequence,
                "channel": channel,
                "event_time_utc": (start + timedelta(seconds=elapsed)).isoformat().replace("+00:00", "Z"),
                "elapsed_seconds": elapsed,
                "startup_seed": self.seed,
                "data": self.sample(channel, elapsed, 0 if sample_index == 0 else 1 / rates[channel]),
            }
            next_index = sample_index + 1
            heapq.heappush(schedule, (next_index / rates[channel], channel, next_index))


class KafkaSink:
    def __init__(self, args):
        from confluent_kafka import Producer

        config = json.loads(Path(args.kafka_config).read_text()) if args.kafka_config else {}
        config.update({
            "bootstrap.servers": args.bootstrap_servers,
            "client.id": args.vehicle_id,
            "enable.idempotence": True,
            "acks": "all",
            "delivery.timeout.ms": 20000,
        })
        self.credential = None
        if args.event_hubs:
            from azure.identity import DefaultAzureCredential

            host = args.bootstrap_servers.split(",")[0].split(":")[0]
            if not host.endswith(".servicebus.windows.net"):
                raise ValueError("--event-hubs requires an Event Hubs namespace")
            self.credential = DefaultAzureCredential(
                managed_identity_client_id=os.getenv("AZURE_CLIENT_ID")
            )

            def oauth_callback(_config):
                token = self.credential.get_token(f"https://{host}/.default")
                return token.token, float(token.expires_on)

            config.update({"security.protocol": "SASL_SSL", "sasl.mechanism": "OAUTHBEARER",
                           "oauth_cb": oauth_callback})
        self.producer = Producer(config)
        self.failed = 0

    def delivered(self, error, _message):
        if error is not None:
            self.failed += 1

    def publish(self, topic, key, value, stopped):
        deadline = time.monotonic() + 20
        while not stopped.is_set():
            self.producer.poll(0)
            if self.failed:
                raise RuntimeError("Kafka delivery failed; check broker access and topic configuration")
            try:
                self.producer.produce(topic, key=key, value=value, on_delivery=self.delivered)
                return
            except BufferError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Kafka producer queue remained full for 20 seconds") from None
                self.producer.poll(0.1)

    def close(self):
        try:
            remaining = self.producer.flush(25)
            if remaining or self.failed:
                raise RuntimeError(f"Kafka shutdown: {remaining} pending, {self.failed} failed messages")
        finally:
            if self.credential is not None:
                self.credential.close()


def positive_number(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("stdout", "kafka"), default="stdout")
    parser.add_argument("--bootstrap-servers", default=os.getenv("KAFKA_BOOTSTRAP_SERVERS"))
    parser.add_argument("--kafka-config", default=os.getenv("KAFKA_CONFIG_FILE"), help="Mounted librdkafka JSON config, including TLS/SASL settings")
    parser.add_argument("--event-hubs", action="store_true", help="Use Entra OAuth/workload identity")
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC", "target-vehicle-telemetry"))
    parser.add_argument("--vehicle-id", default=os.getenv("VEHICLE_ID", os.getenv("HOSTNAME", "target-01")))
    parser.add_argument("--duration", type=positive_number, default=900.0)
    parser.add_argument("--tspi-hz", type=positive_number, default=20.0)
    parser.add_argument("--temperature-hz", type=positive_number, default=2.0)
    parser.add_argument("--error-hz", type=positive_number, default=1.0)
    parser.add_argument("--seed", type=int, help="Optional replay seed; otherwise generated from OS entropy")
    parser.add_argument("--loop", action="store_true", help="Start another independent flight after each arc")
    parser.add_argument("--fast", action="store_true", help="Generate without wall-clock pacing (stdout only)")
    args = parser.parse_args(argv)
    if max(args.temperature_hz, args.error_hz) >= args.tspi_hz:
        parser.error("internal channel rates must be below --tspi-hz")
    if args.transport == "kafka" and (not args.bootstrap_servers or args.fast):
        parser.error("Kafka requires --bootstrap-servers and does not allow --fast")
    if args.event_hubs and args.transport != "kafka":
        parser.error("--event-hubs requires --transport kafka")
    stopped = threading.Event()
    for signal_number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signal_number, lambda _number, _frame: stopped.set())
    sink = KafkaSink(args) if args.transport == "kafka" else None
    rates = {"tspi": args.tspi_hz, "temperature": args.temperature_hz, "error": args.error_hz}
    flight_number = 0
    try:
        while not stopped.is_set():
            seed = secrets.randbits(53) if args.seed is None else args.seed + flight_number
            run_id = str(uuid.uuid4())
            start = datetime.now(timezone.utc)
            clock_start = time.monotonic()
            print(json.dumps({"run_id": run_id, "seed": seed, "vehicle_id": args.vehicle_id}), file=sys.stderr, flush=True)
            vehicle = TargetVehicle(seed, args.duration)
            for elapsed, event in vehicle.events(start, run_id, args.vehicle_id, rates):
                if stopped.is_set() or (not args.fast and stopped.wait(max(0, clock_start + elapsed - time.monotonic()))):
                    break
                record = {"topic": args.topic, "key": args.vehicle_id, "event": event}
                payload = json.dumps(record, separators=(",", ":"), allow_nan=False)
                if sink is None:
                    print(payload, flush=True)
                else:
                    sink.publish(args.topic, args.vehicle_id, payload.encode(), stopped)
            if not args.fast:
                stopped.wait(max(0, clock_start + args.duration - time.monotonic()))
            if not args.loop:
                break
            flight_number += 1
    finally:
        if sink is not None:
            sink.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())