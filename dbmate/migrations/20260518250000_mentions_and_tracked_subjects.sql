-- migrate:up

-- =====================================================================
-- tracked_subjects
-- Things the tenant wants to monitor: competitors, the brand itself,
-- keywords, hashtags. Tenant-managed (admin UI lists these).
-- =====================================================================
CREATE TABLE tracked_subjects (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN (
                    'competitor', 'brand', 'keyword', 'hashtag'
                )),
    label       text NOT NULL,
    handles     jsonb NOT NULL DEFAULT '{}'::jsonb,
    keywords    text[] NOT NULL DEFAULT '{}'::text[],
    hashtags    text[] NOT NULL DEFAULT '{}'::text[],
    enabled     boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT NOW(),
    updated_at  timestamptz NOT NULL DEFAULT NOW(),
    deleted_at  timestamptz
);

CREATE INDEX idx_tracked_subjects_tenant_enabled
    ON tracked_subjects(tenant_id, enabled)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_tracked_subjects_tenant_kind
    ON tracked_subjects(tenant_id, kind)
    WHERE deleted_at IS NULL;

CREATE TRIGGER tracked_subjects_set_updated_at
    BEFORE UPDATE ON tracked_subjects
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE tracked_subjects ENABLE ROW LEVEL SECURITY;

CREATE POLICY tracked_subjects_tenant_isolation ON tracked_subjects
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- =====================================================================
-- mentions
-- Public observations matching a tracked_subject. No thread, no contact
-- relationship (the author is NOT a customer of the tenant — they're
-- just someone who posted publicly).
-- =====================================================================
CREATE TABLE mentions (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    tracked_subject_id    uuid REFERENCES tracked_subjects(id) ON DELETE SET NULL,
    platform              text NOT NULL CHECK (platform IN (
                              'instagram', 'facebook', 'tiktok', 'web', 'news'
                          )),
    kind                  text NOT NULL CHECK (kind IN (
                              'post', 'comment', 'mention'
                          )),
    author_handle         text,
    author_display_name   text,
    author_url            text,
    content_text          text,
    content_url           text NOT NULL,
    content_published_at  timestamptz NOT NULL,
    metrics               jsonb NOT NULL DEFAULT '{}'::jsonb,
    external_id           text,
    raw_payload           jsonb,
    ingested_at           timestamptz NOT NULL DEFAULT NOW(),
    apify_run_id          text
);

CREATE INDEX idx_mentions_tenant_subject_published
    ON mentions(tenant_id, tracked_subject_id, content_published_at DESC);

CREATE INDEX idx_mentions_tenant_platform_published
    ON mentions(tenant_id, platform, content_published_at DESC);

CREATE UNIQUE INDEX uq_mentions_external
    ON mentions(tenant_id, platform, external_id)
    WHERE external_id IS NOT NULL;

ALTER TABLE mentions ENABLE ROW LEVEL SECURITY;

CREATE POLICY mentions_tenant_isolation ON mentions
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- =====================================================================
-- mention_classifications
-- Same shape as message_classifications but for mentions. Separate table
-- (rather than a polymorphic subject_type/subject_id) to keep FKs clean.
-- =====================================================================
CREATE TABLE mention_classifications (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    mention_id    uuid NOT NULL REFERENCES mentions(id) ON DELETE CASCADE,
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

CREATE INDEX idx_mention_classifications_tenant_mention_kind
    ON mention_classifications(tenant_id, mention_id, kind);

CREATE INDEX idx_mention_classifications_tenant_kind_label
    ON mention_classifications(tenant_id, kind, label);

ALTER TABLE mention_classifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY mention_classifications_tenant_isolation ON mention_classifications
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());


-- migrate:down

DROP TABLE IF EXISTS mention_classifications;
DROP TABLE IF EXISTS mentions;
DROP TABLE IF EXISTS tracked_subjects;
