update mda_ops.finding
set finding_status = 'CLOSED'
where test_event_id = 'test-integrated-defense-001';

update mda_ops.corrective_action
set action_status = 'COMPLETE'
where finding_id like 'finding-0001-%';

update mda_ops.finding as finding
set
    site_id = brief.site_id,
    objective_id = brief.objective_id,
    severity = brief.severity,
    finding_status = brief.finding_status,
    finding_title = brief.finding_title,
    finding_summary = brief.finding_summary,
    identified_at_utc = brief.identified_at_utc
from (values
    ('finding-0001-0001', 'site-alpha', 'obj-readiness-recovery', 'CRITICAL', 'OPEN', 'Andersen sensor readiness below execution threshold', 'Two sensor participants remain constrained at Andersen, placing the readiness-recovery objective and execution window at risk.', timestamptz '2026-11-03 10:20:00+00'),
    ('finding-0001-0002', 'site-bravo', 'obj-track-fusion', 'CRITICAL', 'IN_REVIEW', 'Basa command-integration timing outside tolerance', 'The command-integration dry run exceeded the approved timing tolerance and requires a successful repeat before release.', timestamptz '2026-11-03 10:35:00+00'),
    ('finding-0001-0003', 'site-charlie', 'obj-readiness-recovery', 'HIGH', 'OPEN', 'Osan participant recovery check incomplete', 'The participant recovery poll is incomplete, reducing confidence that the formation can recover before the execution gate.', timestamptz '2026-11-03 10:50:00+00'),
    ('finding-0001-0004', 'site-015', 'obj-range-evidence', 'HIGH', 'IN_REVIEW', 'Kadena range-evidence package incomplete', 'The range-evidence package is missing one required validation record needed to explain deviations after execution.', timestamptz '2026-11-03 11:05:00+00'),
    ('finding-0001-0005', 'site-004', 'obj-range-evidence', 'MEDIUM', 'OPEN', 'Naval Base Guam instrumentation clock drift', 'Instrumentation clock drift remains above the rehearsal threshold and could reduce event-correlation confidence.', timestamptz '2026-11-03 11:20:00+00'),
    ('finding-0001-0006', 'site-013', 'obj-observed-vs-predicted', 'MEDIUM', 'IN_REVIEW', 'Busan recovery rehearsal pending final review', 'The recovery rehearsal completed, but the observed-versus-predicted comparison still awaits director-level evidence review.', timestamptz '2026-11-03 11:35:00+00')
) as brief(finding_id, site_id, objective_id, severity, finding_status, finding_title, finding_summary, identified_at_utc)
where finding.finding_id = brief.finding_id;

update mda_ops.corrective_action as action
set
    action_title = brief.action_title,
    action_status = 'IN_PROGRESS',
    owner_role = brief.owner_organization,
    due_time_utc = brief.due_time_utc,
    recorded_at_utc = brief.recorded_at_utc
from (values
    ('action-0001-0001-1', 'Complete Andersen sensor recovery poll', 'Guam Sensor Integration Team', timestamptz '2026-11-03 13:00:00+00', timestamptz '2026-11-03 10:25:00+00'),
    ('action-0001-0002-1', 'Repeat command-integration timing run', 'Joint Command Integration Lead', timestamptz '2026-11-03 12:30:00+00', timestamptz '2026-11-03 10:40:00+00'),
    ('action-0001-0003-1', 'Certify Osan participant recovery state', 'Korea Participant Readiness Cell', timestamptz '2026-11-03 13:30:00+00', timestamptz '2026-11-03 10:55:00+00'),
    ('action-0001-0004-1', 'Complete Kadena evidence validation', 'Kadena Range Evidence Lead', timestamptz '2026-11-03 14:00:00+00', timestamptz '2026-11-03 11:10:00+00'),
    ('action-0001-0005-1', 'Re-synchronize Guam instrumentation clocks', 'Guam Instrumentation Lead', timestamptz '2026-11-03 13:15:00+00', timestamptz '2026-11-03 11:25:00+00'),
    ('action-0001-0006-1', 'Approve Busan recovery evidence', 'Joint Test Evidence Chair', timestamptz '2026-11-03 14:15:00+00', timestamptz '2026-11-03 11:40:00+00')
) as brief(corrective_action_id, action_title, owner_organization, due_time_utc, recorded_at_utc)
where action.corrective_action_id = brief.corrective_action_id;