-- migrate:up

-- =====================================================================
-- Extensions
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS citext;
-- gen_random_uuid() is a Postgres 13+ built-in; no extension needed.


-- =====================================================================
-- Reusable trigger: keep updated_at fresh
-- =====================================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =====================================================================
-- Helper: read the current tenant from a session GUC.
-- Used by RLS policies on tenant-scoped tables (added in later migrations).
-- The API sets `app.current_tenant` on every authenticated request.
-- =====================================================================
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS uuid AS $$
BEGIN
    RETURN current_setting('app.current_tenant', true)::uuid;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;


-- =====================================================================
-- tenants
-- The root of multi-tenancy. Module entitlements live in `modules` JSONB.
-- =====================================================================
CREATE TABLE tenants (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        text UNIQUE NOT NULL,
    name        text NOT NULL,
    status      text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'trial', 'suspended')),
    modules     jsonb NOT NULL DEFAULT '{}'::jsonb,
    settings    jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT NOW(),
    updated_at  timestamptz NOT NULL DEFAULT NOW()
);

CREATE TRIGGER tenants_set_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =====================================================================
-- users
-- Global identity. A user can belong to multiple tenants via tenant_users.
-- No RLS on this table; the auth layer queries it with explicit filters.
-- =====================================================================
CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email           citext UNIQUE NOT NULL,
    password_hash   text NOT NULL,
    name            text NOT NULL,
    is_superadmin   boolean NOT NULL DEFAULT false,
    last_login_at   timestamptz,
    created_at      timestamptz NOT NULL DEFAULT NOW(),
    updated_at      timestamptz NOT NULL DEFAULT NOW(),
    deleted_at      timestamptz
);

CREATE TRIGGER users_set_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =====================================================================
-- tenant_users
-- Junction: who can access which tenant, with what role.
-- =====================================================================
CREATE TABLE tenant_users (
    tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        text NOT NULL CHECK (role IN ('admin', 'agent', 'viewer')),
    created_at  timestamptz NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, user_id)
);

CREATE INDEX idx_tenant_users_user_id ON tenant_users(user_id);


-- migrate:down

DROP TABLE IF EXISTS tenant_users;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS tenants;
DROP FUNCTION IF EXISTS current_tenant_id();
DROP FUNCTION IF EXISTS set_updated_at();
DROP EXTENSION IF EXISTS citext;
