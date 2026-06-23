-- migrate:up

CREATE TABLE connected_channels (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider                    text NOT NULL DEFAULT 'meta' CHECK (provider IN ('meta')),
    page_id                     text NOT NULL,
    page_name                   text,
    category                    text,
    page_token                  text NOT NULL,
    instagram_business_account  jsonb,
    connected_by_user_id        text,
    token_expires_at            timestamptz,
    last_sync_at                timestamptz,
    created_at                  timestamptz NOT NULL DEFAULT NOW(),
    updated_at                  timestamptz NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_connected_channels_tenant_page
    ON connected_channels(tenant_id, page_id);

CREATE INDEX idx_connected_channels_tenant
    ON connected_channels(tenant_id);

CREATE INDEX idx_connected_channels_connected_by
    ON connected_channels(connected_by_user_id);

CREATE TRIGGER connected_channels_set_updated_at
    BEFORE UPDATE ON connected_channels
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE connected_channels ENABLE ROW LEVEL SECURITY;

CREATE POLICY connected_channels_tenant_isolation ON connected_channels
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- migrate:down

DROP TABLE IF EXISTS connected_channels;
