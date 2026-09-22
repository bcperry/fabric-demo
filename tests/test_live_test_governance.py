import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "live_test_governance",
    ROOT / "fabric-demos/04-real-time-ingestion/scripts/live_test_governance.py",
)
governance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(governance)
PUBLISHER = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REVIEWER = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
NOW = "2026-09-18T01:00:00Z"
CATALOG = ROOT / "shared/integrated-test-data/01-contracts/examples/live-test-catalog.json"


def reference_bytes(duration=1, **changes):
    parameters = {"duration_seconds": duration, "tspi_hz": 20,
                  "temperature_hz": 2, "error_hz": 1}
    parameters.update(changes)
    return json.dumps(parameters, sort_keys=True).encode()


def pin_for(raw):
    digest = hashlib.sha256(raw).hexdigest()
    return {"version": "sha256:" + digest, "sha256": digest}


def refresh(catalog, raw, **changes):
    arguments = {"expected_sha256": pin_for(raw)["sha256"], "publisher_object_id": PUBLISHER,
                 "effective_at": NOW, "received_at": NOW, "max_age_seconds": 60}
    arguments.update(changes)
    return governance.refresh_reference(catalog, raw, **arguments)


def review(catalog, pin, action, actor_id=REVIEWER, **changes):
    arguments = {**pin, "action": action, "actor": {"object_id": actor_id},
                 "recorded_at": NOW, "rationale": "Synthetic local transition test only"}
    arguments.update(changes)
    return governance.review_reference(catalog, **arguments)


def approve(catalog, pin):
    return review(review(catalog, pin, "request_review", PUBLISHER), pin, "accept")


class ReferenceGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.empty = governance.new_reference_catalog("synthetic-parameters")
        self.raw = reference_bytes()
        self.pin = pin_for(self.raw)
        self.catalog = refresh(self.empty, self.raw)

    def test_v1_preserved_v2_promoted_v3_quarantined_without_fixture_overwrite(self):
        fixture_before = CATALOG.read_bytes()
        first = approve(self.catalog, self.pin)
        first = governance.promote_reference(first, **self.pin, recorded_at=NOW)
        before = copy.deepcopy(first)
        second_bytes = reference_bytes(2)
        second_pin = pin_for(second_bytes)
        second = approve(refresh(first, second_bytes), second_pin)
        second = governance.promote_reference(second, **second_pin, recorded_at=NOW)
        third = refresh(second, b'{"duration_seconds":')
        self.assertEqual(first, before)
        self.assertEqual(third["snapshots"][self.pin["version"]], first["snapshots"][self.pin["version"]])
        self.assertEqual(third["promoted"], second_pin)
        self.assertEqual(len(third["snapshots"]), 2)
        self.assertEqual(len(third["quarantine"]), 1)
        self.assertEqual(governance.select_reference(third, now=NOW)["bytes"], second_bytes)
        self.assertEqual(governance.select_reference(third, now=NOW, pin=self.pin)["bytes"], self.raw)
        self.assertEqual(CATALOG.read_bytes(), fixture_before)
        self.assertEqual(self.empty["snapshots"], {})

    def test_corruption_hash_schema_and_finite_bounds(self):
        invalid = [b"not-json", b"\xff", b"[]", b"{}",
                   self.raw.replace(b'"duration_seconds": 1', b'"duration_seconds": 1, "duration_seconds": 2'),
                   reference_bytes(1.5), reference_bytes(extra=1), reference_bytes(tspi_hz=2),
                   reference_bytes(10 ** 1000)]
        for field in governance.PARAMETER_LIMITS:
            for value in (True, 0, -1, float("nan"), float("inf"), "2", 4001):
                invalid.append(reference_bytes(**{field: value}))
        for raw in invalid:
            with self.subTest(raw=raw[:90]):
                result = refresh(self.catalog, raw)
                self.assertEqual(result["snapshots"], self.catalog["snapshots"])
                self.assertEqual(len(result["quarantine"]), 1)
        for digest in ("0" * 64, "invalid", None):
            with self.subTest(digest=digest):
                self.assertEqual(len(refresh(self.catalog, self.raw, expected_sha256=digest)["quarantine"]), 1)

    def test_exact_bytes_versions_and_schema(self):
        snapshot = governance.validate_reference(self.raw, self.pin["sha256"])
        self.assertEqual(snapshot["version"], self.pin["version"])
        self.assertNotEqual(pin_for(self.raw), pin_for(self.raw + b" "))
        self.assertEqual(governance.REFERENCE_SCHEMA["required"], list(governance.PARAMETER_LIMITS))
        self.assertFalse(governance.REFERENCE_SCHEMA["additionalProperties"])
        self.assertEqual(refresh(self.catalog, self.raw), self.catalog)
        with self.assertRaisesRegex(ValueError, "immutable"):
            refresh(self.catalog, self.raw, max_age_seconds=120)

    def test_timestamp_order_awareness_and_age(self):
        for changes in ({"effective_at": "2026-09-18T02:00:00Z"},
                        {"received_at": "2026-09-18T01:00:00"},
                        {"effective_at": "bad"}, {"max_age_seconds": float("nan")},
                        {"max_age_seconds": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                refresh(self.empty, self.raw, **changes)
        equivalent = refresh(self.empty, self.raw, effective_at="2026-09-18T03:00:00+02:00")
        self.assertEqual(equivalent, self.catalog)
        approved = approve(self.catalog, self.pin)
        promoted = governance.promote_reference(approved, **self.pin, recorded_at=NOW)
        governance.select_reference(promoted, now="2026-09-18T01:01:00Z")
        for moment in ("2026-09-18T00:59:59Z", "2026-09-18T01:01:01Z"):
            with self.assertRaises(ValueError):
                governance.select_reference(promoted, now=moment)
        late = refresh(self.empty, self.raw, effective_at="2026-09-18T00:00:00Z")
        late = governance.promote_reference(approve(late, self.pin), **self.pin, recorded_at=NOW)
        with self.assertRaisesRegex(ValueError, "stale"):
            governance.select_reference(late, now=NOW)

    def test_stale_refuses_new_and_requires_explicit_old_replay(self):
        first = governance.promote_reference(approve(self.catalog, self.pin), **self.pin, recorded_at=NOW)
        raw_second = reference_bytes(2)
        second_pin = pin_for(raw_second)
        latest = refresh(first, raw_second, max_age_seconds=3600)
        latest = governance.promote_reference(approve(latest, second_pin), **second_pin, recorded_at=NOW)
        later = "2026-09-18T01:02:00Z"
        with self.assertRaisesRegex(ValueError, "stale"):
            governance.select_reference(latest, now=later, pin=self.pin)
        with self.assertRaises(ValueError):
            governance.select_reference(latest, now=later, allow_stale_replay=True)
        replay = governance.select_reference(latest, now=later, pin=self.pin, allow_stale_replay=True)
        self.assertEqual(replay["bytes"], self.raw)
        self.assertEqual(governance.select_reference(latest, now=later)["bytes"], raw_second)
        with self.assertRaises(ValueError):
            governance.select_reference(first, now=later)
        with self.assertRaises(ValueError):
            governance.select_reference(latest, now=later, pin=pin_for(reference_bytes(99)))

    def test_review_separation_version_isolation_and_immutable_history(self):
        with self.assertRaisesRegex(ValueError, "transition"):
            review(self.catalog, self.pin, "accept")
        pending = review(self.catalog, self.pin, "request_review", PUBLISHER)
        saved = copy.deepcopy(pending)
        for actor_id in (PUBLISHER, PUBLISHER.upper()):
            with self.assertRaisesRegex(ValueError, "publisher"):
                review(pending, self.pin, "accept", actor_id)
        with self.assertRaises(ValueError):
            review(pending, self.pin, "accept", actor="reviewer-name")
        with self.assertRaises(ValueError):
            review(pending, self.pin, "accept", sha256="0" * 64)
        accepted = review(pending, self.pin, "accept")
        self.assertEqual(pending, saved)
        self.assertEqual(len(accepted["reviews"][self.pin["version"]]["history"]), 2)
        accepted["reviews"][self.pin["version"]]["history"][0]["rationale"] = "detached"
        self.assertEqual(pending, saved)
        newer_pin = pin_for(reference_bytes(2))
        newer = refresh(accepted, reference_bytes(2))
        with self.assertRaises(ValueError):
            governance.promote_reference(newer, **newer_pin, recorded_at=NOW)
        rejected = review(review(newer, newer_pin, "request_review"), newer_pin, "reject")
        self.assertEqual(rejected["reviews"][self.pin["version"]]["state"], "APPROVED")
        for action in ("accept", "request_review", "reject"):
            with self.assertRaises(ValueError):
                review(rejected, newer_pin, action)
        with self.assertRaises(ValueError):
            governance.select_reference(rejected, now=NOW, pin=newer_pin, allow_stale_replay=True)

    def test_future_reviews_promotions_and_tampered_bytes_refused(self):
        with self.assertRaises(ValueError):
            review(self.catalog, self.pin, "request_review", recorded_at="2026-09-18T00:00:00Z")
        pending = review(self.catalog, self.pin, "request_review")
        accepted = review(pending, self.pin, "accept", recorded_at="2026-09-18T01:00:10Z")
        with self.assertRaises(ValueError):
            governance.promote_reference(accepted, **self.pin, recorded_at=NOW)
        promoted = governance.promote_reference(accepted, **self.pin, recorded_at="2026-09-18T01:00:20Z")
        for moment in (NOW, "2026-09-18T01:00:15Z"):
            with self.assertRaises(ValueError):
                governance.select_reference(promoted, now=moment)
        promoted["snapshots"][self.pin["version"]]["bytes"] += b" "
        with self.assertRaises(ValueError):
            governance.select_reference(promoted, now="2026-09-18T01:00:30Z")

    def test_tag_override_idempotence_provenance_and_no_classification_updates(self):
        snapshot = self.catalog["snapshots"][self.pin["version"]]
        proposal = governance.propose_tags(snapshot)
        saved = copy.deepcopy(proposal)
        state = governance.apply_tag_proposal(None, proposal, manual_overrides={"rate_profile": "manual"})
        self.assertEqual(state, governance.apply_tag_proposal(state, proposal))
        self.assertEqual(state["source_sha256"], self.pin["sha256"])
        self.assertEqual(state["rule_version"], governance.TAG_RULE_VERSION)
        self.assertEqual(state["tags"]["rate_profile"], "manual")
        self.assertEqual(proposal, saved)
        for key in ("classification", "permissions", "access", "synthetic"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                governance.apply_tag_proposal(state, proposal, manual_overrides={key: "override"})
        with self.assertRaises(ValueError):
            governance.apply_tag_proposal(state, {**proposal, "classification": "UNCLASS"})
        with self.assertRaises(ValueError):
            governance.propose_tags(snapshot, rule_version="unknown.v2")
        other = governance.validate_reference(reference_bytes(2), pin_for(reference_bytes(2))["sha256"])
        with self.assertRaises(ValueError):
            governance.apply_tag_proposal(state, governance.propose_tags(other))

    def test_technical_completion_rate_cohort_wilson_and_zero_eligible(self):
        result = governance.technical_completion_rate(
            ["a", "b", "c", "d", "e"], {"a": "succeeded", "b": "failed", "c": "canceled", "d": "running"})
        self.assertEqual(result["estimate"], 0.5)
        self.assertEqual(result["sample_size"], 2)
        self.assertEqual(result["declared_size"], 5)
        self.assertEqual(result["counts"], {"succeeded": 1, "failed": 1, "canceled": 1, "unknown": 2})
        self.assertAlmostEqual(result["wilson95"][0], 0.09453120573423074)
        self.assertAlmostEqual(result["wilson95"][1], 0.9054687942657693)
        self.assertFalse(result["operational_probability"])
        for declared, outcomes in (([], {}), (["a", "b"], {"a": "canceled"})):
            empty = governance.technical_completion_rate(declared, outcomes)
            self.assertIsNone(empty["estimate"])
            self.assertIsNone(empty["wilson95"])
            self.assertEqual(empty["sample_size"], 0)
        for declared, outcomes in ((["a", "a"], {}), (["a"], {"b": "succeeded"})):
            with self.assertRaises(ValueError):
                governance.technical_completion_rate(declared, outcomes)


if __name__ == "__main__":
    unittest.main()