import json
import sys
import unittest
from io import StringIO
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mda_emulators.engine import ScenarioEngine  # noqa: E402
from mda_emulators.scenario import load_scenario  # noqa: E402
from mda_emulators.transports import JsonLinesTransport  # noqa: E402


SCENARIO = (
    ROOT.parent
    / "01-contracts"
    / "examples"
    / "scenario.integrated-defense.json"
)


class ScenarioEngineTests(unittest.TestCase):
    def test_locations_are_deterministic_and_separated(self):
        first = load_scenario(SCENARIO)
        second = load_scenario(SCENARIO)
        first_locations = [site["location"] for site in first["sites"]]
        second_locations = [site["location"] for site in second["sites"]]
        self.assertEqual(first_locations, second_locations)
        self.assertEqual(len({json.dumps(item, sort_keys=True) for item in first_locations}), 3)

    def test_event_sequence_is_deterministic(self):
        start = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)
        scenario = load_scenario(SCENARIO)
        first = list(ScenarioEngine(scenario, start_time=start).generate(130))
        second = list(ScenarioEngine(scenario, start_time=start).generate(130))
        self.assertEqual(first, second)

    def test_extended_source_families_are_present(self):
        scenario = load_scenario(SCENARIO)
        counts = Counter(
            event["event_type"]
            for _, event in ScenarioEngine(scenario).generate(180)
        )
        for event_type in {
            "target.telemetry",
            "interceptor.telemetry",
            "instrumentation.observation",
            "groundtruth.observation",
            "environment.observation",
            "instrumentation.health",
            "network.health",
            "readiness.poll",
            "operator.test_event",
            "safety.status",
        }:
            self.assertGreater(counts[event_type], 0, event_type)

    def test_anomaly_delays_target_integration_event(self):
        scenario = load_scenario(SCENARIO)
        events = list(ScenarioEngine(scenario).generate(121))
        command_events = [
            event
            for topic, event in events
            if topic == "command-integration"
        ]
        delayed = [
            event
            for event in command_events
            if event["source_instance_id"] == "army-int-bravo-01"
            and event["status"] == "DELAYED"
        ]
        self.assertEqual(len(delayed), 1)
        self.assertGreaterEqual(delayed[0]["processing_delay_ms"], 3500)

    def test_all_events_have_required_envelope_fields(self):
        scenario = load_scenario(SCENARIO)
        events = list(ScenarioEngine(scenario).generate(31))
        required = {
            "event_id",
            "event_type",
            "schema_version",
            "scenario_id",
            "run_manifest_id",
            "site_id",
            "source_system",
            "source_instance_id",
            "ordering_key",
            "sequence_number",
            "event_time_utc",
            "ingest_time_utc",
            "startup_seed",
            "classification",
            "location_notice",
            "synthetic",
        }
        for _, event in events:
            self.assertFalse(required.difference(event))
            self.assertEqual(event["classification"], "SYNTHETIC_UNCLASS")
            self.assertTrue(event["synthetic"])

    def test_run_manifest_is_deterministic_and_reports_seeds(self):
        scenario = load_scenario(SCENARIO)
        engine = ScenarioEngine(
            scenario,
            start_time=datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc),
            run_id="run-fixed-001",
        )
        manifest = engine.build_run_manifest(180)
        self.assertEqual(manifest["run_manifest_id"], "run-fixed-001")
        self.assertEqual(len(manifest["sources"]), 19)
        startup_seeds = {item["source_instance_id"]: item["startup_seed"] for item in manifest["sources"]}
        self.assertEqual(len(startup_seeds), len(manifest["sources"]))
        self.assertEqual(manifest, engine.build_run_manifest(180))

    def test_safety_status_remains_advisory(self):
        scenario = load_scenario(SCENARIO)
        events = [
            event
            for _, event in ScenarioEngine(scenario).generate(180)
            if event["event_type"] == "safety.status"
        ]
        self.assertGreater(len(events), 0)
        self.assertTrue(all(event["authority_scope"] == "EVIDENCE_ONLY" for event in events))

    def test_transport_stamps_actual_publish_time(self):
        scenario = load_scenario(SCENARIO)
        _, event = next(ScenarioEngine(scenario).generate(1))
        stream = StringIO()
        transport = JsonLinesTransport(stream)
        transport.publish("system-status", event)
        published = json.loads(stream.getvalue())["event"]
        self.assertNotEqual(published["ingest_time_utc"], event["event_time_utc"])

    def test_runs_have_unique_ids_unless_shared_explicitly(self):
        scenario = load_scenario(SCENARIO)
        first = ScenarioEngine(
            scenario,
            start_time=datetime(2026, 11, 3, 15, 0, 0, tzinfo=timezone.utc),
        )
        second = ScenarioEngine(
            scenario,
            start_time=datetime(2026, 11, 3, 15, 0, 1, tzinfo=timezone.utc),
        )
        shared = ScenarioEngine(scenario, run_id="run-shared-001")
        self.assertNotEqual(first.run_id, second.run_id)
        self.assertEqual(shared.run_id, "run-shared-001")


if __name__ == "__main__":
    unittest.main()
