BEGIN;
CREATE SCHEMA IF NOT EXISTS live_test_control;
REVOKE ALL ON SCHEMA live_test_control FROM PUBLIC;
CREATE TABLE IF NOT EXISTS live_test_control.runs (
    run_id text PRIMARY KEY CHECK (run_id::uuid IS NOT NULL),
    actor text NOT NULL CHECK (actor::uuid IS NOT NULL),
    idempotency_key uuid NOT NULL,
    manifest jsonb NOT NULL,
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    image text NOT NULL CHECK (image ~ '@sha256:[0-9a-f]{64}$'),
    state text NOT NULL,
    execution_id text UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (actor, idempotency_key)
);
ALTER TABLE live_test_control.runs
    DROP CONSTRAINT IF EXISTS runs_state_check,
    DROP CONSTRAINT IF EXISTS runs_check,
    ADD CONSTRAINT runs_state_check CHECK (state IN ('REQUESTED','STARTING','RUNNING','START_UNKNOWN','SUCCEEDED','FAILED','CANCELLED')),
    ADD CONSTRAINT runs_check CHECK (state NOT IN ('RUNNING','SUCCEEDED','FAILED','CANCELLED') OR execution_id IS NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS single_active_run ON live_test_control.runs ((true))
    WHERE state IN ('REQUESTED','STARTING','RUNNING','START_UNKNOWN');
REVOKE ALL ON live_test_control.runs FROM PUBLIC;
CREATE OR REPLACE FUNCTION live_test_control.guard_run() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'state' - 'execution_id') IS DISTINCT FROM (to_jsonb(OLD) - 'state' - 'execution_id')
       OR (OLD.execution_id IS NOT NULL AND NEW.execution_id IS DISTINCT FROM OLD.execution_id)
       OR NOT ((OLD.state='REQUESTED' AND NEW.state='STARTING')
           OR (OLD.state='STARTING' AND NEW.state IN ('RUNNING','START_UNKNOWN'))
           OR (OLD.state IN ('RUNNING','START_UNKNOWN') AND NEW.state IN ('SUCCEEDED','FAILED','CANCELLED'))) THEN
        RAISE EXCEPTION 'Invalid run transition';
    END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER guard_run BEFORE UPDATE ON live_test_control.runs
    FOR EACH ROW EXECUTE FUNCTION live_test_control.guard_run();
REVOKE ALL ON FUNCTION live_test_control.guard_run() FROM PUBLIC;
DO $$
DECLARE runtime_role text := NULLIF(current_setting('live_test_control.runtime_role', true), '');
BEGIN
    IF runtime_role IS NOT NULL THEN
        IF runtime_role = current_user OR NOT EXISTS (
            SELECT FROM pg_roles WHERE rolname=runtime_role AND NOT rolsuper AND NOT rolcreaterole AND NOT rolcreatedb
                AND NOT rolreplication AND NOT rolbypassrls
        ) THEN RAISE EXCEPTION 'A separate nonadmin runtime role is required'; END IF;
        EXECUTE format('GRANT USAGE ON SCHEMA live_test_control TO %I', runtime_role);
        EXECUTE format('GRANT SELECT, INSERT ON live_test_control.runs TO %I', runtime_role);
        EXECUTE format('GRANT UPDATE (state, execution_id) ON live_test_control.runs TO %I', runtime_role);
    END IF;
END $$;
COMMIT;