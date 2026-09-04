\set ON_ERROR_STOP on
\if :{?seed_scale}
\else
\set seed_scale 1
\endif
\if :{?skip_entra_principal}
\set fabric_principal_name fabric_user
\else
\if :{?fabric_principal_name}
\else
\echo 'fabric_principal_name is required.'
\quit 3
\endif
\endif
\if :{?test_event_count}
\else
\set test_event_count 120
\endif
\if :{?readiness_points}
\else
\set readiness_points 720
\endif
\if :{?maintenance_per_system}
\else
\set maintenance_per_system 6
\endif
\if :{?findings_per_event}
\else
\set findings_per_event 24
\endif

-- Destructive, deterministic demo reset. Override with: psql -v seed_scale=2 ...
\ir ../../../shared/integrated-test-data/04-source-projections/sql/001_schema.sql

set statement_timeout = 0;
set lock_timeout = '30s';
set timezone = 'UTC';
set synchronous_commit = off;

begin;

truncate table
    mda_ops.projector_dead_letter,
    mda_ops.projector_checkpoint,
    mda_ops.report_review,
    mda_ops.corrective_action,
    mda_ops.finding_evidence,
    mda_ops.finding,
    mda_ops.inventory_position,
    mda_ops.maintenance_action,
    mda_ops.readiness_history,
    mda_ops.event_participant,
    mda_ops.system_instance,
    mda_ops.site,
    mda_ops.required_feed,
    mda_ops.test_objective,
    mda_ops.test_event
restart identity cascade;

create temporary table seed_config on commit drop as
select
    greatest(1, :seed_scale::integer) as scale,
    :test_event_count::integer * greatest(1, :seed_scale::integer) as test_event_count,
    :readiness_points::integer as readiness_points_per_system,
    :maintenance_per_system::integer as maintenance_per_system,
    :findings_per_event::integer as findings_per_event,
    timestamptz '2026-11-03 15:00:00+00' as release_time;

insert into mda_ops.test_event (
    test_event_id,
    scenario_id,
    test_type,
    observed_run_manifest_id,
    predicted_run_manifest_id,
    event_name,
    planned_start_time_utc,
    planned_end_time_utc,
    classification
)
select
    case when event_number = 1
        then 'test-integrated-defense-001'
        else format('test-integrated-defense-%s', lpad(event_number::text, 3, '0'))
    end,
    'integrated-defense-001',
    case
        when event_number = 1 then 'DISTRIBUTED_INTEGRATION'
        when event_number % 3 = 0 then 'LIVE_INTERCEPT'
        when event_number % 3 = 1 then 'OPERATIONAL_EXERCISE'
        else 'DISTRIBUTED_INTEGRATION'
    end,
    format('run-2026-11-03-%s', lpad(event_number::text, 4, '0')),
    format('sim-2026-11-03-%s', lpad(event_number::text, 4, '0')),
    case when event_number = 1
        then 'Synthetic integrated defense lifecycle rehearsal'
        else format('%s %s',
            (array['Synthetic distributed integration test', 'Synthetic live intercept flight test', 'Synthetic operational exercise'])[((event_number - 2) % 3) + 1],
            event_number)
    end,
    release_time - ((event_number - 1) * interval '3 days'),
    release_time - ((event_number - 1) * interval '3 days') + interval '15 minutes',
    'SYNTHETIC_UNCLASS'
from seed_config
cross join lateral generate_series(1, test_event_count) as event_number;

insert into mda_ops.test_objective (
    objective_id,
    objective_name,
    objective_phase,
    success_measure,
    classification
)
values
    ('obj-track-fusion', 'Shared track reaches both engagement lanes', 'Running', 'One TPY-2 track produces shared-track, assignment, and participant events.', 'SYNTHETIC_UNCLASS'),
    ('obj-observed-vs-predicted', 'Observed chain is compared against deterministic prediction', 'Analysis', 'Delayed acknowledgements are isolated from the predicted baseline.', 'SYNTHETIC_UNCLASS'),
    ('obj-range-evidence', 'Range instrumentation explains deviations', 'Analysis', 'Instrumentation and ground-truth lanes isolate timing issues.', 'SYNTHETIC_UNCLASS'),
    ('obj-readiness-recovery', 'Readiness posture is recoverable for the next event', 'Post-Test Reporting', 'Recovery polls preserve limitation and corrective-action lineage.', 'SYNTHETIC_UNCLASS'),
    ('obj-safety-boundary', 'Safety evidence stays advisory', 'Running|Post-Test Reporting', 'Safety evidence recommends action without becoming an operator decision.', 'SYNTHETIC_UNCLASS');

