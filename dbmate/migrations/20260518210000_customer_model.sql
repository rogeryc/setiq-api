-- migrate:up

-- =====================================================================
-- contacts
-- An end-customer of the tenant. One person can have multiple handles
-- across channels (see channel_identities). Tenant-scoped, RLS-enforced.
-- =====================================================================
CREATE TABLE contacts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    display_name    text,
    primary_email   citext,
    primary_phone   text,
    profile_data    jsonb NOT NULL DEFAULT '{}'::jsonb,
    tags            text[] NOT NULL DEFAULT '{}'::text[],
    first_seen_at   timestamptz,
    last_seen_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT NOW(),
    updated_at      timestamptz NOT NULL DEFAULT NOW(),
    deleted_at      timestamptz
);

CREATE INDEX idx_contacts_tenant_last_seen
    ON contacts(tenant_id, last_seen_at DESC NULLS LAST)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_contacts_tenant_email
    ON contacts(tenant_id, primary_email)
    WHERE primary_email IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX idx_contacts_tenant_phone
    ON contacts(tenant_id, primary_phone)
    WHERE primary_phone IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX idx_contacts_tags
    ON contacts USING GIN (tags)
    WHERE deleted_at IS NULL;

CREATE TRIGGER contacts_set_updated_at
    BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY contacts_tenant_isolation ON contacts
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- =====================================================================
-- channel_identities
-- A handle a contact uses on a specific channel/platform.
-- One Facebook identity covers both Messenger DMs and FB Page comments.
-- One Instagram identity covers both IG DMs and IG comments.
-- =====================================================================
CREATE TABLE channel_identities (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    contact_id      uuid NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    channel         text NOT NULL CHECK (channel IN (
                        'whatsapp',
                        'instagram',
                        'facebook',
                        'email',
                        'youtube',
                        'x',
                        'reddit',
                        'web'
                    )),
    external_id     text NOT NULL,
    display_name    text,
    verified        boolean NOT NULL DEFAULT false,
    raw_metadata    jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT NOW(),
    updated_at      timestamptz NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, channel, external_id)
);

CREATE INDEX idx_channel_identities_contact
    ON channel_identities(contact_id);

CREATE TRIGGER channel_identities_set_updated_at
    BEFORE UPDATE ON channel_identities
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE channel_identities ENABLE ROW LEVEL SECURITY;

CREATE POLICY channel_identities_tenant_isolation ON channel_identities
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- migrate:down

DROP TABLE IF EXISTS channel_identities;
DROP TABLE IF EXISTS contacts;
