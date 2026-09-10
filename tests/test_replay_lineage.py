from copy import deepcopy
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fabric-demos/06-ai-data-agent"))
from publish_review_source import build_record
from verify_replay_lineage import verify_payloads


class ReplayLineageTests(unittest.TestCase):
    def test_clock_serialization_does_not_hide_content_changes(self):
        package = build_record()
        events = []
        for row in package["RawRecords"]:
            event = deepcopy(row["record"])
            event["recorded_simulation_run_id"] = event["simulation_run_id"]
            event["simulation_run_id"] = "rehearsal"
            event.update(transport_mode="recorded_replay", replay_speed=10, published_time_utc="2026-09-08T22:00:00Z")
            if event["event_time_utc"].endswith("Z"):
                event["recorded_event_time_utc"] = event["event_time_utc"].replace("Z", ".0000000Z")
                event["event_time_utc"] = "2026-09-08T22:00:00Z"
            events.append(event)
        verify_payloads(package, events)
        events[0]["source_system"] = "CHANGED"
        with self.assertRaises(ValueError):
            verify_payloads(package, events)

    def test_missing_duplicate_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            verify_payloads(build_record(), [])


if __name__ == "__main__":
    unittest.main()