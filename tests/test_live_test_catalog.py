import base64
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "fabric-demos/04-real-time-ingestion/scripts"
SPEC = importlib.util.spec_from_file_location("publish_live_test_catalog", SCRIPTS / "publish_live_test_catalog.py")
catalog = importlib.util.module_from_spec(SPEC)
with patch.object(sys, "path", [str(SCRIPTS), *sys.path]):
    SPEC.loader.exec_module(catalog)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.content = catalog.dashboard()
        queries = {query["id"]: query["text"] for query in self.content["queries"]}
        self.queries = {tile["title"]: queries[tile["queryRef"]["queryId"]]
                        for tile in self.content["tiles"]}

    def test_deterministic_pure_builder_and_template_isolation(self):
        original = copy.deepcopy(catalog._TEMPLATE)
        with patch.object(catalog.publish_live_test, "dashboard", side_effect=AssertionError("I/O")), \
                patch.object(catalog.publish_live_test, "api", side_effect=AssertionError("Cloud")), \
                patch.object(Path, "read_text", side_effect=AssertionError("Read")), \
                patch.object(Path, "write_text", side_effect=AssertionError("Write")):
            self.assertEqual(catalog.dashboard(), self.content)
            changed = catalog.dashboard()
            changed["tiles"][0]["visualOptions"]["table__enableRenderLinks"] = False
            changed["dataSources"][0]["database"] = "changed"
            self.assertEqual(catalog.dashboard(), self.content)
        self.assertEqual(catalog._TEMPLATE, original)
        self.assertEqual(self.content["autoRefresh"], original["autoRefresh"])
        self.assertEqual(self.content["changeDetection"], original["changeDetection"])

    def test_schema_pages_and_unique_bindings(self):
        catalog.validate_definition(self.content)
        self.assertEqual(self.content["schema_version"], 82)
        self.assertEqual([page["name"] for page in self.content["pages"]], ["Catalog", "Run History"])
        self.assertEqual(set(self.queries), {"Assets", "Access and Review", "Run History", "Retained Evidence"})
        all_ids = [item["id"] for key in ("pages", "tiles", "queries") for item in self.content[key]]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(self.content["parameters"], [])
        self.assertEqual(self.content["baseQueries"], [])
        for query in self.content["queries"]:
            self.assertEqual(query["usedVariables"], [])
            self.assertNotRegex(query["text"], r"_startTime|_endTime|_asset|_run")
        source = self.content["dataSources"][0]
        self.assertEqual(source["database"], catalog.publish_live_test.DATABASE)
        self.assertEqual(source["databaseArtifactId"], catalog.publish_live_test.DATABASE)
        self.assertEqual(source["workspace"], catalog.publish_live_test.WORKSPACE)
        self.assertEqual(source["clusterUri"], catalog.publish_live_test.CLUSTER)

    def test_native_tables_links_and_nonoverlapping_layouts(self):
        for tile in self.content["tiles"]:
            self.assertEqual(tile["visualType"], "table")
            self.assertTrue(tile["visualOptions"]["table__enableRenderLinks"])
            self.assertEqual(tile["visualOptions"]["crossFilter"], [])
            self.assertEqual(tile["visualOptions"]["drillthrough"], [])
        for page in self.content["pages"]:
            layouts = [tile["layout"] for tile in self.content["tiles"] if tile["pageId"] == page["id"]]
            self.assertEqual(len(layouts), 2)
            self.assertLessEqual(layouts[0]["y"] + layouts[0]["height"], layouts[1]["y"])

    def test_actual_configured_asset_not_fixture_catalog(self):
        query = self.queries["Assets"]
        for value in ("target-01", "job-mda-live-test", "live-test-v2", catalog.IMAGE_DIGEST,
                      "2026-09-18", "Configured deployment; not live query", "UNASSIGNED",
                      "NOT_REVIEWED", "NOT_CATALOG_ISSUED", "visualization", "true"):
            self.assertIn(value, query)
        self.assertNotRegex(query, r"fixture|placeholder|normal-collection|4fb31de3")
        self.assertIn("join kind=leftouter", query)
        self.assertIn("arg_max(ReceivedAt, Run) by Vehicle", query)
        self.assertIn("LastReceivedUTC=ReceivedAt, LatestRun=Run", query)
        self.assertNotIn("coalesce", query)
        self.assertNotIn(catalog.VERIFIED_RUN, query)

    def test_only_live_target_observations_and_no_fabricated_status(self):
        for title in ("Assets", "Run History"):
            query = self.queries[title]
            self.assertIn("LiveTargetEvents()", query)
            self.assertIn("ReceivedAt > ago(7d) and ReceivedAt <= now()", query)
            self.assertNotRegex(query, r"AzureSucceeded|COMPLETE|Succeeded|union|230|200")
        history = self.queries["Run History"]
        for fragment in ("by Run, Vehicle", "FirstEventUTC=min(EventTime)", "LastEventUTC=max(EventTime)",
                         "FirstReceivedUTC=min(ReceivedAt)", "LastReceivedUTC=max(ReceivedAt)",
                         "ReceivedSamples=count()", "countif(Channel == 'tspi')",
                         "countif(Channel == 'temperature')", "countif(Channel == 'error')"):
            self.assertIn(fragment, history)
        text = "\n".join(self.queries.values())
        self.assertNotRegex(text, r"RawIntegratedTestEvents|CanonicalIntegratedTestEvents|EvidenceReplay|TestSourceCoverage")
        self.assertEqual(text.count("LiveTargetEvents()"), 2)

    def test_retained_evidence_exact_single_verified_snapshot(self):
        verification = (ROOT / "DEMO_BRIEF.md").read_text()
        query = self.queries["Retained Evidence"]
        rows = json.loads("[" + query.split(")[\n    ", 1)[1].rsplit("\n]", 1)[0] + "]")
        columns = [column.strip().split(":")[0] for column in query.split(")[", 1)[0][len("datatable("):].split(",")]
        self.assertEqual(len(rows), len(columns))
        evidence = dict(zip(columns, rows))
        for value in (catalog.VERIFIED_RUN, catalog.EXECUTION, catalog.BUNDLE_SHA256,
                      catalog.IMAGE_DIGEST, catalog.LAKEHOUSE):
            self.assertIn(value, verification)
        self.assertEqual(evidence["Run"], catalog.VERIFIED_RUN)
        self.assertEqual(evidence["Execution"], "job-mda-live-test-b6ut3my")
        self.assertEqual(evidence["ReceivedSamplesSnapshot"], 230)
        self.assertEqual([evidence[key] for key in ("TSPISnapshot", "TemperatureSnapshot", "ErrorSnapshot")], [200, 20, 10])
        self.assertEqual(evidence["RetainedFilesSnapshot"], 5)
        self.assertEqual(evidence["Seed"], 42)
        self.assertEqual(evidence["DurationOverrideSeconds"], 10)
        self.assertEqual(evidence["AzureResultSnapshot"], "Succeeded")
        self.assertEqual(evidence["SnapshotDate"], "2026-09-18")
        self.assertEqual(evidence["BundleURI"], catalog.BUNDLE_URI)
        self.assertIn("not live query", evidence["Provenance"])
        self.assertNotIn("LiveTargetEvents()", query)
        self.assertIn("not full payloads", evidence["Limits"])
        self.assertIn("QUERY_FAILED", evidence["Limits"])

    def test_exact_link_routes_without_handoff_parameters(self):
        notebook = urlsplit(catalog.NOTEBOOK_URL)
        self.assertEqual(notebook.scheme, "https")
        self.assertEqual(notebook.netloc, "app.fabric.microsoft.com")
        self.assertEqual(notebook.path, f"/groups/{catalog.publish_live_test.WORKSPACE}/synapsenotebooks/0025467b-0c80-4b3d-ae03-241016221e19")
        self.assertEqual(notebook.path, notebook.path.lower())
        self.assertEqual(notebook.query, "")
        self.assertIn(catalog.NOTEBOOK_URL, self.queries["Assets"])
        bundle = urlsplit(catalog.BUNDLE_URI)
        self.assertEqual(bundle.scheme, "https")
        self.assertEqual(bundle.netloc, "onelake.dfs.fabric.microsoft.com")
        self.assertTrue(bundle.path.endswith(f"/{catalog.VERIFIED_RUN}/{catalog.BUNDLE_SHA256}/bundle.json"))
        self.assertRegex(catalog.BUNDLE_SHA256, r"^[0-9a-f]{64}$")
        self.assertRegex(catalog.IMAGE_DIGEST, r"^sha256:[0-9a-f]{64}$")

    def test_review_access_and_legacy_provenance_are_not_approval(self):
        access = self.queries["Access and Review"]
        for value in ("UNASSIGNED", "NOT_REVIEWED", "NOT_CATALOG_ISSUED", "not approved",
                      "allow/deny", "UNVERIFIED", "NOT_IMPLEMENTED"):
            self.assertIn(value, access)
        self.assertIn("'NOT_CATALOG_ISSUED', 'UNVERIFIED'", self.queries["Run History"])
        self.assertIn("Return to this dashboard manually", catalog.__doc__)

    def test_validation_rejects_bad_references_variables_and_ids(self):
        for corruption in ("page", "query", "source", "variable", "duplicate", "parameter"):
            with self.subTest(corruption=corruption):
                content = copy.deepcopy(self.content)
                if corruption == "page":
                    content["tiles"][0]["pageId"] = "missing"
                elif corruption == "query":
                    content["tiles"][0]["queryRef"]["queryId"] = "missing"
                elif corruption == "source":
                    content["queries"][0]["dataSource"]["dataSourceId"] = "missing"
                elif corruption == "variable":
                    content["queries"][0]["usedVariables"] = ["_run"]
                elif corruption == "duplicate":
                    content["queries"][1]["id"] = content["queries"][0]["id"]
                else:
                    content["parameters"] = [{"name": "unsupported"}]
                with self.assertRaises(ValueError):
                    catalog.validate_definition(content)

    def test_default_and_explicit_validation_never_publish_or_call_cloud(self):
        for arguments in ([], ["validate"]):
            with self.subTest(arguments=arguments), \
                    patch.object(catalog.publish_live_test, "publish_item", side_effect=AssertionError("Publish")), \
                    patch.object(catalog.publish_live_test, "api", side_effect=AssertionError("Cloud")), \
                    patch.object(catalog.publish_live_test.subprocess, "check_output", side_effect=AssertionError("Process")), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(catalog.main(arguments), 0)
                self.assertEqual(json.loads(output.getvalue())["status"], "validated_locally")

    def test_publish_only_additional_dashboard_and_202_stays_pending(self):
        for status_code, expected in ((200, "definition_published"), (201, "definition_published"), (202, "pending")):
            with self.subTest(status_code=status_code), \
                    patch.object(catalog.publish_live_test, "publish_item", return_value={"status_code": status_code}) as publish, \
                    patch.object(catalog.publish_live_test, "api", side_effect=AssertionError("Direct API")), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(catalog.main(["publish"]), 0)
                publish.assert_called_once()
                name, kind, definition = publish.call_args.args
                self.assertEqual(name, "Live Test - Catalog and Run History")
                self.assertEqual(kind, "KQLDashboard")
                self.assertEqual(len(definition["parts"]), 1)
                part = definition["parts"][0]
                self.assertEqual(part["path"], "RealTimeDashboard.json")
                self.assertEqual(part["payloadType"], "InlineBase64")
                self.assertEqual(json.loads(base64.b64decode(part["payload"])), self.content)
                result = json.loads(output.getvalue())
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["browserVerification"], "NOT_PERFORMED")
                self.assertEqual(result["selectedAssetHandoff"], "NOT_IMPLEMENTED")

    def test_unsuccessful_publication_not_reported_as_success(self):
        with patch.object(catalog.publish_live_test, "publish_item", return_value={"status_code": 500}), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(RuntimeError, "500"):
                catalog.main(["publish"])
            self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()