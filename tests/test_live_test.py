import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


SCRIPTS = Path(__file__).resolve().parents[1] / "fabric-demos/04-real-time-ingestion/scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveTestTests(unittest.TestCase):
    def setUp(self):
        self.launcher = load("start_live_test")
        self.session = MagicMock()
        self.session.headers = {}
        self.session.__enter__.return_value = self.session
        self.session.get.return_value.json.return_value = {"value": []}
        self.session.post.return_value.json.return_value = {"name": "flight"}
        self.session_patch = patch.object(self.launcher.requests, "Session", return_value=self.session)
        self.session_patch.start()
        self.addCleanup(self.session_patch.stop)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_start(self):
        self.launcher.control("start", "test-token")
        self.assertTrue(self.session.post.call_args.args[0].endswith("/start"))
        self.assertEqual(self.session.headers["Authorization"], "Bearer test-token")

    def test_active_execution_prevents_start(self):
        for status in ("Running", "Processing", "Pending"):
            with self.subTest(status=status):
                self.session.get.return_value.json.return_value = {
                    "value": [{"name": "flight", "properties": {"status": status}}]}
                self.launcher.control("start", "test-token")
                self.session.post.assert_not_called()

    def test_status_and_invalid_action_never_mutate(self):
        self.launcher.control("status", "test-token")
        with self.assertRaises(ValueError):
            self.launcher.control("invalid", "test-token")
        self.session.post.assert_not_called()

    def test_stop_only_active_executions(self):
        self.session.get.return_value.json.return_value = {"value": [
            {"name": "active", "properties": {"status": "Running"}},
            {"name": "finished", "properties": {"status": "Succeeded"}}]}
        self.launcher.control("stop", "test-token")
        self.session.post.assert_called_once()
        self.assertTrue(self.session.post.call_args.args[0].endswith("/executions/active/stop"))

    def test_read_failure_prevents_start(self):
        self.session.get.return_value.raise_for_status.side_effect = RuntimeError("denied")
        with self.assertRaises(RuntimeError):
            self.launcher.control("start", "test-token")
        self.session.post.assert_not_called()

    def test_dashboard_bindings(self):
        content = load("publish_live_test").dashboard()
        self.assertEqual(len(content["tiles"]), 6)
        query_ids = {query["id"] for query in content["queries"]}
        self.assertTrue(all(tile["queryRef"]["queryId"] in query_ids for tile in content["tiles"]))
        options = next(tile["visualOptions"] for tile in content["tiles"] if tile["visualType"] == "map")
        self.assertEqual(options["map__geoType"], "numeric")
        self.assertEqual(options["map__latitudeColumn"], "Latitude")
        self.assertEqual(options["map__longitudeColumn"], "Longitude")
        self.assertEqual(options["map__labelColumn"], "MarkerLabel")
        self.assertIsNone(options["map__sizeColumn"])
        self.assertTrue(options["map__sizeDisabled"])
        map_tile = next(tile for tile in content["tiles"] if tile["visualType"] == "map")
        query = next(query["text"] for query in content["queries"]
                 if query["id"] == map_tile["queryRef"]["queryId"])
        self.assertIn("LiveTargetTrail()", query)
        self.assertIn("LiveTargetPosition()", query)
        self.assertIn("arg_max(MarkerSize, *) by Vehicle, Run, EventTime", query)
        self.assertEqual(content["changeDetection"]["fallbackRefreshRate"], "30s")


if __name__ == "__main__":
    unittest.main()