insert into mda_ops.test_objective
select
    format('obj-synthetic-%s', lpad(objective_number::text, 3, '0')),
    format('%s readiness objective %s',
        (array['Sensor coverage', 'Track continuity', 'Command latency', 'Network resilience', 'Sustainment recovery'])[((objective_number - 1) % 5) + 1],
        objective_number),
    (array['Planning', 'Pre-Test', 'Running', 'Analysis', 'Post-Test Reporting'])[((objective_number - 1) % 5) + 1],
    format('At least %s percent of samples meet the governed threshold.', 90 + (objective_number % 10)),
    'SYNTHETIC_UNCLASS'
from generate_series(1, 55) as objective_number;

insert into mda_ops.required_feed (
    required_feed_id,
    feed_name,
    source_pattern,
    expected_topic,
    classification
)
values
    ('feed-sensor-observation', 'TPY-2 sensor observation', 'streaming', 'sensor-observation', 'SYNTHETIC_UNCLASS'),
    ('feed-command-integration', 'Integration command events', 'streaming', 'command-integration', 'SYNTHETIC_UNCLASS'),
    ('feed-range-evidence', 'Instrumentation and optical evidence', 'streaming', 'instrumentation-observation', 'SYNTHETIC_UNCLASS'),
    ('feed-network-health', 'Abstract network health', 'streaming', 'network-health', 'SYNTHETIC_UNCLASS'),
    ('feed-readiness-poll', 'Authoritative readiness poll', 'streaming', 'readiness-poll', 'SYNTHETIC_UNCLASS'),
    ('feed-operator-control', 'Authoritative operator decisions', 'streaming', 'operator-test-event', 'SYNTHETIC_UNCLASS'),
    ('feed-safety-evidence', 'Advisory safety evidence', 'streaming', 'safety-status', 'SYNTHETIC_UNCLASS'),
    ('feed-postgres-admin', 'PostgreSQL administrative control plane', 'postgresql', '', 'SYNTHETIC_UNCLASS'),
    ('feed-adls-baseline', 'Emulated baseline package', 'adls', '', 'SYNTHETIC_UNCLASS');

insert into mda_ops.required_feed
select
    format('feed-synthetic-%s', lpad(feed_number::text, 2, '0')),
    format('Synthetic mission feed %s', feed_number),
    (array['streaming', 'postgresql', 'adls'])[((feed_number - 10) % 3) + 1],
    case when (feed_number - 10) % 3 = 0 then format('mission-feed-%s', feed_number) else '' end,
    'SYNTHETIC_UNCLASS'
from generate_series(10, 24) as feed_number;

\ir seed_sites.sql

insert into mda_ops.system_instance
select
    system_instance_id,
    site_id,
    system_family,
    mission_role,
    event_profile,
    20261103 + component_number,
    format('1.%s.%s', component_number % 12, component_number),
    'SYNTHETIC_UNCLASS',
    release_time
