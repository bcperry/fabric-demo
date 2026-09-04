import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mda_emulators.replay import (  # noqa: E402
    load_json_lines,
    paced_records,
    rebase_event_times,
)
from mda_emulators.transports import _build_record, event_hubs_token_scope  # noqa: E402


class ReplayTests(unittest.TestCase):
    def test_kafka_record_matches_raw_table_envelope(self):
        event = {
            "event_id": "1",
            "event_type": "system.status",
            "ordering_key": "patriot-bravo-02",
        }
        record = _build_record("mda-test-events", event)
        self.assertEqual(record["topic"], "mda-test-events")
        self.assertEqual(record["key"], "patriot-bravo-02")
        self.assertEqual(record["event"]["event_id"], "1")
        self.assertIn("ingest_time_utc", record["event"])

    def test_event_hubs_scope_uses_namespace_fqdn(self):
        self.assertEqual(
            event_hubs_token_scope("demo.servicebus.windows.net:9093"),
            "https://demo.servicebus.windows.net/.default",
        )
        with self.assertRaisesRegex(ValueError, "Event Hubs namespace"):
            event_hubs_token_scope("localhost:9092")

    def test_load_requires_routing_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text(json.dumps({"event_id": "1"}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "event_type"):
                load_json_lines(path)

    def test_rebase_preserves_offsets_and_malformed_time(self):
        records = [
            {
                "event_id": "1",
                "event_type": "test.marker",
                "ordering_key": "test",
                "event_time_utc": "2026-09-01T14:00:00Z",
            },
            {
                "event_id": "2",
                "event_type": "system.status",
                "ordering_key": "participant",
                "event_time_utc": "2026-09-01T14:00:05Z",
            },
            {
                "event_id": "3",
                "event_type": "system.status",
                "ordering_key": "invalid",
                "event_time_utc": "2026/09/01 14:00:06",
            },
        ]
        rebased = rebase_event_times(
            records, datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(rebased[0]["event_time_utc"], "2026-09-04T12:00:00Z")
        self.assertEqual(rebased[1]["event_time_utc"], "2026-09-04T12:00:05Z")
        self.assertEqual(rebased[2]["event_time_utc"], records[2]["event_time_utc"])

    def test_pacing_uses_nonnegative_event_time_deltas(self):
        records = [
            {"event_time_utc": "2026-09-04T12:00:00Z"},
            {"event_time_utc": "2026-09-04T12:00:10Z"},
            {"event_time_utc": "2026-09-04T12:00:05Z"},
        ]
        delays = [delay for delay, _ in paced_records(records, speed=10)]
        self.assertEqual(delays, [0.0, 1.0, 0.0])


if __name__ == "__main__":
    unittest.main()