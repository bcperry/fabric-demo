create schema if not exists mda_ops;

create table if not exists mda_ops.test_event (
    test_event_id text primary key,
    scenario_id text not null,
    test_type text not null,
    observed_run_manifest_id text not null,
    predicted_run_manifest_id text not null,
    event_name text not null,
    planned_start_time_utc timestamptz not null,
    planned_end_time_utc timestamptz not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS')
);

alter table mda_ops.test_event
    add column if not exists test_type text not null default 'DISTRIBUTED_INTEGRATION';

create table if not exists mda_ops.test_objective (
    objective_id text primary key,
    objective_name text not null,
    objective_phase text not null,
    success_measure text not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS')
);

create table if not exists mda_ops.required_feed (
    required_feed_id text primary key,
    feed_name text not null,
    source_pattern text not null,
    expected_topic text not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS')
);

create table if not exists mda_ops.site (
    site_id text primary key,
    display_name text not null,
    city text not null,
    country_name text not null,
    country_code text not null,
    theater text not null,
    site_type text not null,
    latitude numeric(9, 5) not null,
    longitude numeric(9, 5) not null,
    location_notice text not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS'),
    updated_at_utc timestamptz not null
);

alter table mda_ops.site add column if not exists city text not null default 'Unknown';
alter table mda_ops.site add column if not exists country_name text not null default 'Unknown';
alter table mda_ops.site add column if not exists country_code text not null default 'XX';
alter table mda_ops.site add column if not exists theater text not null default 'Indo-Pacific';
alter table mda_ops.site add column if not exists site_type text not null default 'Operational location';

create table if not exists mda_ops.system_instance (
    system_instance_id text primary key,
    site_id text not null references mda_ops.site (site_id),
    system_family text not null,
    mission_role text not null,
    event_profile text not null,
    startup_seed integer not null,
    configuration_version text not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS'),
    updated_at_utc timestamptz not null
);

create index if not exists ix_system_instance_site_family
    on mda_ops.system_instance (site_id, system_family);

create table if not exists mda_ops.event_participant (
    test_event_id text not null references mda_ops.test_event (test_event_id),
    system_instance_id text not null references mda_ops.system_instance (system_instance_id),
    participation_mode text not null check (participation_mode in ('LIVE', 'HARDWARE_IN_LOOP', 'SIMULATED')),
    participation_role text not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS'),
    primary key (test_event_id, system_instance_id)
);

create index if not exists ix_event_participant_system
    on mda_ops.event_participant (system_instance_id, test_event_id);

create table if not exists mda_ops.readiness_history (
    readiness_event_id text primary key,
    system_instance_id text not null references mda_ops.system_instance (system_instance_id),
    readiness_state text not null check (readiness_state in ('READY', 'LIMITED', 'NOT_READY', 'MAINTENANCE')),
    health_score numeric(6, 4) not null check (health_score >= 0 and health_score <= 1),
    reason_code text not null,
    effective_at_utc timestamptz not null,
    recorded_at_utc timestamptz not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS')
);

create index if not exists ix_readiness_history_system_time
    on mda_ops.readiness_history (system_instance_id, effective_at_utc desc);

create table if not exists mda_ops.maintenance_action (
    maintenance_action_id text primary key,
    system_instance_id text not null references mda_ops.system_instance (system_instance_id),
    work_order_id text not null,
    action_type text not null,
    status text not null,
    reason_code text not null,
    started_at_utc timestamptz not null,
    completed_at_utc timestamptz,
    updated_at_utc timestamptz not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS')
);

create unique index if not exists ux_maintenance_action_work_order
    on mda_ops.maintenance_action (work_order_id, action_type);

create table if not exists mda_ops.inventory_position (
    system_instance_id text not null references mda_ops.system_instance (system_instance_id),
    inventory_category text not null,
    quantity_available integer not null check (quantity_available >= 0),
    quantity_required integer not null check (quantity_required >= 0),
    updated_at_utc timestamptz not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS'),
    primary key (system_instance_id, inventory_category)
);

create table if not exists mda_ops.finding (
    finding_id text primary key,
    test_event_id text not null references mda_ops.test_event (test_event_id),
    site_id text references mda_ops.site (site_id),
    objective_id text references mda_ops.test_objective (objective_id),
    severity text not null,
    finding_status text not null,
    finding_title text not null,
    finding_summary text not null,
    identified_at_utc timestamptz not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS')
);

alter table mda_ops.finding add column if not exists site_id text references mda_ops.site (site_id);
alter table mda_ops.finding add column if not exists objective_id text references mda_ops.test_objective (objective_id);

create table if not exists mda_ops.finding_evidence (
    finding_evidence_id text primary key,
    finding_id text not null references mda_ops.finding (finding_id),
    evidence_source text not null,
    evidence_reference text not null,
    evidence_type text not null,
    recorded_at_utc timestamptz not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS')
);

create table if not exists mda_ops.corrective_action (
    corrective_action_id text primary key,
    finding_id text not null references mda_ops.finding (finding_id),
    action_title text not null,
    action_status text not null,
    owner_role text not null,
    due_time_utc timestamptz not null,
    recorded_at_utc timestamptz not null,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS')
);

create table if not exists mda_ops.report_review (
    report_review_id text primary key,
    test_event_id text not null references mda_ops.test_event (test_event_id),
    report_stage text not null,
    reviewer_role text not null,
    review_status text not null,
    review_time_utc timestamptz,
    classification text not null check (classification = 'SYNTHETIC_UNCLASS')
);

create table if not exists mda_ops.projector_checkpoint (
    projector_name text not null,
    topic_name text not null,
    partition_id integer not null,
    last_sequence_number bigint not null,
    updated_at_utc timestamptz not null,
    primary key (projector_name, topic_name, partition_id)
);

create table if not exists mda_ops.projector_dead_letter (
    dead_letter_id bigint generated always as identity primary key,
    event_id text,
    topic_name text not null,
    failure_reason text not null,
    raw_payload jsonb not null,
    recorded_at_utc timestamptz not null
);
 
