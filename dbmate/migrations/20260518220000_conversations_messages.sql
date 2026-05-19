-- migrate:up

-- =====================================================================
-- conversations
-- A thread with a contact on a specific channel. `channel` is more
-- granular than `channel_identities.channel` because the same identity
-- can carry both DMs and comments on different post threads.
-- =====================================================================
CREATE TABLE conversations (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    contact_id           uuid NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    channel              text NOT NULL CHECK (channel IN (
                            'whatsapp',
                            'instagram_dm',
                            'instagram_comment',
                            'facebook_dm',
                            'facebook_comment',
                            'email',
                            'youtube_comment',
                            'x_mention',
                            'reddit_mention',
                            'tiktok_comment',
                            'web'
                         )),
    channel_identity_id  uuid NOT NULL REFERENCES channel_identities(id),
    status               text NOT NULL DEFAULT 'open' CHECK (status IN (
                            'open',
                            'pending_agent',
                            'waiting_customer',
                            'resolved',
                            'closed'
                         )),
    assigned_user_id     uuid REFERENCES users(id),
    subject              text,
    external_thread_id   text,
    last_message_at      timestamptz,
    unread_count         int NOT NULL DEFAULT 0,
    created_at           timestamptz NOT NULL DEFAULT NOW(),
    updated_at           timestamptz NOT NULL DEFAULT NOW(),
    closed_at            timestamptz
);

CREATE INDEX idx_conversations_tenant_status_last
    ON conversations(tenant_id, status, last_message_at DESC NULLS LAST);

CREATE INDEX idx_conversations_tenant_assigned_status
    ON conversations(tenant_id, assigned_user_id, status)
    WHERE assigned_user_id IS NOT NULL;

CREATE INDEX idx_conversations_tenant_contact
    ON conversations(tenant_id, contact_id);

CREATE UNIQUE INDEX uq_conversations_external_thread
    ON conversations(tenant_id, channel, external_thread_id)
    WHERE external_thread_id IS NOT NULL;

CREATE TRIGGER conversations_set_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversations_tenant_isolation ON conversations
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- =====================================================================
-- messages
-- =====================================================================
CREATE TABLE messages (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    direction       text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    sender_type     text NOT NULL CHECK (sender_type IN (
                        'contact', 'agent', 'ai', 'system'
                    )),
    sender_user_id  uuid REFERENCES users(id),
    content_type    text NOT NULL CHECK (content_type IN (
                        'text', 'image', 'audio', 'video', 'file', 'template'
                    )),
    content_text    text,
    external_id     text,
    sent_at         timestamptz NOT NULL,
    delivered_at    timestamptz,
    read_at         timestamptz,
    raw_payload     jsonb,
    created_at      timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_tenant_conversation_sent
    ON messages(tenant_id, conversation_id, sent_at);

CREATE UNIQUE INDEX uq_messages_external_id
    ON messages(tenant_id, external_id)
    WHERE external_id IS NOT NULL;

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY messages_tenant_isolation ON messages
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- =====================================================================
-- message_attachments
-- =====================================================================
CREATE TABLE message_attachments (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    message_id  uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN (
                    'image', 'audio', 'video', 'file', 'document'
                )),
    storage_url text NOT NULL,
    filename    text,
    mime_type   text,
    size_bytes  bigint,
    metadata    jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_message_attachments_tenant_message
    ON message_attachments(tenant_id, message_id);

ALTER TABLE message_attachments ENABLE ROW LEVEL SECURITY;

CREATE POLICY message_attachments_tenant_isolation ON message_attachments
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- =====================================================================
-- message_classifications
-- AI-derived labels on a message. Separate table so we can re-classify
-- with a new model/prompt without destroying history.
-- =====================================================================
CREATE TABLE message_classifications (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    message_id    uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    kind          text NOT NULL CHECK (kind IN (
                      'intent', 'sentiment', 'priority', 'opportunity', 'language'
                  )),
    label         text NOT NULL,
    confidence    numeric(4,3),
    model_name    text NOT NULL,
    model_version text,
    payload       jsonb,
    created_at    timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_message_classifications_tenant_message_kind
    ON message_classifications(tenant_id, message_id, kind);

CREATE INDEX idx_message_classifications_tenant_kind_label
    ON message_classifications(tenant_id, kind, label);

ALTER TABLE message_classifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY message_classifications_tenant_isolation ON message_classifications
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- =====================================================================
-- webhook_events
-- Raw log of every inbound webhook. Used for replay + debugging.
-- tenant_id is nullable because we may not have resolved which tenant
-- a payload belongs to before processing it.
-- Workers process this table with a role that bypasses RLS;
-- tenant-scoped reads (for debug UI) are guarded by the RLS policy below.
-- =====================================================================
CREATE TABLE webhook_events (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid REFERENCES tenants(id) ON DELETE SET NULL,
    source       text NOT NULL CHECK (source IN (
                    'whatsapp', 'meta', 'email', 'x', 'reddit', 'youtube', 'apify', 'test'
                 )),
    external_id  text,
    payload      jsonb NOT NULL,
    received_at  timestamptz NOT NULL DEFAULT NOW(),
    processed_at timestamptz,
    status       text NOT NULL DEFAULT 'pending' CHECK (status IN (
                    'pending', 'processed', 'failed', 'skipped'
                 )),
    error        text
);

CREATE INDEX idx_webhook_events_status_received
    ON webhook_events(status, received_at)
    WHERE status = 'pending';

CREATE INDEX idx_webhook_events_source_external
    ON webhook_events(source, external_id)
    WHERE external_id IS NOT NULL;

ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY webhook_events_tenant_isolation ON webhook_events
    USING (tenant_id IS NOT NULL AND tenant_id = current_tenant_id())
    WITH CHECK (tenant_id IS NULL OR tenant_id = current_tenant_id());


-- migrate:down

DROP TABLE IF EXISTS webhook_events;
DROP TABLE IF EXISTS message_classifications;
DROP TABLE IF EXISTS message_attachments;
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS conversations;
