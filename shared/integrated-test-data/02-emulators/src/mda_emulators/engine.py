from __future__ import annotations

import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from .events import create_envelope


TOPICS = {
    "sensor.observation": "sensor-observation",
    "system.status": "system-status",
    "command.integration": "command-integration",
    "sustainment.event": "sustainment",
    "target.telemetry": "target-telemetry",
    "interceptor.telemetry": "interceptor-telemetry",
    "instrumentation.observation": "instrumentation-observation",
    "groundtruth.observation": "ground-truth-observation",
    "environment.observation": "environment-observation",
    "instrumentation.health": "instrumentation-health",
    "network.health": "network-health",
    "readiness.poll": "readiness-poll",
    "operator.test_event": "operator-test-event",
    "safety.status": "safety-status",
}


class ScenarioEngine:
    """Generate a deterministic, finite synthetic event sequence."""

    def __init__(
        self,
        scenario: dict[str, Any],
        *,
        start_time: datetime | None = None,
        run_id: str | None = None,
    ) -> None:
        self.scenario = scenario
        self.start_time = start_time or datetime.now(timezone.utc)
        self.run_id = run_id or (
            f"run-{scenario['scenario_id']}-"
            f"{self.start_time.strftime('%Y%m%dT%H%M%S%fZ')}"
        )
        self.run_manifest_id = self.run_id
        self.rng = random.Random(scenario["seed"])
        self.test_event_id = f"test-{scenario['scenario_id']}"
        self._site_lookup = {site["site_id"]: site for site in scenario["sites"]}
        self._systems = [
            (site, system)
            for site in scenario["sites"]
            for system in site["systems"]
        ]
        self._operational_sources = [
            {
                "site": site,
                "site_id": site["site_id"],
                "source_system": system["system_family"],
                "source_instance_id": system["instance_id"],
                "role": system["role"],
                "event_profile": system["event_profile"],
                "readiness_state": system["sustainment_profile"],
                "source_kind": "operational",
            }
            for site, system in self._systems
        ]
        self._supporting_sources = [
            {
                "site": self._site_lookup[source["site_id"]],
                "site_id": source["site_id"],
                "source_system": source["source_system"],
                "source_instance_id": source["source_instance_id"],
                "role": source["role"],
                "event_profile": source["event_profile"],
                "source_kind": "supporting",
            }
            for source in scenario.get("supporting_sources", [])
        ]
        sustainment_site = self._source_entry_from_id("patriot-bravo-02")["site"]
        self._internal_sources = [
            {
                "site": sustainment_site,
                "site_id": sustainment_site["site_id"],
                "source_system": "SUSTAINMENT",
                "source_instance_id": "sustainment-producer-01",
                "role": "POSTGRES_PROJECTOR_INPUT",
                "event_profile": "NORMAL",
                "source_kind": "internal",
            }
        ]
        self._source_catalog = (
            self._operational_sources + self._supporting_sources + self._internal_sources
        )
        self._startup_seeds = {
            entry["source_instance_id"]: self._derive_startup_seed(
                entry["source_instance_id"]
            )
            for entry in self._source_catalog
        }

    def build_run_manifest(self, duration_seconds: int) -> dict[str, Any]:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        return {
            "schema_version": "1.0.0",
            "manifest_type": "run.manifest",
            "classification": "SYNTHETIC_UNCLASS",
            "scenario_id": self.scenario["scenario_id"],
            "test_event_id": self.test_event_id,
            "simulation_run_id": self.run_id,
            "run_manifest_id": self.run_manifest_id,
            "location_notice": self.scenario["location_notice"],
            "start_time_utc": self.start_time.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "duration_seconds": duration_seconds,
            "time_scale": self.scenario["time_scale"],
            "sources": [
                {
                    "site_id": entry["site_id"],
                    "source_system": entry["source_system"],
                    "source_instance_id": entry["source_instance_id"],
                    "role": entry["role"],
                    "event_profile": entry["event_profile"],
                    "startup_seed": self._startup_seeds[entry["source_instance_id"]],
                    "readiness_state": entry.get("readiness_state"),
                    "location": entry["site"]["location"],
                }
                for entry in self._source_catalog
            ],
            "topics": sorted(set(TOPICS.values())),
        }

    def generate(self, duration_seconds: int = 180) -> Iterator[tuple[str, dict]]:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")

        for offset in range(duration_seconds):
            event_time = self.start_time + timedelta(seconds=offset)
            if offset % 10 == 0:
                yield from self._status_events(offset, event_time)
            if offset >= 15 and offset % 2 == 0:
                yield TOPICS["sensor.observation"], self._sensor_event(
                    offset, event_time
                )
            if offset >= 12 and offset % 3 == 0:
                yield TOPICS["target.telemetry"], self._target_telemetry_event(
                    offset, event_time
                )
            if offset >= 60 and offset % 4 == 0:
                yield TOPICS["interceptor.telemetry"], self._interceptor_telemetry_event(
                    offset, event_time
                )
            if offset >= 12 and offset % 6 == 0:
                yield TOPICS["instrumentation.observation"], self._receiver_observation_event(
                    offset, event_time
                )
                yield TOPICS["groundtruth.observation"], self._ground_truth_event(
                    offset, event_time
                )
            if offset >= 24 and offset % 12 == 0:
                yield TOPICS["instrumentation.observation"], self._optical_observation_event(
                    offset, event_time
                )
            if offset % 30 == 0:
                yield TOPICS["environment.observation"], self._environment_event(
                    offset, event_time
                )
                yield TOPICS["instrumentation.health"], self._instrumentation_health_event(
                    offset, event_time
                )
            if offset in {20, 30, 45, 60, 90, 120}:
                yield from self._command_events(offset, event_time)
            if offset in {0, 75, 135}:
                yield from self._sustainment_events(offset, event_time)
            if offset in {0, 60, 90, 100, 120}:
                yield TOPICS["network.health"], self._network_health_event(
                    offset, event_time
                )
            if offset in {0, 100}:
                yield from self._readiness_poll_events(offset, event_time)
            if offset in {0, 20, 95, 100, 120}:
                yield TOPICS["operator.test_event"], self._operator_test_event(
                    offset, event_time
                )
            if offset in {0, 92, 100, 120}:
                yield TOPICS["safety.status"], self._safety_status_event(
                    offset, event_time
                )

    def _derive_startup_seed(self, source_instance_id: str) -> int:
        key = f"{self.scenario['scenario_id']}|{source_instance_id}|startup"
        return self.scenario["seed"] + (uuid.uuid5(uuid.NAMESPACE_URL, key).int % 100000)

    def _source_entry(
        self, source_system: str, source_instance_id: str | None = None
    ) -> dict[str, Any]:
        for entry in self._source_catalog:
            if entry["source_system"] != source_system:
                continue
            if source_instance_id and entry["source_instance_id"] != source_instance_id:
                continue
            return entry
        raise ValueError(f"Scenario requires a {source_system} source")

    def _source_entry_from_id(self, source_instance_id: str) -> dict[str, Any]:
        for entry in self._operational_sources + self._supporting_sources:
            if entry["source_instance_id"] == source_instance_id:
                return entry
        raise ValueError(f"Scenario requires a source instance named {source_instance_id}")

    def _site_for_family(self, family: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for site, system in self._systems:
            if system["system_family"] == family:
                return site, system
        raise ValueError(f"Scenario requires a {family} instance")

    def _base_envelope(
        self,
        *,
        entry: dict[str, Any],
        event_type: str,
        ordering_key: str,
        sequence_number: int,
        event_time: datetime,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        return create_envelope(
            scenario=self.scenario,
            site_id=entry["site_id"],
            source_system=entry["source_system"],
            source_instance_id=entry["source_instance_id"],
            event_type=event_type,
            ordering_key=ordering_key,
            sequence_number=sequence_number,
            event_time=event_time,
            test_event_id=self.test_event_id,
            simulation_run_id=self.run_id,
            run_manifest_id=self.run_manifest_id,
            startup_seed=self._startup_seeds[entry["source_instance_id"]],
            correlation_id=correlation_id,
            causation_id=causation_id,
        )

    def _track_position(self, offset: int, *, elevation_bias: float = 0.0) -> dict[str, Any]:
        angle = offset / 18
        return {
            "x": round(450 + offset * 2.6, 3),
            "y": round(220 + math.sin(angle) * 18, 3),
            "z": round(90 + elevation_bias + offset * 0.8, 3),
            "coordinate_system": "FICTIONAL_LOCAL_GRID",
        }

    def _sensor_event(self, offset: int, event_time: datetime) -> dict[str, Any]:
        entry = self._source_entry("TPY2")
        sequence = offset // 2
        envelope = self._base_envelope(
            entry=entry,
            event_type="sensor.observation",
            ordering_key="track-synthetic-001",
            sequence_number=sequence,
            event_time=event_time,
            correlation_id="track-synthetic-001",
        )
        envelope.update(
            {
                "track_id": "track-synthetic-001",
                "observation_type": "DETECTION"
                if sequence == 7
                else "TRACK_UPDATE",
                "quality": {
                    "score": round(0.91 + self.rng.uniform(-0.025, 0.025), 4),
                    "freshness_ms": 120 + self.rng.randint(0, 45),
                    "continuity": round(
                        0.97 + self.rng.uniform(-0.015, 0.015), 4
                    ),
                },
                "position": self._track_position(offset),
            }
        )
        return envelope

    def _target_telemetry_event(
        self, offset: int, event_time: datetime
    ) -> dict[str, Any]:
        entry = self._source_entry("TARGET_RANGE")
        sequence = (offset - 12) // 3
        envelope = self._base_envelope(
            entry=entry,
            event_type="target.telemetry",
            ordering_key="track-synthetic-001",
            sequence_number=sequence,
            event_time=event_time,
            correlation_id="track-synthetic-001",
        )
        envelope.update(
            {
                "track_id": "track-synthetic-001",
                "track_role": "TARGET",
                "phase": "INGRESS" if offset < 90 else "TERMINAL",
                "position": self._track_position(offset, elevation_bias=-0.4),
                "velocity": {
                    "x_mps": round(2550 + self.rng.uniform(-40, 40), 3),
                    "y_mps": round(185 + self.rng.uniform(-15, 15), 3),
                    "z_mps": round(-115 + self.rng.uniform(-12, 12), 3),
                },
                "source_clock_offset_ms": 18 + (offset % 5),
            }
        )
        return envelope

    def _interceptor_telemetry_event(
        self, offset: int, event_time: datetime
    ) -> dict[str, Any]:
        entry = self._source_entry("INTERCEPTOR_RANGE")
        sequence = (offset - 60) // 4
        angle = (offset - 60) / 12
        envelope = self._base_envelope(
            entry=entry,
            event_type="interceptor.telemetry",
            ordering_key="track-interceptor-001",
            sequence_number=sequence,
            event_time=event_time,
            correlation_id="track-synthetic-001",
        )
        envelope.update(
            {
                "track_id": "track-interceptor-001",
                "track_role": "INTERCEPTOR",
                "phase": "BOOST" if offset < 84 else "MIDCOURSE",
                "position": {
                    "x": round(390 + (offset - 60) * 2.1, 3),
                    "y": round(180 + math.sin(angle) * 10, 3),
                    "z": round(32 + (offset - 60) * 1.1, 3),
                    "coordinate_system": "FICTIONAL_LOCAL_GRID",
                },
                "update_receipt_state": "EXPECTED_RECEIVED" if offset >= 72 else "PENDING",
                "source_clock_offset_ms": 24 + (offset % 4),
            }
        )
        return envelope

    def _receiver_observation_event(
        self, offset: int, event_time: datetime
    ) -> dict[str, Any]:
        entry = self._source_entry("RANGE_RECEIVER")
        sequence = (offset - 12) // 6
        clock_offset = 42
        sample_state = "NOMINAL"
        if 90 <= offset < 100:
            clock_offset = 265
            sample_state = "CLOCK_SKEW_OBSERVED"
        envelope = self._base_envelope(
            entry=entry,
            event_type="instrumentation.observation",
            ordering_key="track-synthetic-001",
            sequence_number=sequence,
            event_time=event_time,
            correlation_id="track-synthetic-001",
        )
        envelope.update(
            {
                "track_id": "track-synthetic-001",
                "sensor_modality": "RANGE_RECEIVER",
                "measurement_quality": round(0.96 + self.rng.uniform(-0.02, 0.01), 4),
                "position": self._track_position(offset, elevation_bias=-0.2),
                "clock_offset_ms": clock_offset,
                "sample_state": sample_state,
            }
        )
        return envelope

    def _optical_observation_event(
        self, offset: int, event_time: datetime
    ) -> dict[str, Any]:
        entry = self._source_entry("OPTICAL_TRACKER")
        sequence = (offset - 24) // 12
        envelope = self._base_envelope(
            entry=entry,
            event_type="instrumentation.observation",
            ordering_key="track-synthetic-001",
            sequence_number=sequence,
            event_time=event_time,
            correlation_id="track-synthetic-001",
        )
        envelope.update(
            {
                "track_id": "track-synthetic-001",
                "sensor_modality": "OPTICAL_TRACKER",
                "measurement_quality": round(0.9 + self.rng.uniform(-0.03, 0.02), 4),
                "position": self._track_position(offset, elevation_bias=0.1),
                "clock_offset_ms": 12,
                "sample_state": "SPARSE_CONFIRMATION",
            }
        )
        return envelope

    def _ground_truth_event(self, offset: int, event_time: datetime) -> dict[str, Any]:
        entry = self._source_entry("GROUND_TRUTH")
        sequence = (offset - 12) // 6
        envelope = self._base_envelope(
            entry=entry,
            event_type="groundtruth.observation",
            ordering_key="track-synthetic-001",
            sequence_number=sequence,
            event_time=event_time,
            correlation_id="track-synthetic-001",
        )
        envelope.update(
            {
                "track_id": "track-synthetic-001",
                "truth_role": "REFERENCE_TRACK",
                "position": self._track_position(offset, elevation_bias=-0.35),
                "reference_state": "ALIGNED_TO_RANGE_CLOCK",
            }
        )
        return envelope

    def _environment_event(self, offset: int, event_time: datetime) -> dict[str, Any]:
        entry = self._source_entry("ENVIRONMENT")
        sequence = offset // 30
        condition_summary = "NOMINAL"
        if 90 <= offset < 120:
            condition_summary = "TIMING_JITTER_WINDOW"
        envelope = self._base_envelope(
            entry=entry,
            event_type="environment.observation",
            ordering_key=entry["source_instance_id"],
            sequence_number=sequence,
            event_time=event_time,
        )
        envelope.update(
            {
                "condition_id": f"env-window-{sequence:03d}",
                "condition_summary": condition_summary,
                "wind_factor": round(0.22 + self.rng.uniform(-0.02, 0.05), 3),
                "visibility_state": "CLEAR",
                "scenario_effect": "TIMING_JITTER_REVIEW" if condition_summary != "NOMINAL" else "NONE",
            }
        )
        return envelope

    def _status_events(
        self, offset: int, event_time: datetime
    ) -> Iterator[tuple[str, dict]]:
        sequence = offset // 10
        for entry in self._operational_sources:
            profile = entry["event_profile"]
            readiness = entry["readiness_state"]
            health_base = 0.96 if profile == "NORMAL" else 0.78
            envelope = self._base_envelope(
                entry=entry,
                event_type="system.status",
                ordering_key=entry["source_instance_id"],
                sequence_number=sequence,
                event_time=event_time,
            )
            envelope.update(
                {
                    "operating_state": "DEGRADED"
                    if profile == "DEGRADED"
                    else "ACTIVE",
                    "readiness_state": readiness,
                    "health_score": round(
                        health_base + self.rng.uniform(-0.02, 0.02), 4
                    ),
                    "metrics": {
                        "synthetic_load_pct": round(
                            55 + self.rng.uniform(-8, 8), 2
                        ),
                        "synthetic_latency_ms": round(
                            25 + self.rng.uniform(0, 12), 2
                        ),
                    },
                    "contributing_conditions": ["FICTIONAL_PROFILE_" + profile],
                }
            )
            yield TOPICS["system.status"], envelope

    def _instrumentation_health_event(
        self, offset: int, event_time: datetime
    ) -> dict[str, Any]:
        entry = self._source_entry("INSTRUMENTATION_MONITOR")
        sequence = offset // 30
        status = "HEALTHY"
        observed_lag = 28
        issue_profile = "nominal"
        if offset == 90:
            status = "DEGRADED"
            observed_lag = 3550
            issue_profile = "clock_alignment_delay_window"
        elif offset == 120:
            status = "RECOVERED"
            observed_lag = 64
            issue_profile = "post_correction_validation"
        envelope = self._base_envelope(
            entry=entry,
            event_type="instrumentation.health",
            ordering_key=entry["source_instance_id"],
            sequence_number=sequence,
            event_time=event_time,
        )
        envelope.update(
            {
                "component_id": "timing-cell-alpha",
                "status": status,
                "observed_lag_ms": observed_lag,
                "issue_profile": issue_profile,
            }
        )
        return envelope

    def _command_events(
        self, offset: int, event_time: datetime
    ) -> Iterator[tuple[str, dict]]:
        plan = {
            20: ("BATTLE_MANAGEMENT", "TRACK_CORRELATED", None),
            30: ("BATTLE_MANAGEMENT", "SHARED_TRACK_PUBLISHED", None),
            45: ("ARMY_INTEGRATION", "CUE_RECEIVED", None),
            60: ("ARMY_INTEGRATION", "ABSTRACT_ASSIGNMENT", "patriot-bravo-01"),
            90: (
                "ARMY_INTEGRATION",
                "ASSIGNMENT_ACKNOWLEDGED",
                "patriot-bravo-01",
            ),
            120: ("THAAD", "PARTICIPATION_REPORTED", "thaad-charlie-01"),
        }
        family, action, target = plan[offset]
        entry = self._source_entry(family)
        delay = 90 + self.rng.randint(0, 30)
        status = "COMPLETED"
        anomaly = self._active_anomaly(entry["source_instance_id"], offset)
        if anomaly:
            delay += 3_500
            status = "DELAYED"

        envelope = self._base_envelope(
            entry=entry,
            event_type="command.integration",
            ordering_key="track-synthetic-001",
            sequence_number=offset,
            event_time=event_time,
            correlation_id="track-synthetic-001",
        )
        envelope.update(
            {
                "track_id": "track-synthetic-001",
                "action": action,
                "target_instance_id": target,
                "status": status,
                "processing_delay_ms": delay,
                "data_product_version": "1.0",
            }
        )
        yield TOPICS["command.integration"], envelope

    def _sustainment_events(
        self, offset: int, event_time: datetime
    ) -> Iterator[tuple[str, dict]]:
        affected_asset = self._source_entry("PATRIOT", "patriot-bravo-02")
        entry = self._source_entry("SUSTAINMENT")
        actions = {
            0: ("FAULT_RECORDED", "OPEN", "READY", "LIMITED"),
            75: ("WORK_ORDER_OPENED", "IN_PROGRESS", "LIMITED", "MAINTENANCE"),
            135: ("WORK_ORDER_COMPLETED", "COMPLETE", "MAINTENANCE", "READY"),
        }
        action, status, before, after = actions[offset]
        envelope = self._base_envelope(
            entry=entry,
            event_type="sustainment.event",
            ordering_key=affected_asset["source_instance_id"],
            sequence_number=offset,
            event_time=event_time,
            correlation_id=affected_asset["source_instance_id"],
        )
        envelope.update(
            {
                "asset_id": affected_asset["source_instance_id"],
                "action": action,
                "status": status,
                "readiness_before": before,
                "readiness_after": after,
                "reason_code": "SYNTHETIC_COMPONENT_CONDITION",
                "details": {
                    "work_order_id": "wo-synthetic-001",
                    "narrative": "Fictional maintenance event for demonstration",
                },
            }
        )
        yield TOPICS["sustainment.event"], envelope

    def _network_health_event(
        self, offset: int, event_time: datetime
    ) -> dict[str, Any]:
        entry = self._source_entry("NETWORK_MONITOR")
        sequence = {0: 0, 60: 1, 90: 2, 100: 3, 120: 4}[offset]
        status = "AVAILABLE"
        packet_loss_pct = 0.0
        latency_ms = 38
        event_scope = "NOMINAL"
        if offset == 90:
            status = "DEGRADED"
            packet_loss_pct = 14.5
            latency_ms = 1820
            event_scope = "BACKHAUL_OUTAGE_WINDOW"
        elif offset == 100:
            status = "RECOVERING"
            packet_loss_pct = 1.8
            latency_ms = 135
            event_scope = "BACKHAUL_RECOVERY"
        envelope = self._base_envelope(
            entry=entry,
            event_type="network.health",
            ordering_key="circuit-test-control-backhaul",
            sequence_number=sequence,
            event_time=event_time,
        )
        envelope.update(
            {
                "circuit_id": "circuit-test-control-backhaul",
                "status": status,
                "availability_pct": 100.0 if status == "AVAILABLE" else 73.0,
                "packet_loss_pct": packet_loss_pct,
                "latency_ms": latency_ms,
                "event_scope": event_scope,
            }
        )
        return envelope

    def _readiness_poll_events(
        self, offset: int, event_time: datetime
    ) -> Iterator[tuple[str, dict]]:
        entry = self._source_entry("READINESS_CONTROLLER")
        if offset == 0:
            responses = [
                ("role-test-director", "READY", True, "Prestart gates complete."),
                ("role-data-control", "READY", True, "Administrative mirror watermark current."),
                ("role-network-analyst", "READY", True, "All abstract circuits nominal."),
                ("role-safety-liaison", "READY", True, "Advisory safety evidence available."),
            ]
            poll_id = "poll-prestart-001"
        else:
            responses = [
                ("role-test-director", "READY_WITH_LIMITATION", True, "Resume approved with captured limitation."),
                ("role-data-control", "READY_WITH_LIMITATION", True, "Mirror gap preserved for reporting."),
                ("role-network-analyst", "READY_WITH_LIMITATION", True, "Backhaul restored after seeded outage."),
            ]
            poll_id = "poll-recovery-001"

        for sequence, (participant_role, response, is_authoritative, note) in enumerate(
            responses,
            start=offset,
        ):
            envelope = self._base_envelope(
                entry=entry,
                event_type="readiness.poll",
                ordering_key=poll_id,
                sequence_number=sequence,
                event_time=event_time,
            )
            envelope.update(
                {
                    "poll_id": poll_id,
                    "participant_role": participant_role,
                    "response": response,
                    "is_authoritative": is_authoritative,
                    "limitation_note": note,
                }
            )
            yield TOPICS["readiness.poll"], envelope

    def _operator_test_event(
        self, offset: int, event_time: datetime
    ) -> dict[str, Any]:
        entry = self._source_entry("OPERATOR_CONTROL")
        plan = {
            0: ("COUNTDOWN_STARTED", "PROCEED", "HUMAN_AUTHORITY", "countdown"),
            20: ("TRACK_OBSERVED", "PROCEED", "HUMAN_AUTHORITY", "sensor-observation"),
            95: ("HOLD_ISSUED", "PAUSE_FOR_REVIEW", "HUMAN_AUTHORITY", "network-health"),
            100: ("RESUME_AUTHORIZED", "PROCEED_WITH_LIMITATION", "HUMAN_AUTHORITY", "readiness-poll"),
            120: ("QUICKLOOK_RELEASED", "EVIDENCE_PUBLISHED", "HUMAN_AUTHORITY", "command-integration"),
        }
        marker, decision, authority, related_feed = plan[offset]
        envelope = self._base_envelope(
            entry=entry,
            event_type="operator.test_event",
            ordering_key=self.test_event_id,
            sequence_number=offset,
            event_time=event_time,
        )
        envelope.update(
            {
                "marker": marker,
                "decision": decision,
                "decision_authority": authority,
                "related_feed": related_feed,
            }
        )
        return envelope

    def _safety_status_event(
        self, offset: int, event_time: datetime
    ) -> dict[str, Any]:
        entry = self._source_entry("SAFETY_MONITOR")
        plan = {
            0: ("NOMINAL", "GREEN", "EVIDENCE_ONLY", "NONE"),
            92: (
                "TIMING_EVIDENCE_REVIEW",
                "AMBER",
                "EVIDENCE_ONLY",
                "PAUSE_RECOMMENDED_NOT_AUTHORITATIVE",
            ),
            100: ("POST_REVIEW_CLEAR", "GREEN", "EVIDENCE_ONLY", "RESUME_RECOMMENDED_NOT_AUTHORITATIVE"),
            120: ("QUICKLOOK_EVIDENCE_LOCKED", "GREEN", "EVIDENCE_ONLY", "NONE"),
        }
        condition, advisory_state, authority_scope, action = plan[offset]
        envelope = self._base_envelope(
            entry=entry,
            event_type="safety.status",
            ordering_key=self.test_event_id,
            sequence_number=offset,
            event_time=event_time,
        )
        envelope.update(
            {
                "condition": condition,
                "authority_scope": authority_scope,
                "advisory_state": advisory_state,
                "recommended_action": action,
            }
        )
        return envelope

    def _active_anomaly(
        self, instance_id: str, offset: int
    ) -> dict[str, Any] | None:
        for anomaly in self.scenario["anomalies"]:
            end = anomaly["start_offset_seconds"] + anomaly["duration_seconds"]
            if (
                anomaly["target_instance_id"] == instance_id
                and anomaly["start_offset_seconds"] <= offset < end
            ):
                return anomaly
        return None