from seed_config
cross join lateral (values
    (1, 'thaad-andersen-launcher-01', 'site-alpha', 'THAAD_LAUNCHER', 'UPPER_TIER_ENGAGEMENT', 'NORMAL'),
    (2, 'thaad-andersen-fire-control-01', 'site-alpha', 'THAAD_FIRE_CONTROL', 'UPPER_TIER_FIRE_CONTROL', 'NORMAL'),
    (3, 'tpy2-andersen-01', 'site-alpha', 'AN_TPY2_RADAR', 'LONG_RANGE_SENSOR', 'DEGRADED'),
    (4, 'bm-andersen-01', 'site-alpha', 'BATTLE_MANAGEMENT', 'SHARED_TRACK_INTEGRATION', 'NORMAL'),
    (5, 'patriot-basa-launcher-01', 'site-bravo', 'PATRIOT_LAUNCHER', 'LOWER_TIER_ENGAGEMENT', 'NORMAL'),
    (6, 'patriot-basa-launcher-02', 'site-bravo', 'PATRIOT_LAUNCHER', 'LOWER_TIER_ENGAGEMENT', 'NORMAL'),
    (7, 'patriot-basa-radar-01', 'site-bravo', 'PATRIOT_RADAR', 'LOWER_TIER_SENSOR', 'NORMAL'),
    (8, 'patriot-basa-control-01', 'site-bravo', 'PATRIOT_ENGAGEMENT_CONTROL', 'LOWER_TIER_FIRE_CONTROL', 'DEGRADED'),
    (9, 'patriot-osan-launcher-01', 'site-charlie', 'PATRIOT_LAUNCHER', 'LOWER_TIER_ENGAGEMENT', 'DEGRADED'),
    (10, 'patriot-osan-radar-01', 'site-charlie', 'PATRIOT_RADAR', 'LOWER_TIER_SENSOR', 'NORMAL'),
    (11, 'patriot-osan-control-01', 'site-charlie', 'PATRIOT_ENGAGEMENT_CONTROL', 'LOWER_TIER_FIRE_CONTROL', 'NORMAL'),
    (12, 'range-radar-kadena-01', 'site-015', 'RANGE_RADAR', 'INDEPENDENT_TRACKING', 'DEGRADED'),
    (13, 'army-integration-kadena-01', 'site-015', 'ARMY_INTEGRATION', 'JOINT_TRACK_INTEGRATION', 'NORMAL'),
    (14, 'network-monitor-kadena-01', 'site-015', 'NETWORK_MONITOR', 'DATA_LINK_HEALTH', 'NORMAL'),
    (15, 'range-receiver-busan-01', 'site-013', 'RANGE_RECEIVER', 'INSTRUMENTATION_RECEIVER', 'DEGRADED'),
    (16, 'optical-tracker-busan-01', 'site-013', 'OPTICAL_TRACKER', 'OPTICAL_CONFIRMATION', 'NORMAL'),
    (17, 'target-telemetry-guam-01', 'site-004', 'TARGET_TELEMETRY', 'TARGET_GROUND_TRUTH', 'NORMAL'),
    (18, 'ground-truth-guam-01', 'site-004', 'GROUND_TRUTH', 'INDEPENDENT_REFERENCE', 'DEGRADED')
) as roster(component_number, system_instance_id, site_id, system_family, mission_role, event_profile);

insert into mda_ops.event_participant (
    test_event_id,
    system_instance_id,
    participation_mode,
    participation_role,
    classification
)
select
    event.test_event_id,
    system.system_instance_id,
    case
        when event.test_type = 'LIVE_INTERCEPT' then 'LIVE'
        when event.test_type = 'OPERATIONAL_EXERCISE' and system.system_family like '%LAUNCHER' then 'SIMULATED'
        else 'HARDWARE_IN_LOOP'
    end,
    system.mission_role,
    'SYNTHETIC_UNCLASS'
from mda_ops.test_event as event
cross join mda_ops.system_instance as system;

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
select
    format('ready-%s-%s', system_instance_id, lpad(point_number::text, 4, '0')),
    system_instance_id,
    case
        when point_number % 181 between 0 and 5 then 'MAINTENANCE'
        when (system_number * 17 + point_number * 13) % 211 < 5 then 'NOT_READY'
        when (system_number * 11 + point_number * 7) % 47 < 6 then 'LIMITED'
        else 'READY'
    end,
    round(greatest(0.05, least(0.9999,
        0.97 - (((system_number * 11 + point_number * 7) % 37)::numeric / 100)
        - case when point_number % 181 between 0 and 5 then 0.35 else 0 end
    )), 4),
    case
        when point_number % 181 between 0 and 5 then 'SCHEDULED_MAINTENANCE'
        when (system_number * 17 + point_number * 13) % 211 < 5 then 'FAILED_HEALTH_CHECK'
        when (system_number * 11 + point_number * 7) % 47 < 6 then 'DEGRADED_COMPONENT'
        else 'NOMINAL'
    end,
    release_time - interval '30 days' + ((point_number - 1) * interval '1 hour'),
    release_time - interval '30 days' + ((point_number - 1) * interval '1 hour') + (((system_number + point_number) % 90) * interval '1 second'),
    'SYNTHETIC_UNCLASS'
from seed_config
cross join lateral (
    select system_instance_id, row_number() over (order by system_instance_id) as system_number
    from mda_ops.system_instance
) as systems
cross join lateral generate_series(1, readiness_points_per_system) as point_number;

