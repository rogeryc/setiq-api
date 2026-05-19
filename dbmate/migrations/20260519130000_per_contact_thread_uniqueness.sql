-- migrate:up

-- Original constraint assumed one conversation per (tenant, channel, thread).
-- That's right for DMs but wrong for comments: multiple contacts post on the
-- same IG post, each becomes their own conversation row. Include contact_id
-- in the uniqueness key.

DROP INDEX IF EXISTS uq_conversations_external_thread;

CREATE UNIQUE INDEX uq_conversations_thread
    ON conversations(tenant_id, channel, contact_id, external_thread_id)
    WHERE external_thread_id IS NOT NULL;


-- migrate:down

DROP INDEX IF EXISTS uq_conversations_thread;

CREATE UNIQUE INDEX uq_conversations_external_thread
    ON conversations(tenant_id, channel, external_thread_id)
    WHERE external_thread_id IS NOT NULL;
