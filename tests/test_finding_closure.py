import copy
from pathlib import Path
import sys
import subprocess
import unittest


DIRECTORY = Path(__file__).resolve().parents[1] / "fabric-demos/06-ai-data-agent"
sys.path.insert(0, str(DIRECTORY))
from finding_closure import build_finding, validate_transition
from publish_review_source import build_record


class FindingClosureTests(unittest.TestCase):
    def setUp(self):
        self.record = build_record()
        self.finding = build_finding(self.record)

    def test_link_uses_exact_rejected_record(self):
        self.assertEqual(self.finding["test_event_id"], "test-streaming-findings-001")
        self.assertEqual(self.finding["source_line"], 15)
        self.assertEqual(self.finding["event_id"], "malformed-event-001")
        self.assertFalse(self.finding["execution_authorization"])

    def test_cross_event_evidence_is_rejected(self):
        record = copy.deepcopy(self.record)
        record["TestEventId"] = "another-event"
        with self.assertRaises(ValueError):
            build_finding(record)

    def test_close_requires_matching_package_and_review(self):
        for package_id, human in (("other-package", True), (self.finding["package_id"], False)):
            with self.subTest(package=package_id, human=human), self.assertRaises(ValueError):
                validate_transition(self.finding, package_id, "ACCEPT_EVIDENCE", "Inspected", human)
        with self.assertRaises(ValueError):
            validate_transition(self.finding, self.finding["package_id"], "CLOSE_FINDING", "Inspected", True)

    def test_accepted_evidence_can_close_once(self):
        package_id = self.finding["package_id"]
        self.finding["status"] = validate_transition(self.finding, package_id, "ACCEPT_EVIDENCE", "Quarantine retained", True)
        self.finding["status"] = validate_transition(self.finding, package_id, "CLOSE_FINDING", "Disposition accepted", True)
        self.assertEqual(self.finding["status"], "CLOSED")
        with self.assertRaises(ValueError):
            validate_transition(self.finding, package_id, "CLOSE_FINDING", "Again", True)

    def test_requested_changes_block_closure(self):
        package_id = self.finding["package_id"]
        self.finding["status"] = validate_transition(self.finding, package_id, "REQUEST_CHANGES", "Need another review", True)
        with self.assertRaises(ValueError):
            validate_transition(self.finding, package_id, "CLOSE_FINDING", "Not accepted", True)

    def test_cli_dry_run_rejects_unreviewed_decision(self):
        result = subprocess.run([sys.executable, str(DIRECTORY / "finding_closure.py"), "CLOSE_FINDING"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("actual human source review", result.stderr)