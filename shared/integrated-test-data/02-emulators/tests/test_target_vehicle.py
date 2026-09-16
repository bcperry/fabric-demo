import math
import random
import statistics
import subprocess
import sys
import threading
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mda_emulators.target_vehicle import CorrelatedNoise, KafkaSink, TargetVehicle


class TargetVehicleTests(unittest.TestCase):
    def events(self, seed=12, duration=900, rates=None):
        return list(TargetVehicle(seed, duration).events(
            datetime(2026, 1, 1, tzinfo=timezone.utc), "run", "vehicle",
            rates or {"tspi": 20, "temperature": 2, "error": 1},
        ))

    def test_cadence_and_replay(self):
        events = self.events(duration=3)
        self.assertEqual(events, self.events(duration=3))
        self.assertNotEqual(events, self.events(seed=13, duration=3))
        self.assertEqual(Counter(event["channel"] for _, event in events),
                         {"tspi": 60, "temperature": 6, "error": 3})
        self.assertEqual([elapsed for elapsed, _ in events], sorted(elapsed for elapsed, _ in events))
        self.assertEqual([event["sequence_number"] for _, event in events], list(range(1, 70)))
        changed_rates = self.events(duration=3, rates={"tspi": 20, "temperature": 3, "error": 0.5})
        self.assertEqual([event["data"] for _, event in events if event["channel"] == "tspi"],
                         [event["data"] for _, event in changed_rates if event["channel"] == "tspi"])

    def test_pacific_arc_and_continuity(self):
        positions = [event["data"] for _, event in self.events() if event["channel"] == "tspi"]
        first, last = positions[0], positions[-1]
        latitude_delta = math.radians(last["latitude_deg"] - first["latitude_deg"])
        longitude_delta = math.radians(last["longitude_deg"] - first["longitude_deg"])
        haversine = math.sin(latitude_delta / 2) ** 2 + math.cos(math.radians(first["latitude_deg"])) * math.cos(math.radians(last["latitude_deg"])) * math.sin(longitude_delta / 2) ** 2
        distance_miles = 3958.8 * 2 * math.asin(math.sqrt(haversine))
        self.assertGreater(distance_miles, 1000)
        for position in positions:
            self.assertTrue(9 < position["latitude_deg"] < 19)
            self.assertTrue(-166 < position["longitude_deg"] < -147)
            self.assertTrue(19000 < position["altitude_m"] < 111000)
        for previous, current in zip(positions, positions[1:]):
            self.assertLess(abs(current["latitude_deg"] - previous["latitude_deg"]), 0.002)
            self.assertLess(abs(current["longitude_deg"] - previous["longitude_deg"]), 0.003)
            self.assertLess(abs(current["altitude_m"] - previous["altitude_m"]), 30)

    def test_noise_distribution_and_correlation(self):
        noise = CorrelatedNoise(random.Random(7), 8, 2)
        samples = [noise.step(0.1) for _ in range(100000)]
        self.assertAlmostEqual(statistics.mean(samples), 0, delta=0.5)
        self.assertAlmostEqual(statistics.variance(samples), 64, delta=5)
        self.assertAlmostEqual(statistics.correlation(samples[:-1], samples[1:]), math.exp(-0.1 / 2), delta=0.01)

    def test_error_word_stationary_distribution(self):
        vehicle = TargetVehicle(7)
        words = [vehicle.sample("error", 0, 1)["error_word"] for _ in range(100000)]
        self.assertTrue(all(0 <= word <= 15 for word in words))
        for bit in range(4):
            occupancy = sum(bool(word & (1 << bit)) for word in words) / len(words)
            self.assertAlmostEqual(occupancy, 0.002 / 0.202, delta=0.003)

    def sink(self, producer):
        with patch.dict(sys.modules, {"confluent_kafka": SimpleNamespace(Producer=Mock(return_value=producer))}):
            return KafkaSink(SimpleNamespace(kafka_config=None, bootstrap_servers="localhost:9092",
                                             vehicle_id="test", event_hubs=False))

    def test_kafka_backpressure_and_delivery_failure(self):
        producer = Mock()
        producer.produce.side_effect = [BufferError(), None]
        sink = self.sink(producer)
        sink.publish("topic", "vehicle", b"{}", threading.Event())
        self.assertEqual(producer.produce.call_count, 2)
        producer.poll.assert_any_call(0.1)
        sink.delivered("failed", None)
        with self.assertRaisesRegex(RuntimeError, "Kafka delivery failed"):
            sink.publish("topic", "vehicle", b"{}", threading.Event())
        producer.flush.return_value = 0
        with self.assertRaisesRegex(RuntimeError, "1 failed"):
            sink.close()

    def test_kafka_queue_timeout_and_shutdown(self):
        producer = Mock()
        producer.produce.side_effect = BufferError()
        sink = self.sink(producer)
        with patch("mda_emulators.target_vehicle.time.monotonic", side_effect=[0, 21]):
            with self.assertRaisesRegex(RuntimeError, "queue remained full"):
                sink.publish("topic", "vehicle", b"{}", threading.Event())
        producer.flush.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "1 pending"):
            sink.close()
        producer.flush.return_value = 0
        sink.close()
        producer.flush.assert_called_with(25)

    def test_cli_output_validation_and_sigterm(self):
        script = Path(__file__).resolve().parents[1] / "src/mda_emulators/target_vehicle.py"
        completed = subprocess.run([sys.executable, str(script), "--fast", "--duration", "1"],
                                   capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(len(completed.stdout.splitlines()), 23)
        for arguments in (["--duration", "nan"], ["--error-hz", "20"],
                          ["--transport", "kafka", "--fast"]):
            invalid = subprocess.run([sys.executable, str(script), *arguments],
                                     capture_output=True, timeout=10)
            self.assertEqual(invalid.returncode, 2)
        process = subprocess.Popen([sys.executable, str(script), "--loop"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(process.stdout.readline())
            process.terminate()
            process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    unittest.main()