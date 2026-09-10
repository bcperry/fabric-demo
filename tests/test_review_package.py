import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "review_package", ROOT / "shared/integrated-test-data/scripts/build_review_package.py"
)
review_package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review_package)


class ReviewPackageTests(unittest.TestCase):
    def test_raw_bytes_and_counts_reconcile(self):
        package = review_package.build_package()
        self.assertEqual(package["source"]["sha256"], hashlib.sha256(review_package.EVENTS.read_bytes()).hexdigest())
        self.assertEqual(package["counts"], {
            "raw_records": 15, "admitted_records_including_duplicates": 14,
            "canonical_events": 13, "duplicate_records": 1, "rejected_records": 1,
        })
        self.assertEqual(package["duplicates"][0]["source_lines"], [7, 8])
        self.assertEqual(package["rejected"][0]["source_line"], 15)

    def test_truncated_window_does_not_infer_missing_acknowledgment(self):
        package = review_package.build_package()
        observation = package["follow_on_observations"][0]
        self.assertEqual(observation["observation"], "UNDETERMINED")
        self.assertEqual(observation["due_utc"], "2026-09-01T14:05:25Z")
        self.assertEqual(package["clock"]["last_recorded_event_utc"], "2026-09-01T14:05:05Z")

    def test_evidence_is_not_automatically_approved(self):
        package = review_package.build_package()
        self.assertEqual(package["review"]["status"], "PENDING_HUMAN_REVIEW")
        self.assertIsNone(package["review"]["reviewer"])
        self.assertIsNone(package["review"]["approved_at_utc"])
        self.assertEqual(package, review_package.build_package())

    def test_envelope_admission_cases(self):
        valid = {"event_id": "event-1", "event_type": "command.integration", "site_id": "site-1", "source_system": "DEMO", "source_instance_id": "demo-1", "event_time_utc": "2026-09-01T14:00:00Z"}
        self.assertEqual(review_package.envelope_issue(valid), "")
        self.assertEqual(review_package.envelope_issue({**valid, "source_system": ""}), "MISSING_SOURCE_SYSTEM")
        for timestamp in ("2026-02-30T14:00:00Z", "2026/09/01 14:00:00", None):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(review_package.envelope_issue({**valid, "event_time_utc": timestamp}), "INVALID_EVENT_TIME")

    def test_rules_change_also_changes_package_identity(self):
        original = review_package.build_package()
        rules = json.loads(review_package.RULES.read_text())
        rules["expected_follow_on_events"][0]["due_in_seconds"] = 120
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(json.dumps(rules))
            changed = review_package.build_package(rules_path=path)
        self.assertEqual(original["source"]["sha256"], changed["source"]["sha256"])
        self.assertNotEqual(original["package_id"], changed["package_id"])
        self.assertEqual(changed["follow_on_observations"][0]["observation"], "NOT_OBSERVED_IN_RECORDED_WINDOW")
        self.assertEqual(changed["clock"]["capture_cutoff"], "NOT_INDEPENDENTLY_VERIFIED")

    def test_modified_input_changes_identity_and_mixed_scope_is_rejected(self):
        original = review_package.build_package()
        records = [json.loads(line) for line in review_package.EVENTS.read_text().splitlines()]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            records[0]["review_note"] = "Changed bytes"
            path.write_text("\n".join(json.dumps(record) for record in records))
            changed = review_package.build_package(path)
            self.assertNotEqual(original["package_id"], changed["package_id"])
            records[0]["simulation_run_id"] = "another-run"
            path.write_text("\n".join(json.dumps(record) for record in records))
            with self.assertRaisesRegex(ValueError, "One explicit scenario"):
                review_package.build_package(path)


if __name__ == "__main__":
    unittest.main()