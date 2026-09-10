import ast
import importlib.util
import json
from pathlib import Path
import unittest


NOTEBOOK = Path(__file__).resolve().parents[1] / "fabric-demos/03-star-schema-bi/notebooks/03_gold_test_products.ipynb"


@unittest.skipUnless(importlib.util.find_spec("pyspark"), "Run with uv --with pyspark==3.5.7 for Spark regressions")
class CaseworkSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyspark.sql import SparkSession

        cls.spark = SparkSession.builder.master("local[1]").appName("casework-regression").config(
            "spark.ui.enabled", "false"
        ).config("spark.sql.shuffle.partitions", "1").getOrCreate()
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def evaluate_assignment(self, name, **inputs):
        from pyspark.sql import functions as F

        notebook = json.loads(NOTEBOOK.read_text())
        source = next("".join(cell["source"]) for cell in notebook["cells"] if f"{name} = (" in "".join(cell.get("source", [])))
        statement = next(
            statement for statement in ast.parse(source).body
            if isinstance(statement, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in statement.targets)
        )
        context = {"F": F, **inputs}
        exec(compile(ast.Module(body=[statement], type_ignores=[]), str(NOTEBOOK), "exec"), context)
        return context[name]

    def test_next_action_is_one_record_with_stable_ties(self):
        from pyspark.sql import functions as F

        actions = self.spark.createDataFrame([
            ("finding-1", "later", "OPEN", "Later action", "Later owner", "2026-11-03 14:00:00", "2026-11-03 10:00:00"),
            ("finding-1", "earlier-b", "OPEN", "Tied action", "Tied owner", "2026-11-03 12:00:00", "2026-11-03 10:00:00"),
            ("finding-1", "earlier-a", "IN_REVIEW", "Earlier action", "Earlier owner", "2026-11-03 12:00:00", "2026-11-03 10:00:00"),
            ("finding-1", "closed", "COMPLETE", "Closed action", "Closed owner", "2026-11-03 11:00:00", "2026-11-03 10:00:00"),
            ("finding-1", "undated", "OPEN", "Undated action", "Undated owner", None, "2026-11-03 10:00:00"),
            ("finding-2", "complete-only", "COMPLETE", "Complete only", "Other owner", "2026-11-03 11:00:00", "2026-11-03 10:00:00"),
            ("finding-3", "undated-only", "OPEN", "Undated only", "Third owner", None, "2026-11-03 10:00:00"),
        ], "finding_id string, corrective_action_id string, action_status string, action_title string, owner_role string, due_time_utc string, recorded_at_utc string").withColumn("due_time_utc", F.to_timestamp("due_time_utc"))
        findings = self.spark.createDataFrame([("finding-1",), ("finding-2",), ("finding-3",)], ["finding_id"])
        result = {row.finding_id: row for row in self.evaluate_assignment("action_summary_df", mirror_action_df=actions, active_findings_df=findings).collect()}
        selected = result["finding-1"]
        self.assertEqual((selected.next_action, selected.next_action_owner, selected.next_action_status), ("Earlier action", "Earlier owner", "IN_REVIEW"))
        self.assertEqual(selected.next_action_due_utc.hour, 12)
        self.assertEqual(selected.open_action_count, 4)
        self.assertIsNone(result["finding-2"].next_action)
        self.assertEqual(result["finding-3"].next_action_owner, "Third owner")
        self.assertIsNone(result["finding-3"].next_action_due_utc)

    def test_attached_evidence_fields_are_from_the_same_record(self):
        evidence = self.spark.createDataFrame([
            ("finding-1", "evidence-b", "FILES", "TYPE_B", "reference-b", "2026-11-03 11:00:00"),
            ("finding-1", "evidence-a", "FILES", None, "reference-a", "2026-11-03 10:00:00"),
        ], "finding_id string, finding_evidence_id string, evidence_source string, evidence_type string, evidence_reference string, recorded_at_utc string")
        findings = self.spark.createDataFrame([("finding-1",)], ["finding_id"])
        result = self.evaluate_assignment("evidence_summary_df", mirror_evidence_df=evidence, active_findings_df=findings).first()
        self.assertEqual(result.evidence_count, 2)
        self.assertEqual(result.representative_evidence_reference, "reference-a")
        self.assertIsNone(result.representative_evidence_type)


if __name__ == "__main__":
    unittest.main()