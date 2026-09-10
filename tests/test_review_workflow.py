import importlib.util
from pathlib import Path
import sys
import unittest


DIRECTORY = Path(__file__).resolve().parents[1] / "fabric-demos/06-ai-data-agent"
sys.path.insert(0, str(DIRECTORY))
SPEC = importlib.util.spec_from_file_location("review_workflow", DIRECTORY / "review_workflow.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReviewWorkflowTests(unittest.TestCase):
    def test_request_does_not_require_or_imply_approval(self):
        MODULE.validate_decision("REQUEST_REVIEW", "Source package is ready for inspection", False)

    def test_decision_requires_human_review_and_rationale(self):
        for action in ("ACCEPT_EVIDENCE", "REQUEST_CHANGES"):
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    MODULE.validate_decision(action, "Reviewed", False)
                with self.assertRaises(ValueError):
                    MODULE.validate_decision(action, " ", True)
                MODULE.validate_decision(action, "Inspected source bytes", True)

    def test_execution_authorization_is_not_a_review_action(self):
        with self.assertRaises(ValueError):
            MODULE.validate_decision("AUTHORIZE_EXECUTION", "Not supported", True)


if __name__ == "__main__":
    unittest.main()