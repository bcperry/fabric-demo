begin;

insert into mda_ops.readiness_history (
    readiness_event_id,
    system_instance_id,
    readiness_state,
    health_score,
    reason_code,
    effective_at_utc,
    recorded_at_utc,
    classification
)
values (
    'ready-army-int-bravo-01-002',
    'army-int-bravo-01',
    'LIMITED',
    0.78,
    'CLOCK_ALIGNMENT_DELAY_REVIEW',
    '2026-11-03T15:01:30Z',
    '2026-11-03T15:01:35Z',
    'SYNTHETIC_UNCLASS'
)
on conflict (readiness_event_id) do update
set readiness_state = excluded.readiness_state,
    health_score = excluded.health_score,
    reason_code = excluded.reason_code,
    effective_at_utc = excluded.effective_at_utc,
    recorded_at_utc = excluded.recorded_at_utc;

insert into mda_ops.finding_evidence (
    finding_evidence_id,
    finding_id,
    evidence_source,
    evidence_reference,
    evidence_type,
    recorded_at_utc,
    classification
)
values (
    'evidence-003',
    'finding-clock-alignment-001',
    'observed_eventstream',
    'network-health-event-003',
    'network.health',
    '2026-11-03T15:01:30Z',
    'SYNTHETIC_UNCLASS'
)
on conflict (finding_evidence_id) do nothing;

insert into mda_ops.projector_checkpoint (
    projector_name,
    topic_name,
    partition_id,
    last_sequence_number,
    updated_at_utc
)
values (
    'sustainment-projector',
    'sustainment',
    0,
    135,
    '2026-11-03T15:02:15Z'
)
on conflict (projector_name, topic_name, partition_id) do update
set last_sequence_number = excluded.last_sequence_number,
    updated_at_utc = excluded.updated_at_utc;

commit;