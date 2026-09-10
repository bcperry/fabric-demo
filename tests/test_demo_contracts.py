from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
PRETEST = ROOT / "fabric-demos/03-star-schema-bi/fabric-items"
MODEL = PRETEST / "MDA Pre-Test Readiness.SemanticModel/definition"
REPORT = PRETEST / "MDA Pre-Test Readiness and Data Trust.Report/definition"
STREAMING = ROOT / "fabric-demos/04-real-time-ingestion/fabric-items"
KQL = STREAMING / "kqldb_mda_test.KQLDatabase/DatabaseSchema.kql"


class ReportContractTests(unittest.TestCase):
    def test_ml_partitions_match_schema_less_onelake_tables(self):
        model = ROOT / "fabric-demos/05-ml-models/fabric-items/MDA Readiness Model Governance.SemanticModel/definition"
        for table in ("gold_governed_readiness_scores", "gold_readiness_drift_summary"):
            with self.subTest(table=table):
                text = (model / f"tables/{table}.tmdl").read_text()
                partition = text.split(f"partition {table} = entity", 1)[1]
                self.assertIn(f"entityName: {table}", partition)
                self.assertIn("expressionSource: 'DirectLake - IntegratedTestLakehouse'", partition)
                self.assertNotIn("schemaName:", partition)

    def test_rank_measures_do_not_resurrect_filtered_rows(self):
        for table, measure in (("gold_mirror_casework", "Risk Decision Order"), ("gold_mirror_site_locations", "Site Risk Decision Order")):
            text = (MODEL / f"tables/{table}.tmdl").read_text()
            expression = next(line for line in text.splitlines() if f"measure '{measure}'" in line)
            self.assertTrue(expression.endswith("BLANK())"), expression)

    def test_review_summary_does_not_authorize_execution(self):
        model = (MODEL / "tables/gold_mirror_casework.tmdl").read_text()
        summary = model.split("measure 'Director Recommendation'", 1)[1].split(
            "measure 'Decision Scope Banner'", 1
        )[0]
        self.assertIn("[Mirrored Active Findings]", summary)
        self.assertNotIn("[Missing Feeds]", summary)
        self.assertNotIn("[Constrained Systems]", summary)
        self.assertIn("approval and completeness not established", summary)
        self.assertNotIn("PROCEED", summary)
        self.assertNotIn("authorized", summary.lower())

    def test_site_filters_have_a_casework_relationship(self):
        relationships = (MODEL / "relationships.tmdl").read_text()
        relationship = relationships.split("relationship MirrorSite_Casework", 1)[1].split(
            "relationship ", 1
        )[0]
        self.assertIn("fromColumn: gold_mirror_casework.site_id", relationship)
        self.assertIn("toColumn: gold_mirror_site_locations.site_id", relationship)
        self.assertIn("crossFilteringBehavior: oneDirection", relationship)

    def test_report_json_and_evidence_labels(self):
        for path in REPORT.rglob("*.json"):
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text()
                json.loads(text)
                self.assertNotIn("AUTHORITATIVE/COMPLETE", text)
                self.assertNotIn("Latest closure evidence", text)
                self.assertNotIn("EXECUTION NOT AUTHORIZED", text)
                self.assertNotIn("Maintain HOLD", text)
                self.assertNotIn("Decision required today", text)
                self.assertNotIn("Top 3 of 4 Critical/High risks", text)


