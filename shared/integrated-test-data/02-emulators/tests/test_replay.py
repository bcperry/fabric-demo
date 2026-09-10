import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

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
        self.assertIn("published_time_utc", record["event"])
        self.assertNotIn("ingest_time_utc", record["event"])

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
                "ingest_time_utc": "2026-09-01T14:00:03Z",
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
        self.assertEqual(rebased[0]["ingest_time_utc"], "2026-09-04T12:00:03Z")
        self.assertEqual(rebased[0]["recorded_ingest_time_utc"], records[0]["ingest_time_utc"])
        self.assertEqual(rebased[0]["recorded_event_time_utc"], records[0]["event_time_utc"])
        self.assertEqual(rebased[1]["event_time_utc"], "2026-09-04T12:00:05Z")
        self.assertEqual(rebased[2]["event_time_utc"], records[2]["event_time_utc"])

    def test_pacing_uses_nonnegative_event_time_deltas(self):
        records = [
            {"event_time_utc": "2026-09-04T12:00:00Z"},
            {"event_time_utc": "2026-09-04T12:00:10Z"},
            {"event_time_utc": "2026-09-04T12:00:05Z"},
            {"event_time_utc": "2026-09-04T12:00:12Z"},
        ]
        delays = [delay for delay, _ in paced_records(records, speed=10)]
        self.assertEqual(delays, [0.0, 1.0, 0.0, 0.2])

    def test_replay_invocations_have_distinct_identity_and_explicit_mode(self):
        from mda_emulators.replay_cli import main

        fixture = ROOT.parent / "projections/realtime/recorded_observed_events.jsonl"
        run_ids = []
        for _ in range(2):
            with patch("sys.argv", ["replay", "--input", str(fixture), "--keep-event-times"]), patch(
                "mda_emulators.replay_cli.create_transport"
            ) as create_transport, patch("mda_emulators.replay_cli.time.sleep"), patch("builtins.print"):
                main()
                events = [call.args[1] for call in create_transport.return_value.publish.call_args_list]
                self.assertEqual(len(events), 15)
                self.assertEqual(len({event["simulation_run_id"] for event in events}), 1)
                self.assertTrue(all(event["transport_mode"] == "recorded_replay" for event in events))
                self.assertTrue(all(event["recorded_simulation_run_id"] == "run-streaming-findings-001-replay-01" for event in events))
                run_ids.append(events[0]["simulation_run_id"])
        self.assertNotEqual(*run_ids)

    def test_accelerated_default_replay_has_no_future_event_times(self):
        from mda_emulators.replay_cli import main

        fixture = ROOT.parent / "projections/realtime/recorded_observed_events.jsonl"
        anchor = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
        with patch("sys.argv", ["replay", "--input", str(fixture)]), patch(
            "mda_emulators.replay_cli.create_transport"
        ) as create_transport, patch("mda_emulators.replay_cli.datetime") as clock, patch(
            "mda_emulators.replay_cli.time.sleep"
        ), patch("builtins.print"):
            clock.now.return_value = anchor
            main()
            events = [call.args[1] for call in create_transport.return_value.publish.call_args_list]
        event_times = [datetime.fromisoformat(event["event_time_utc"].replace("Z", "+00:00")) for event in events if event["event_time_utc"].endswith("Z")]
        self.assertEqual(max(event_times), anchor)
        self.assertEqual((max(event_times) - min(event_times)).total_seconds(), 305)
        self.assertEqual(events[0]["recorded_event_time_utc"], "2026-09-01T14:00:00Z")


if __name__ == "__main__":
    unittest.main()