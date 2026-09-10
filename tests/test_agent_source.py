import importlib.util
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("agent_source", ROOT / "fabric-demos/06-ai-data-agent/publish_review_source.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AgentSourceTests(unittest.TestCase):
    def test_context_normalizes_only_zero_fractional_utc_seconds(self):
        expected = {"clock": [{"event_time_utc": "2026-09-01T14:00:00Z"}]}
        serialized = {"clock": [{"event_time_utc": "2026-09-01T14:00:00.0000000Z"}]}
        changed = {"clock": [{"event_time_utc": "2026-09-01T14:00:00.0000001Z"}]}
        self.assertEqual(MODULE.comparable_context(expected), MODULE.comparable_context(serialized))
        self.assertNotEqual(MODULE.comparable_context(expected), MODULE.comparable_context(changed))

    def test_context_keeps_independent_source_identity(self):
        context = MODULE.build_context_record()
        recorded = MODULE.build_record()
        reference = MODULE.build_reference_record()
        for name, value in recorded.items():
            self.assertEqual(context[name], value)
        self.assertEqual(context["ReferenceDocumentId"], reference["DocumentId"])
        self.assertEqual(context["ReferenceContent"], reference["Content"])
        self.assertIn("not a verified event relationship", context["ContextLimitations"])
        self.assertEqual(context["Review"]["status"], "PENDING_HUMAN_REVIEW")

    def test_reference_preserves_seed_without_claiming_current_status(self):
        reference = MODULE.build_reference_record()
        content = (ROOT / reference["SourcePath"]).read_bytes()
        self.assertEqual(reference["Content"].encode(), content)
        self.assertEqual(reference["ContentSha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(reference["DocumentId"], "source-reference-" + reference["ContentSha256"])
        self.assertIn("not proof of current deployed status", reference["Limitations"])
        self.assertIn("No verified mapping", reference["Limitations"])

    def test_source_lines_and_counts_remain_traceable(self):
        record = MODULE.build_record()
        self.assertEqual(len(record["RawRecords"]), 15)
        self.assertEqual(record["RawRecords"][6]["source_line"], 7)
        self.assertEqual(record["RawRecords"][7]["source_line"], 8)
        self.assertEqual(record["Package"]["counts"]["canonical_events"], 13)
        self.assertIsNone(record["Package"]["review"]["reviewer"])

    def test_modified_package_cannot_keep_original_identity(self):
        package = json.loads((MODULE.SOURCE / "review_package.json").read_text())
        package["review"]["status"] = "APPROVED"
        with patch.object(Path, "read_text", return_value=json.dumps(package)):
            with self.assertRaisesRegex(ValueError, "identity"):
                MODULE.build_record()


if __name__ == "__main__":
    unittest.main()