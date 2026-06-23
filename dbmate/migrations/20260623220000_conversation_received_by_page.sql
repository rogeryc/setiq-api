-- migrate:up

ALTER TABLE conversations ADD COLUMN received_by_page_id text;

CREATE INDEX idx_conversations_received_by_page
    ON conversations(tenant_id, received_by_page_id)
    WHERE received_by_page_id IS NOT NULL;

-- migrate:down

DROP INDEX IF EXISTS idx_conversations_received_by_page;
ALTER TABLE conversations DROP COLUMN IF EXISTS received_by_page_id;