class AnswerAcceptanceTests(unittest.TestCase):
    def test_ontology_static_bindings_and_archive_match(self):
        directory = ROOT / "fabric-demos/06-ai-data-agent/Ontology"
        source = directory / "package-src/binding/binding_entity_types.csv"
        with source.open() as stream:
            bindings = list(csv.DictReader(stream))
        with (directory / "package-src/definition/entity_types.csv").open() as stream:
            definitions = {
                (row["EntityTypeName"], row["PropertyName"]): row
                for row in csv.DictReader(stream)
            }
        self.assertTrue(bindings)
        for row in bindings:
            definition = definitions[(row["EntityTypeName"], row["PropertyName"])]
            for field in ("IsIdentifier", "IsDisplayName", "IsTimeseries"):
                self.assertEqual(row[field].lower(), definition[field].lower())
            if row["DataBindingType"] == "TimeSeries":
                self.assertTrue(
                    definition["IsIdentifier"].lower() == "true"
                    or definition["IsTimeseries"].lower() == "true"
                )
        for entity in {row["EntityTypeName"] for row in bindings}:
            with self.subTest(entity=entity):
                static_tables = {
                    row["SourceTableName"]
                    for row in bindings
                    if row["EntityTypeName"] == entity and row["DataBindingType"] == "NonTimeSeries"
                }
                self.assertEqual(len(static_tables), 1)
        relationships = list(csv.DictReader((directory / "package-src/binding/binding_relationship_types.csv").read_text().splitlines()))
        for entity, table in (("Observation", "fact_sensor_observation"), ("CommandEvent", "fact_command_event")):
            identity = next(row for row in bindings if row["EntityTypeName"] == entity and row["DataBindingType"] == "NonTimeSeries")
            self.assertEqual(identity["SourceTableName"], table)
            self.assertEqual(identity["BindingSourceColumnName"], "event_id")
            relationship = next(row for row in relationships if row["SourceEntityTypeName"] == entity)
            self.assertEqual(relationship["SourceTableName"], table)
            self.assertEqual(relationship["SourceKeyColumnNames"], "event_id")
        with ZipFile(directory / "mda_test_ontology.iq") as archive:
            for path in (directory / "package-src").rglob("*.csv"):
                self.assertEqual(archive.read(path.relative_to(directory / "package-src").as_posix()), path.read_bytes())

    def test_kusto_tables_use_the_live_selection_hierarchy(self):
        path = ROOT / "fabric-demos/06-ai-data-agent/fabric-items/MDA Evidence Review Agent.DataAgent/Files/Config/draft/kusto-kqldb_mda_test/datasource.json"
        source = json.loads(path.read_text())
        groups = {element["type"]: element for element in source["elements"]}
        self.assertEqual(set(groups), {"table_grouping", "function_grouping", "shortcut_grouping", "materialized_view_grouping"})
        grouping = groups["table_grouping"]
        self.assertEqual(grouping["display_name"], "Tables")
        tables = {
            element["display_name"]: element
            for group in groups.values()
            for element in group["children"]
            if element["is_selected"]
        }
        expected_columns = {
            "EvidenceReviewContext": {
                "PackageId", "TestEventId", "SourcePath", "Package", "RawRecords", "Rules",
                "ReferenceDocumentId", "ReferenceSourcePath", "ReferenceContentSha256",
                "ReferenceContent", "ReferenceLimitations", "ContextLimitations", "Review",
                "Limitations", "RecordedClock", "FollowOnObservations", "SyntheticRuleNotice",
                "Counts", "Source",
            },
        }
        self.assertEqual(set(tables), set(expected_columns))
        for name, columns in expected_columns.items():
            with self.subTest(table=name):
                table = tables[name]
                self.assertEqual(table["type"], "kusto.table")
                self.assertTrue(table["is_selected"])
                self.assertEqual({column["display_name"] for column in table["children"]}, columns)
                for column in table["children"]:
                    self.assertEqual(column["type"], "kusto.column")
                    self.assertTrue(column["is_selected"])

    def test_walkthrough_links_resolve(self):
        for relative in (
            "DEMO_BUILD_PLAN.md", "DEMO_WALKTHROUGH.md", "README.md",
            "fabric-demos/03-star-schema-bi/DEMO_SCRIPT.md",
            "fabric-demos/04-real-time-ingestion/DEMO_SCRIPT.md",
            "fabric-demos/04-real-time-ingestion/README.md",
            "fabric-demos/06-ai-data-agent/DEMO_SCRIPT.md",
            "fabric-demos/06-ai-data-agent/README.md",
            "shared/integrated-test-data/README.md",
            "shared/integrated-test-data/projections/realtime/QUICK_LOOK.md",
        ):
            path = ROOT / relative
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" not in target:
                    with self.subTest(document=relative, target=target):
                        self.assertTrue((path.parent / unquote(target.split("#", 1)[0])).exists())

    def test_cases_have_existing_sources_and_explicit_assertions(self):
        suite = json.loads((ROOT / "fabric-demos/06-ai-data-agent/ANSWER_ACCEPTANCE.json").read_text())
        identifiers = [case["id"] for case in suite["cases"]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertIn(suite["execution_status"], {
            "NOT_RUN", "BLOCKED", "TECHNICALLY_VERIFIED_PENDING_HUMAN_REVIEW"
        })
        if suite["execution_status"] == "BLOCKED":
            self.assertTrue(suite["execution_evidence"]["agent_id"])
            self.assertTrue(suite["execution_evidence"]["response"])
            self.assertFalse(suite["execution_evidence"]["citations_resolved"])
        if suite["execution_status"] == "TECHNICALLY_VERIFIED_PENDING_HUMAN_REVIEW":
            evidence = suite["execution_evidence"]
            self.assertEqual(evidence["human_review"], "NOT_PERFORMED")
            self.assertTrue(evidence["citations_resolved"])
            self.assertTrue(evidence["citation_resolution_mode"])
            self.assertEqual([result["id"] for result in evidence["case_results"]], identifiers)
            self.assertTrue(all(result["result"] == "OBSERVED_ASSERTIONS_MET"
                                for result in evidence["case_results"]))
            capture = json.loads((ROOT / evidence["response_capture"]).read_text())
            self.assertEqual(capture["deployment_operation"], evidence["deployment_operation"])
            self.assertEqual([answer["question"] for answer in capture["answers"]],
                             [case["question"] for case in suite["cases"]])
            self.assertTrue(all("Response time:" in answer["response"]
                                for answer in capture["answers"]))
        for case in suite["cases"]:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["required_assertions"])
                self.assertTrue(case["fail_conditions"])
                for source in case["sources"]:
                    self.assertTrue((ROOT / source).is_file(), source)


