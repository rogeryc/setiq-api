-- migrate:up

-- Tenant-scoped, AI-generated (or hand-set during dev) insights that show up
-- on the Overview dashboard: the hero lead copy, the featured recommendation,
-- and the smaller memo cards.
--
-- One table for all three kinds — they share most fields. Nullable columns
-- are populated only for the kinds that use them (see comments per column).
CREATE TABLE insights (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    kind            text NOT NULL CHECK (kind IN ('lead', 'featured', 'memo')),
    -- memos: 'low' | 'med' | 'high'; null otherwise
    severity        text CHECK (severity IN ('low', 'med', 'high')),
    -- memos: e.g. "Memo 02 · Oportunidad"
    tag             text,
    title           text NOT NULL,
    -- highlighted span inside the title (rendered as <em>)
    title_em        text,
    -- text after the <em> (featured rec only)
    title_tail      text,
    body            text NOT NULL,
    confidence      text,
    -- featured rec only: "hace 1h"
    age             text,
    -- featured rec only: "Impacto: …"
    impact          text,
    -- memo only: "Potencial: 12-18%"
    footnote        text,
    -- jsonb array of { label, route?, variant? }
    actions         jsonb NOT NULL DEFAULT '[]'::jsonb,
    -- for ordering memos (lowest first)
    rank            int NOT NULL DEFAULT 0,
    enabled         boolean NOT NULL DEFAULT true,
    valid_until     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT NOW(),
    updated_at      timestamptz NOT NULL DEFAULT NOW(),
    deleted_at      timestamptz
);

CREATE INDEX idx_insights_tenant_kind_rank
    ON insights(tenant_id, kind, rank)
    WHERE deleted_at IS NULL AND enabled;

CREATE TRIGGER insights_set_updated_at
    BEFORE UPDATE ON insights
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE insights ENABLE ROW LEVEL SECURITY;

CREATE POLICY insights_tenant_isolation ON insights
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- migrate:down

DROP TABLE IF EXISTS insights;