insert into mda_ops.maintenance_action
select
    format('maint-%s-%s', system_instance_id, lpad(action_number::text, 2, '0')),
    system_instance_id,
    format('wo-%s-%s', system_instance_id, lpad(action_number::text, 2, '0')),
    (array['INSPECTION', 'CALIBRATION', 'SOFTWARE_UPDATE', 'COMPONENT_REPLACE', 'CONNECTIVITY_TEST'])[((action_number - 1) % 5) + 1],
    case when action_number % 11 = 0 then 'OPEN' when action_number % 7 = 0 then 'IN_PROGRESS' else 'COMPLETED' end,
    (array['PERIODIC_SERVICE', 'DEGRADED_HEALTH', 'CONFIGURATION_DRIFT', 'PART_SHORTAGE'])[((system_number + action_number) % 4) + 1],
    release_time - interval '90 days' + ((action_number * 4 + system_number % 96) * interval '1 hour'),
    case when action_number % 11 = 0 then null else release_time - interval '90 days' + ((action_number * 4 + system_number % 96 + 2) * interval '1 hour') end,
    release_time - interval '90 days' + ((action_number * 4 + system_number % 96 + 3) * interval '1 hour'),
    'SYNTHETIC_UNCLASS'
from seed_config
cross join lateral (
    select system_instance_id, row_number() over (order by system_instance_id) as system_number
    from mda_ops.system_instance
) as systems
cross join lateral generate_series(1, maintenance_per_system) as action_number;

insert into mda_ops.inventory_position
select
    system_instance_id,
    (array['POWER', 'COOLING', 'NETWORK', 'SENSOR_LRU', 'COMPUTE', 'SPARES', 'TOOLS', 'CONSUMABLES'])[category_number],
    greatest(0, 5 + ((system_number * category_number * 13) % 96) - case when system_number % 79 = 0 then 12 else 0 end),
    8 + ((system_number + category_number) % 24),
    release_time - ((system_number % 180) * interval '1 minute'),
    'SYNTHETIC_UNCLASS'
from seed_config
cross join lateral (
    select system_instance_id, row_number() over (order by system_instance_id) as system_number
    from mda_ops.system_instance
) as systems
cross join lateral generate_series(1, 8) as category_number;

