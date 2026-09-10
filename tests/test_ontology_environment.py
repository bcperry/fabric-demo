import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ontology_environment", ROOT / "fabric-demos/06-ai-data-agent/provision_environment.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def response(payload, status=200):
    result = MagicMock(status_code=status)
    result.headers = {}
    result.json.return_value = payload
    return result


class OntologyEnvironmentTests(unittest.TestCase):
    def run_setup(self, session, publish=False):
        arguments = ["provision_environment.py"] + (["--publish"] if publish else [])
        with patch.object(MODULE.requests, "Session", return_value=session), \
             patch.object(MODULE.subprocess, "check_output", return_value="test-token\r\n"), \
             patch("sys.argv", arguments), patch("builtins.print"):
            MODULE.main()

    def test_default_does_not_create_environment(self):
        session = MagicMock()
        session.get.return_value = response({"value": []})
        self.run_setup(session)
        session.post.assert_not_called()

    def test_running_publish_is_not_restarted(self):
        session = MagicMock()
        session.get.side_effect = [
            response({"value": [{"id": "environment-id", "displayName": MODULE.NAME}]}),
            response({"properties": {"publishDetails": {"state": "Running"}}}),
        ]
        self.run_setup(session, publish=True)
        session.post.assert_not_called()

    def test_published_dependency_is_idempotent(self):
        session = MagicMock()
        session.get.side_effect = [
            response({"value": [{"id": "environment-id", "displayName": MODULE.NAME}]}),
            response({"properties": {"publishDetails": {"state": "Success"}}}),
            response({"libraries": [{"name": "rdflib", "version": "7.1.4"}]}),
        ]
        self.run_setup(session, publish=True)
        session.post.assert_not_called()

    def test_empty_library_state_uses_raw_upload(self):
        session = MagicMock()
        session.get.side_effect = [
            response({"value": [{"id": "environment-id", "displayName": MODULE.NAME}]}),
            response({"properties": {"publishDetails": {"state": "Success"}}}),
            response({"errorCode": "EnvironmentLibrariesNotFound"}, status=404),
        ]
        session.post.side_effect = [response({}), response({}, status=202)]
        self.run_setup(session, publish=True)
        upload, publish = session.post.call_args_list
        self.assertTrue(upload.args[0].endswith("/staging/libraries/importExternalLibraries"))
        self.assertEqual(upload.kwargs["headers"], {"Content-Type": "application/octet-stream"})
        self.assertNotIn("files", upload.kwargs)
        self.assertTrue(publish.args[0].endswith("/staging/publish?beta=false"))


if __name__ == "__main__":
    unittest.main()