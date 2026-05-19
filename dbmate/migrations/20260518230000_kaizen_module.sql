-- migrate:up

-- =====================================================================
-- conversation_assignments
-- Append-only history of who was assigned to a conversation, and when.
-- The "current assignee" lives denormalized on conversations.assigned_user_id;
-- this table preserves the full history for audit and reporting.
-- KAIZEN-only: gated at the API layer by tenants.modules.kaizen.enabled,
-- not by schema.
-- =====================================================================
CREATE TABLE conversation_assignments (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    conversation_id       uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    assigned_to_user_id   uuid REFERENCES users(id),
    assigned_by_user_id   uuid REFERENCES users(id),
    reason                text CHECK (reason IN (
                              'manual', 'auto_routing', 'escalation', 'reopen', 'unassign'
                          )),
    assigned_at           timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversation_assignments_tenant_conv_at
    ON conversation_assignments(tenant_id, conversation_id, assigned_at DESC);

CREATE INDEX idx_conversation_assignments_tenant_assignee_at
    ON conversation_assignments(tenant_id, assigned_to_user_id, assigned_at DESC)
    WHERE assigned_to_user_id IS NOT NULL;

ALTER TABLE conversation_assignments ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversation_assignments_tenant_isolation ON conversation_assignments
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- =====================================================================
-- conversation_notes
-- Internal notes agents leave on a conversation. Never sent to the contact.
-- =====================================================================
CREATE TABLE conversation_notes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    author_user_id  uuid NOT NULL REFERENCES users(id),
    body            text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT NOW(),
    updated_at      timestamptz NOT NULL DEFAULT NOW(),
    deleted_at      timestamptz
);

CREATE INDEX idx_conversation_notes_tenant_conv_created
    ON conversation_notes(tenant_id, conversation_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE TRIGGER conversation_notes_set_updated_at
    BEFORE UPDATE ON conversation_notes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE conversation_notes ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversation_notes_tenant_isolation ON conversation_notes
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- migrate:down

DROP TABLE IF EXISTS conversation_notes;
DROP TABLE IF EXISTS conversation_assignments;
