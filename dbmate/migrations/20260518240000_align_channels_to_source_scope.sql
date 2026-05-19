-- migrate:up

-- Realign channel enums to match the channels named in the source docs
-- (CONCEPTO + SDD v1 + SDD v2): whatsapp, facebook, instagram, email, 0800, web.
-- TikTok is kept because it was added as an MVP channel by user decision.
-- YouTube, X, Reddit were earlier scope drift; drop them.

ALTER TABLE channel_identities
    DROP CONSTRAINT IF EXISTS channel_identities_channel_check;

ALTER TABLE channel_identities
    ADD CONSTRAINT channel_identities_channel_check
    CHECK (channel IN (
        'whatsapp',
        'instagram',
        'facebook',
        'email',
        'tiktok',
        'web'
    ));


ALTER TABLE conversations
    DROP CONSTRAINT IF EXISTS conversations_channel_check;

ALTER TABLE conversations
    ADD CONSTRAINT conversations_channel_check
    CHECK (channel IN (
        'whatsapp',
        'instagram_dm',
        'instagram_comment',
        'facebook_dm',
        'facebook_comment',
        'email',
        'tiktok_comment',
        'web'
    ));


ALTER TABLE webhook_events
    DROP CONSTRAINT IF EXISTS webhook_events_source_check;

ALTER TABLE webhook_events
    ADD CONSTRAINT webhook_events_source_check
    CHECK (source IN (
        'whatsapp',
        'meta',
        'email',
        'apify',
        'test'
    ));


-- migrate:down

ALTER TABLE channel_identities
    DROP CONSTRAINT IF EXISTS channel_identities_channel_check;

ALTER TABLE channel_identities
    ADD CONSTRAINT channel_identities_channel_check
    CHECK (channel IN (
        'whatsapp', 'instagram', 'facebook', 'email',
        'youtube', 'x', 'reddit', 'web'
    ));

ALTER TABLE conversations
    DROP CONSTRAINT IF EXISTS conversations_channel_check;

ALTER TABLE conversations
    ADD CONSTRAINT conversations_channel_check
    CHECK (channel IN (
        'whatsapp',
        'instagram_dm', 'instagram_comment',
        'facebook_dm', 'facebook_comment',
        'email',
        'youtube_comment', 'x_mention', 'reddit_mention',
        'tiktok_comment',
        'web'
    ));

ALTER TABLE webhook_events
    DROP CONSTRAINT IF EXISTS webhook_events_source_check;

ALTER TABLE webhook_events
    ADD CONSTRAINT webhook_events_source_check
    CHECK (source IN (
        'whatsapp', 'meta', 'email',
        'x', 'reddit', 'youtube',
        'apify', 'test'
    ));
