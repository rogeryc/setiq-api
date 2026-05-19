-- Run once per environment as a Postgres superuser. Safe to re-run.
--
-- Creates the non-superuser app role used by the FastAPI runtime so RLS
-- policies actually enforce tenant isolation. Migrations continue to run
-- under the superuser (via dbmate); the running API connects as setiq_app.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'setiq_app') THEN
        CREATE ROLE setiq_app WITH LOGIN PASSWORD 'setiq_dev_password';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO setiq_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO setiq_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO setiq_app;
GRANT EXECUTE ON FUNCTION current_tenant_id() TO setiq_app;
GRANT EXECUTE ON FUNCTION set_updated_at() TO setiq_app;

-- Future tables created by the migration role get auto-grants
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO setiq_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO setiq_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO setiq_app;