class StreamingContractTests(unittest.TestCase):
    def test_dashboard_queries_use_the_selected_window(self):
        path = STREAMING / "MDA Live Test Control.KQLDashboard/RealTimeDashboard.json"
        dashboard = json.loads(path.read_text())
        query_ids = {query["id"] for query in dashboard["queries"]}
        for query in dashboard["queries"]:
            with self.subTest(query=query["id"]):
                self.assertEqual(set(query["usedVariables"]), {"_startTime", "_endTime"})
                self.assertIn("_startTime", query["text"])
                self.assertIn("_endTime", query["text"])
                self.assertNotIn("datetime(2026-01-01)", query["text"])
        for tile in dashboard["tiles"]:
            if "queryRef" in tile:
                self.assertIn(tile["queryRef"]["queryId"], query_ids)
        self.assertNotIn("LIVE EVENTHOUSE", path.read_text())

    def test_admission_and_rejection_share_one_classifier(self):
        schema = KQL.read_text()
        for name in ("SensorObservation", "CommandIntegration", "SystemStatus", "TestMarker"):
            with self.subTest(projection=name):
                body = schema.split(f"Expand{name}() {{", 1)[1].split("\n}", 1)[0]
                self.assertIn("AcceptedIntegratedTestEvents()", body)
                self.assertNotIn("RawIntegratedTestEvents", body)
        rejected = schema.split("ValidateIntegratedTestEvents() {", 1)[1].split("\n}", 1)[0]
        self.assertIn("ClassifyIntegratedTestEvents(RawIntegratedTestEvents)", rejected)
        self.assertIn("where isnotempty(reason_code)", rejected)
        classifier = schema.split("ClassifyIntegratedTestEvents(rows:", 1)[1].split("\n}", 1)[0]
        self.assertNotIn("ingestion_time()", classifier)
        self.assertEqual(schema.count("'MISSING_SOURCE_SYSTEM',"), 2)

    def test_canonical_view_retains_run_identity_and_receipt_clock(self):
        schema = KQL.read_text()
        setup = (KQL.parent / "ReceiptClockSetup.kql").read_text()
        self.assertIn("policy ingestiontime true", setup)
        self.assertNotIn("policy ingestiontime", schema)
        self.assertIn("ReceivedAt=ingestion_time()", schema)
        self.assertIn("arg_min(ReceivedAt, *) by Scenario, Run, event_id", schema)
        self.assertIn("EventTime >= startTime and EventTime < endTime", schema)

    def test_source_coverage_keeps_unobserved_declarations(self):
        schema = KQL.read_text()
        self.assertIn("mv-expand Source=event.expected_sources", schema)
        self.assertIn("join kind=fullouter observed", schema)
        self.assertIn("join kind=inner runWindows", schema)
        self.assertIn("FirstRecordedEvent < endTime and LastRecordedEvent >= startTime", schema)
        self.assertIn("NOT_OBSERVED_IN_WINDOW", schema)
        self.assertIn("UNDECLARED_SOURCE", schema)


if __name__ == "__main__":
    unittest.main()