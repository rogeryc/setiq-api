-- migrate:up

-- Attach an owner to an insight — the person on the tenant who's on the hook
-- for actioning it. Nullable: unassigned by default. Uses SET NULL on user
-- delete so an insight survives its assignee leaving the tenant.
ALTER TABLE insights
    ADD COLUMN assigned_user_id uuid REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX idx_insights_tenant_assignee
    ON insights(tenant_id, assigned_user_id)
    WHERE deleted_at IS NULL AND enabled AND assigned_user_id IS NOT NULL;


-- migrate:down

DROP INDEX IF EXISTS idx_insights_tenant_assignee;
ALTER TABLE insights DROP COLUMN IF EXISTS assigned_user_id;