insert into mda_ops.finding (
    finding_id,
    test_event_id,
    site_id,
    objective_id,
    severity,
    finding_status,
    finding_title,
    finding_summary,
    identified_at_utc,
    classification
)
select
    format('finding-%s-%s', lpad(event_number::text, 4, '0'), lpad(finding_number::text, 4, '0')),
    case when event_number = 1 then 'test-integrated-defense-001' else format('test-integrated-defense-%s', lpad(event_number::text, 3, '0')) end,
    (array['site-alpha', 'site-bravo', 'site-charlie', 'site-004', 'site-013', 'site-015'])[((finding_number - 1) % 6) + 1],
    (array['obj-track-fusion', 'obj-observed-vs-predicted', 'obj-range-evidence', 'obj-readiness-recovery', 'obj-safety-boundary'])[((finding_number - 1) % 5) + 1],
    (array['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])[((event_number + finding_number) % 4) + 1],
    case when finding_number % 17 = 0 then 'OPEN' when finding_number % 11 = 0 then 'IN_REVIEW' else 'CLOSED' end,
    format('%s deviation on system cohort %s',
        (array['Readiness', 'Timing', 'Data quality', 'Configuration', 'Sustainment'])[((finding_number - 1) % 5) + 1],
        1 + (finding_number % 100)),
    format('Synthetic finding %s for rehearsal %s links observed behavior to governed evidence and corrective action.', finding_number, event_number),
    release_time - ((event_number - 1) * interval '3 days') + ((finding_number % 900) * interval '1 second'),
    'SYNTHETIC_UNCLASS'
from seed_config
cross join lateral generate_series(1, test_event_count) as event_number
cross join lateral generate_series(1, findings_per_event) as finding_number;

insert into mda_ops.finding_evidence
select
    format('evidence-%s-%s-%s', lpad(event_number::text, 4, '0'), lpad(finding_number::text, 4, '0'), evidence_number),
    format('finding-%s-%s', lpad(event_number::text, 4, '0'), lpad(finding_number::text, 4, '0')),
    (array['EVENTHOUSE', 'POSTGRESQL', 'LAKEHOUSE'])[evidence_number],
    format('release/2026.11.03/event/%s/finding/%s/evidence/%s', event_number, finding_number, evidence_number),
    (array['TELEMETRY_WINDOW', 'READINESS_SNAPSHOT', 'BASELINE_COMPARISON'])[evidence_number],
    release_time - ((event_number - 1) * interval '3 days') + ((finding_number % 900 + evidence_number) * interval '1 second'),
    'SYNTHETIC_UNCLASS'
from seed_config
cross join lateral generate_series(1, test_event_count) as event_number
cross join lateral generate_series(1, findings_per_event) as finding_number
cross join lateral generate_series(1, 3) as evidence_number;

insert into mda_ops.corrective_action
select
    format('action-%s-%s-%s', lpad(event_number::text, 4, '0'), lpad(finding_number::text, 4, '0'), action_number),
    format('finding-%s-%s', lpad(event_number::text, 4, '0'), lpad(finding_number::text, 4, '0')),
    format('%s for synthetic finding %s',
        (array['Recalibrate component', 'Validate configuration', 'Repeat readiness poll', 'Review evidence package'])[((finding_number + action_number) % 4) + 1],
        finding_number),
    case when finding_number % 17 = 0 then 'OPEN' when finding_number % 11 = 0 then 'IN_PROGRESS' else 'COMPLETE' end,
    (array['SYSTEM_OWNER', 'TEST_DIRECTOR', 'DATA_STEWARD', 'SUSTAINMENT_LEAD'])[((event_number + finding_number + action_number) % 4) + 1],
    release_time - ((event_number - 1) * interval '3 days') + (action_number * interval '1 day'),
    release_time - ((event_number - 1) * interval '3 days') + ((finding_number % 900) * interval '1 second'),
    'SYNTHETIC_UNCLASS'
from seed_config
cross join lateral generate_series(1, test_event_count) as event_number
cross join lateral generate_series(1, findings_per_event) as finding_number
cross join lateral generate_series(1, 2) as action_number;

\ir seed_director_brief.sql

insert into mda_ops.report_review
select
    format('review-%s-%s', lpad(event_number::text, 4, '0'), review_number),
    case when event_number = 1 then 'test-integrated-defense-001' else format('test-integrated-defense-%s', lpad(event_number::text, 3, '0')) end,
    (array['DRAFT', 'TECHNICAL_REVIEW', 'LEADERSHIP_REVIEW', 'FINAL'])[((review_number - 1) % 4) + 1],
    (array['TEST_ANALYST', 'DATA_STEWARD', 'TEST_DIRECTOR', 'MISSION_OWNER', 'SAFETY_REVIEWER', 'SUSTAINMENT_LEAD'])[review_number],
    case when review_number <= 4 then 'APPROVED' when event_number % 9 = 0 then 'CHANGES_REQUESTED' else 'PENDING' end,
    case when review_number <= 4 then release_time - ((event_number - 1) * interval '3 days') + (review_number * interval '1 hour') else null end,
    'SYNTHETIC_UNCLASS'
from seed_config
cross join lateral generate_series(1, test_event_count) as event_number
cross join lateral generate_series(1, 6) as review_number;

insert into mda_ops.projector_checkpoint
select
    'mda-postgres-projector',
    topic_name,
    partition_id,
    1000000 + (topic_number * 10000) + partition_id,
    release_time
from seed_config
cross join lateral unnest(array[
    'sensor-observation',
    'command-integration',
    'system-status',
    'sustainment',
    'operator-test-event'
]) with ordinality as topics(topic_name, topic_number)
cross join lateral generate_series(0, 7) as partition_id;

insert into mda_ops.projector_dead_letter (
    event_id,
    topic_name,
    failure_reason,
    raw_payload,
    recorded_at_utc
)
select
    format('dead-letter-event-%s', lpad(dead_letter_number::text, 6, '0')),
    (array['sensor-observation', 'command-integration', 'system-status', 'sustainment'])[((dead_letter_number - 1) % 4) + 1],
    (array['SCHEMA_VERSION_UNKNOWN', 'REQUIRED_FIELD_MISSING', 'SEQUENCE_GAP', 'TIMESTAMP_OUT_OF_RANGE'])[((dead_letter_number - 1) % 4) + 1],
    jsonb_build_object(
        'event_id', format('dead-letter-event-%s', lpad(dead_letter_number::text, 6, '0')),
        'release_id', '2026.11.03',
        'classification', 'SYNTHETIC_UNCLASS',
        'synthetic_error_number', dead_letter_number
    ),
    release_time + (dead_letter_number * interval '1 second')
from seed_config
cross join lateral generate_series(1, 1000 * scale) as dead_letter_number;

commit;

create index if not exists ix_readiness_history_recorded
    on mda_ops.readiness_history (recorded_at_utc desc);
create index if not exists ix_maintenance_action_system_status
    on mda_ops.maintenance_action (system_instance_id, status, updated_at_utc desc);
create index if not exists ix_inventory_position_category
    on mda_ops.inventory_position (inventory_category, updated_at_utc desc);
create index if not exists ix_finding_event_status_severity
    on mda_ops.finding (test_event_id, finding_status, severity);
create index if not exists ix_finding_evidence_finding
    on mda_ops.finding_evidence (finding_id, recorded_at_utc desc);
create index if not exists ix_corrective_action_finding_status
    on mda_ops.corrective_action (finding_id, action_status, due_time_utc);
create index if not exists ix_report_review_event_stage
    on mda_ops.report_review (test_event_id, report_stage, review_status);

analyze mda_ops.test_event;
analyze mda_ops.test_objective;
analyze mda_ops.required_feed;
analyze mda_ops.site;
analyze mda_ops.system_instance;
analyze mda_ops.event_participant;
analyze mda_ops.readiness_history;
analyze mda_ops.maintenance_action;
analyze mda_ops.inventory_position;
analyze mda_ops.finding;
analyze mda_ops.finding_evidence;
analyze mda_ops.corrective_action;
analyze mda_ops.report_review;
analyze mda_ops.projector_checkpoint;
analyze mda_ops.projector_dead_letter;

-- Fabric requires its Entra connection principal to own mirrored tables.
\if :{?skip_entra_principal}
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'fabric_user') then
        create role fabric_user createdb createrole replication nologin;
    end if;
end
$$;
\else
select exists (
    select 1 from pg_roles where rolname = :'fabric_principal_name'
) as fabric_principal_exists
\gset
\if :fabric_principal_exists
\else
\echo 'fabric_principal_name must already be mapped as a Microsoft Entra role.'
\quit 3
\endif
\endif

\if :{?skip_entra_principal}
\echo 'Skipping Azure-only azure_cdc_admin grant for local validation.'
\else
grant azure_cdc_admin to :"fabric_principal_name";
\endif
select format('grant %I to current_user', :'fabric_principal_name')
where current_user <> :'fabric_principal_name'
\gexec
grant create on database mdaoperations to :"fabric_principal_name";
grant usage on schema mda_ops to :"fabric_principal_name";
grant select, insert, update, delete on all tables in schema mda_ops to :"fabric_principal_name";
grant usage, select on all sequences in schema mda_ops to :"fabric_principal_name";

alter table mda_ops.test_event owner to :"fabric_principal_name";
alter table mda_ops.test_objective owner to :"fabric_principal_name";
alter table mda_ops.required_feed owner to :"fabric_principal_name";
alter table mda_ops.site owner to :"fabric_principal_name";
alter table mda_ops.system_instance owner to :"fabric_principal_name";
alter table mda_ops.event_participant owner to :"fabric_principal_name";
alter table mda_ops.readiness_history owner to :"fabric_principal_name";
alter table mda_ops.maintenance_action owner to :"fabric_principal_name";
alter table mda_ops.inventory_position owner to :"fabric_principal_name";
alter table mda_ops.finding owner to :"fabric_principal_name";
alter table mda_ops.finding_evidence owner to :"fabric_principal_name";
alter table mda_ops.corrective_action owner to :"fabric_principal_name";
alter table mda_ops.report_review owner to :"fabric_principal_name";
alter table mda_ops.projector_checkpoint owner to :"fabric_principal_name";
alter table mda_ops.projector_dead_letter owner to :"fabric_principal_name";
alter sequence mda_ops.projector_dead_letter_dead_letter_id_seq owner to :"fabric_principal_name";

select
    table_name,
    row_count
from (
    select 'test_event' as table_name, count(*) as row_count from mda_ops.test_event
    union all select 'test_objective', count(*) from mda_ops.test_objective
    union all select 'required_feed', count(*) from mda_ops.required_feed
    union all select 'site', count(*) from mda_ops.site
    union all select 'system_instance', count(*) from mda_ops.system_instance
    union all select 'event_participant', count(*) from mda_ops.event_participant
    union all select 'readiness_history', count(*) from mda_ops.readiness_history
    union all select 'maintenance_action', count(*) from mda_ops.maintenance_action
    union all select 'inventory_position', count(*) from mda_ops.inventory_position
    union all select 'finding', count(*) from mda_ops.finding
    union all select 'finding_evidence', count(*) from mda_ops.finding_evidence
    union all select 'corrective_action', count(*) from mda_ops.corrective_action
    union all select 'report_review', count(*) from mda_ops.report_review
    union all select 'projector_checkpoint', count(*) from mda_ops.projector_checkpoint
    union all select 'projector_dead_letter', count(*) from mda_ops.projector_dead_letter
) as counts
order by table_name;
