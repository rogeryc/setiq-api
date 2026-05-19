\restrict 619ZbCoBLqPgV4ehq2lxuil7HaSBxEAVO5EE48ofUkCcccrf42QcpTPUMgSFX8P

-- Dumped from database version 14.20 (Homebrew)
-- Dumped by pg_dump version 14.20 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: citext; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;


--
-- Name: EXTENSION citext; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION citext IS 'data type for case-insensitive character strings';


--
-- Name: current_tenant_id(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.current_tenant_id() RETURNS uuid
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN current_setting('app.current_tenant', true)::uuid;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: channel_identities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.channel_identities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    contact_id uuid NOT NULL,
    channel text NOT NULL,
    external_id text NOT NULL,
    display_name text,
    verified boolean DEFAULT false NOT NULL,
    raw_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT channel_identities_channel_check CHECK ((channel = ANY (ARRAY['whatsapp'::text, 'instagram'::text, 'facebook'::text, 'email'::text, 'tiktok'::text, 'web'::text])))
);


--
-- Name: contacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contacts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    display_name text,
    primary_email public.citext,
    primary_phone text,
    profile_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    tags text[] DEFAULT '{}'::text[] NOT NULL,
    first_seen_at timestamp with time zone,
    last_seen_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: conversation_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_assignments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    assigned_to_user_id uuid,
    assigned_by_user_id uuid,
    reason text,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conversation_assignments_reason_check CHECK ((reason = ANY (ARRAY['manual'::text, 'auto_routing'::text, 'escalation'::text, 'reopen'::text, 'unassign'::text])))
);


--
-- Name: conversation_notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_notes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    author_user_id uuid NOT NULL,
    body text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    contact_id uuid NOT NULL,
    channel text NOT NULL,
    channel_identity_id uuid NOT NULL,
    status text DEFAULT 'open'::text NOT NULL,
    assigned_user_id uuid,
    subject text,
    external_thread_id text,
    last_message_at timestamp with time zone,
    unread_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    closed_at timestamp with time zone,
    CONSTRAINT conversations_channel_check CHECK ((channel = ANY (ARRAY['whatsapp'::text, 'instagram_dm'::text, 'instagram_comment'::text, 'facebook_dm'::text, 'facebook_comment'::text, 'email'::text, 'tiktok_comment'::text, 'web'::text]))),
    CONSTRAINT conversations_status_check CHECK ((status = ANY (ARRAY['open'::text, 'pending_agent'::text, 'waiting_customer'::text, 'resolved'::text, 'closed'::text])))
);


--
-- Name: insights; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.insights (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    kind text NOT NULL,
    severity text,
    tag text,
    title text NOT NULL,
    title_em text,
    title_tail text,
    body text NOT NULL,
    confidence text,
    age text,
    impact text,
    footnote text,
    actions jsonb DEFAULT '[]'::jsonb NOT NULL,
    rank integer DEFAULT 0 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    valid_until timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT insights_kind_check CHECK ((kind = ANY (ARRAY['lead'::text, 'featured'::text, 'memo'::text]))),
    CONSTRAINT insights_severity_check CHECK ((severity = ANY (ARRAY['low'::text, 'med'::text, 'high'::text])))
);


--
-- Name: mention_classifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mention_classifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    mention_id uuid NOT NULL,
    kind text NOT NULL,
    label text NOT NULL,
    confidence numeric(4,3),
    model_name text NOT NULL,
    model_version text,
    payload jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT mention_classifications_kind_check CHECK ((kind = ANY (ARRAY['intent'::text, 'sentiment'::text, 'priority'::text, 'opportunity'::text, 'language'::text])))
);


--
-- Name: mentions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mentions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    tracked_subject_id uuid,
    platform text NOT NULL,
    kind text NOT NULL,
    author_handle text,
    author_display_name text,
    author_url text,
    content_text text,
    content_url text NOT NULL,
    content_published_at timestamp with time zone NOT NULL,
    metrics jsonb DEFAULT '{}'::jsonb NOT NULL,
    external_id text,
    raw_payload jsonb,
    ingested_at timestamp with time zone DEFAULT now() NOT NULL,
    apify_run_id text,
    CONSTRAINT mentions_kind_check CHECK ((kind = ANY (ARRAY['post'::text, 'comment'::text, 'mention'::text]))),
    CONSTRAINT mentions_platform_check CHECK ((platform = ANY (ARRAY['instagram'::text, 'facebook'::text, 'tiktok'::text, 'web'::text, 'news'::text])))
);


--
-- Name: message_attachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_attachments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    message_id uuid NOT NULL,
    kind text NOT NULL,
    storage_url text NOT NULL,
    filename text,
    mime_type text,
    size_bytes bigint,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT message_attachments_kind_check CHECK ((kind = ANY (ARRAY['image'::text, 'audio'::text, 'video'::text, 'file'::text, 'document'::text])))
);


--
-- Name: message_classifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_classifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    message_id uuid NOT NULL,
    kind text NOT NULL,
    label text NOT NULL,
    confidence numeric(4,3),
    model_name text NOT NULL,
    model_version text,
    payload jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT message_classifications_kind_check CHECK ((kind = ANY (ARRAY['intent'::text, 'sentiment'::text, 'priority'::text, 'opportunity'::text, 'language'::text])))
);


--
-- Name: messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    direction text NOT NULL,
    sender_type text NOT NULL,
    sender_user_id uuid,
    content_type text NOT NULL,
    content_text text,
    external_id text,
    sent_at timestamp with time zone NOT NULL,
    delivered_at timestamp with time zone,
    read_at timestamp with time zone,
    raw_payload jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT messages_content_type_check CHECK ((content_type = ANY (ARRAY['text'::text, 'image'::text, 'audio'::text, 'video'::text, 'file'::text, 'template'::text]))),
    CONSTRAINT messages_direction_check CHECK ((direction = ANY (ARRAY['inbound'::text, 'outbound'::text]))),
    CONSTRAINT messages_sender_type_check CHECK ((sender_type = ANY (ARRAY['contact'::text, 'agent'::text, 'ai'::text, 'system'::text])))
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying NOT NULL
);


--
-- Name: tenant_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_users (
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tenant_users_role_check CHECK ((role = ANY (ARRAY['admin'::text, 'agent'::text, 'viewer'::text])))
);


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    slug text NOT NULL,
    name text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    modules jsonb DEFAULT '{}'::jsonb NOT NULL,
    settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tenants_status_check CHECK ((status = ANY (ARRAY['active'::text, 'trial'::text, 'suspended'::text])))
);


--
-- Name: tracked_subjects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tracked_subjects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    kind text NOT NULL,
    label text NOT NULL,
    handles jsonb DEFAULT '{}'::jsonb NOT NULL,
    keywords text[] DEFAULT '{}'::text[] NOT NULL,
    hashtags text[] DEFAULT '{}'::text[] NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT tracked_subjects_kind_check CHECK ((kind = ANY (ARRAY['competitor'::text, 'brand'::text, 'keyword'::text, 'hashtag'::text])))
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email public.citext NOT NULL,
    password_hash text NOT NULL,
    name text NOT NULL,
    is_superadmin boolean DEFAULT false NOT NULL,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: webhook_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.webhook_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid,
    source text NOT NULL,
    external_id text,
    payload jsonb NOT NULL,
    received_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone,
    status text DEFAULT 'pending'::text NOT NULL,
    error text,
    CONSTRAINT webhook_events_source_check CHECK ((source = ANY (ARRAY['whatsapp'::text, 'meta'::text, 'email'::text, 'apify'::text, 'test'::text]))),
    CONSTRAINT webhook_events_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'processed'::text, 'failed'::text, 'skipped'::text])))
);


--
-- Name: channel_identities channel_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_identities
    ADD CONSTRAINT channel_identities_pkey PRIMARY KEY (id);


--
-- Name: channel_identities channel_identities_tenant_id_channel_external_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_identities
    ADD CONSTRAINT channel_identities_tenant_id_channel_external_id_key UNIQUE (tenant_id, channel, external_id);


--
-- Name: contacts contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT contacts_pkey PRIMARY KEY (id);


--
-- Name: conversation_assignments conversation_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_assignments
    ADD CONSTRAINT conversation_assignments_pkey PRIMARY KEY (id);


--
-- Name: conversation_notes conversation_notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_notes
    ADD CONSTRAINT conversation_notes_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: insights insights_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insights
    ADD CONSTRAINT insights_pkey PRIMARY KEY (id);


--
-- Name: mention_classifications mention_classifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mention_classifications
    ADD CONSTRAINT mention_classifications_pkey PRIMARY KEY (id);


--
-- Name: mentions mentions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mentions
    ADD CONSTRAINT mentions_pkey PRIMARY KEY (id);


--
-- Name: message_attachments message_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_attachments
    ADD CONSTRAINT message_attachments_pkey PRIMARY KEY (id);


--
-- Name: message_classifications message_classifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_classifications
    ADD CONSTRAINT message_classifications_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: tenant_users tenant_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_users
    ADD CONSTRAINT tenant_users_pkey PRIMARY KEY (tenant_id, user_id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_slug_key UNIQUE (slug);


--
-- Name: tracked_subjects tracked_subjects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tracked_subjects
    ADD CONSTRAINT tracked_subjects_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: webhook_events webhook_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_events
    ADD CONSTRAINT webhook_events_pkey PRIMARY KEY (id);


--
-- Name: idx_channel_identities_contact; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_channel_identities_contact ON public.channel_identities USING btree (contact_id);


--
-- Name: idx_contacts_tags; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contacts_tags ON public.contacts USING gin (tags) WHERE (deleted_at IS NULL);


--
-- Name: idx_contacts_tenant_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contacts_tenant_email ON public.contacts USING btree (tenant_id, primary_email) WHERE ((primary_email IS NOT NULL) AND (deleted_at IS NULL));


--
-- Name: idx_contacts_tenant_last_seen; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contacts_tenant_last_seen ON public.contacts USING btree (tenant_id, last_seen_at DESC NULLS LAST) WHERE (deleted_at IS NULL);


--
-- Name: idx_contacts_tenant_phone; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contacts_tenant_phone ON public.contacts USING btree (tenant_id, primary_phone) WHERE ((primary_phone IS NOT NULL) AND (deleted_at IS NULL));


--
-- Name: idx_conversation_assignments_tenant_assignee_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversation_assignments_tenant_assignee_at ON public.conversation_assignments USING btree (tenant_id, assigned_to_user_id, assigned_at DESC) WHERE (assigned_to_user_id IS NOT NULL);


--
-- Name: idx_conversation_assignments_tenant_conv_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversation_assignments_tenant_conv_at ON public.conversation_assignments USING btree (tenant_id, conversation_id, assigned_at DESC);


--
-- Name: idx_conversation_notes_tenant_conv_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversation_notes_tenant_conv_created ON public.conversation_notes USING btree (tenant_id, conversation_id, created_at DESC) WHERE (deleted_at IS NULL);


--
-- Name: idx_conversations_tenant_assigned_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversations_tenant_assigned_status ON public.conversations USING btree (tenant_id, assigned_user_id, status) WHERE (assigned_user_id IS NOT NULL);


--
-- Name: idx_conversations_tenant_contact; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversations_tenant_contact ON public.conversations USING btree (tenant_id, contact_id);


--
-- Name: idx_conversations_tenant_status_last; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_conversations_tenant_status_last ON public.conversations USING btree (tenant_id, status, last_message_at DESC NULLS LAST);


--
-- Name: idx_insights_tenant_kind_rank; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_insights_tenant_kind_rank ON public.insights USING btree (tenant_id, kind, rank) WHERE ((deleted_at IS NULL) AND enabled);


--
-- Name: idx_mention_classifications_tenant_kind_label; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mention_classifications_tenant_kind_label ON public.mention_classifications USING btree (tenant_id, kind, label);


--
-- Name: idx_mention_classifications_tenant_mention_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mention_classifications_tenant_mention_kind ON public.mention_classifications USING btree (tenant_id, mention_id, kind);


--
-- Name: idx_mentions_tenant_platform_published; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mentions_tenant_platform_published ON public.mentions USING btree (tenant_id, platform, content_published_at DESC);


--
-- Name: idx_mentions_tenant_subject_published; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mentions_tenant_subject_published ON public.mentions USING btree (tenant_id, tracked_subject_id, content_published_at DESC);


--
-- Name: idx_message_attachments_tenant_message; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_attachments_tenant_message ON public.message_attachments USING btree (tenant_id, message_id);


--
-- Name: idx_message_classifications_tenant_kind_label; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_classifications_tenant_kind_label ON public.message_classifications USING btree (tenant_id, kind, label);


--
-- Name: idx_message_classifications_tenant_message_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_classifications_tenant_message_kind ON public.message_classifications USING btree (tenant_id, message_id, kind);


--
-- Name: idx_messages_tenant_conversation_sent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_messages_tenant_conversation_sent ON public.messages USING btree (tenant_id, conversation_id, sent_at);


--
-- Name: idx_tenant_users_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenant_users_user_id ON public.tenant_users USING btree (user_id);


--
-- Name: idx_tracked_subjects_tenant_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tracked_subjects_tenant_enabled ON public.tracked_subjects USING btree (tenant_id, enabled) WHERE (deleted_at IS NULL);


--
-- Name: idx_tracked_subjects_tenant_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tracked_subjects_tenant_kind ON public.tracked_subjects USING btree (tenant_id, kind) WHERE (deleted_at IS NULL);


--
-- Name: idx_webhook_events_source_external; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_webhook_events_source_external ON public.webhook_events USING btree (source, external_id) WHERE (external_id IS NOT NULL);


--
-- Name: idx_webhook_events_status_received; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_webhook_events_status_received ON public.webhook_events USING btree (status, received_at) WHERE (status = 'pending'::text);


--
-- Name: uq_conversations_thread; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_conversations_thread ON public.conversations USING btree (tenant_id, channel, contact_id, external_thread_id) WHERE (external_thread_id IS NOT NULL);


--
-- Name: uq_mentions_external; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_mentions_external ON public.mentions USING btree (tenant_id, platform, external_id) WHERE (external_id IS NOT NULL);


--
-- Name: uq_messages_external_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_messages_external_id ON public.messages USING btree (tenant_id, external_id) WHERE (external_id IS NOT NULL);


--
-- Name: channel_identities channel_identities_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER channel_identities_set_updated_at BEFORE UPDATE ON public.channel_identities FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: contacts contacts_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER contacts_set_updated_at BEFORE UPDATE ON public.contacts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: conversation_notes conversation_notes_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER conversation_notes_set_updated_at BEFORE UPDATE ON public.conversation_notes FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: conversations conversations_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER conversations_set_updated_at BEFORE UPDATE ON public.conversations FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: insights insights_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER insights_set_updated_at BEFORE UPDATE ON public.insights FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: tenants tenants_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tenants_set_updated_at BEFORE UPDATE ON public.tenants FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: tracked_subjects tracked_subjects_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tracked_subjects_set_updated_at BEFORE UPDATE ON public.tracked_subjects FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: users users_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: channel_identities channel_identities_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_identities
    ADD CONSTRAINT channel_identities_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.contacts(id) ON DELETE CASCADE;


--
-- Name: channel_identities channel_identities_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_identities
    ADD CONSTRAINT channel_identities_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: contacts contacts_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT contacts_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: conversation_assignments conversation_assignments_assigned_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_assignments
    ADD CONSTRAINT conversation_assignments_assigned_by_user_id_fkey FOREIGN KEY (assigned_by_user_id) REFERENCES public.users(id);


--
-- Name: conversation_assignments conversation_assignments_assigned_to_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_assignments
    ADD CONSTRAINT conversation_assignments_assigned_to_user_id_fkey FOREIGN KEY (assigned_to_user_id) REFERENCES public.users(id);


--
-- Name: conversation_assignments conversation_assignments_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_assignments
    ADD CONSTRAINT conversation_assignments_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: conversation_assignments conversation_assignments_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_assignments
    ADD CONSTRAINT conversation_assignments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: conversation_notes conversation_notes_author_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_notes
    ADD CONSTRAINT conversation_notes_author_user_id_fkey FOREIGN KEY (author_user_id) REFERENCES public.users(id);


--
-- Name: conversation_notes conversation_notes_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_notes
    ADD CONSTRAINT conversation_notes_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: conversation_notes conversation_notes_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_notes
    ADD CONSTRAINT conversation_notes_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: conversations conversations_assigned_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_assigned_user_id_fkey FOREIGN KEY (assigned_user_id) REFERENCES public.users(id);


--
-- Name: conversations conversations_channel_identity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_channel_identity_id_fkey FOREIGN KEY (channel_identity_id) REFERENCES public.channel_identities(id);


--
-- Name: conversations conversations_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES public.contacts(id) ON DELETE CASCADE;


--
-- Name: conversations conversations_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: insights insights_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insights
    ADD CONSTRAINT insights_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: mention_classifications mention_classifications_mention_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mention_classifications
    ADD CONSTRAINT mention_classifications_mention_id_fkey FOREIGN KEY (mention_id) REFERENCES public.mentions(id) ON DELETE CASCADE;


--
-- Name: mention_classifications mention_classifications_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mention_classifications
    ADD CONSTRAINT mention_classifications_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: mentions mentions_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mentions
    ADD CONSTRAINT mentions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: mentions mentions_tracked_subject_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mentions
    ADD CONSTRAINT mentions_tracked_subject_id_fkey FOREIGN KEY (tracked_subject_id) REFERENCES public.tracked_subjects(id) ON DELETE SET NULL;


--
-- Name: message_attachments message_attachments_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_attachments
    ADD CONSTRAINT message_attachments_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id) ON DELETE CASCADE;


--
-- Name: message_attachments message_attachments_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_attachments
    ADD CONSTRAINT message_attachments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: message_classifications message_classifications_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_classifications
    ADD CONSTRAINT message_classifications_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id) ON DELETE CASCADE;


--
-- Name: message_classifications message_classifications_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_classifications
    ADD CONSTRAINT message_classifications_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: messages messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: messages messages_sender_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_sender_user_id_fkey FOREIGN KEY (sender_user_id) REFERENCES public.users(id);


--
-- Name: messages messages_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenant_users tenant_users_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_users
    ADD CONSTRAINT tenant_users_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: tenant_users tenant_users_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_users
    ADD CONSTRAINT tenant_users_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: tracked_subjects tracked_subjects_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tracked_subjects
    ADD CONSTRAINT tracked_subjects_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: webhook_events webhook_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_events
    ADD CONSTRAINT webhook_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE SET NULL;


--
-- Name: channel_identities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.channel_identities ENABLE ROW LEVEL SECURITY;

--
-- Name: channel_identities channel_identities_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY channel_identities_tenant_isolation ON public.channel_identities USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: contacts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.contacts ENABLE ROW LEVEL SECURITY;

--
-- Name: contacts contacts_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY contacts_tenant_isolation ON public.contacts USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: conversation_assignments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.conversation_assignments ENABLE ROW LEVEL SECURITY;

--
-- Name: conversation_assignments conversation_assignments_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY conversation_assignments_tenant_isolation ON public.conversation_assignments USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: conversation_notes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.conversation_notes ENABLE ROW LEVEL SECURITY;

--
-- Name: conversation_notes conversation_notes_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY conversation_notes_tenant_isolation ON public.conversation_notes USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: conversations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;

--
-- Name: conversations conversations_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY conversations_tenant_isolation ON public.conversations USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: insights; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.insights ENABLE ROW LEVEL SECURITY;

--
-- Name: insights insights_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY insights_tenant_isolation ON public.insights USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: mention_classifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.mention_classifications ENABLE ROW LEVEL SECURITY;

--
-- Name: mention_classifications mention_classifications_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY mention_classifications_tenant_isolation ON public.mention_classifications USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: mentions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.mentions ENABLE ROW LEVEL SECURITY;

--
-- Name: mentions mentions_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY mentions_tenant_isolation ON public.mentions USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: message_attachments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.message_attachments ENABLE ROW LEVEL SECURITY;

--
-- Name: message_attachments message_attachments_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY message_attachments_tenant_isolation ON public.message_attachments USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: message_classifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.message_classifications ENABLE ROW LEVEL SECURITY;

--
-- Name: message_classifications message_classifications_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY message_classifications_tenant_isolation ON public.message_classifications USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

--
-- Name: messages messages_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY messages_tenant_isolation ON public.messages USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: tracked_subjects; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tracked_subjects ENABLE ROW LEVEL SECURITY;

--
-- Name: tracked_subjects tracked_subjects_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tracked_subjects_tenant_isolation ON public.tracked_subjects USING ((tenant_id = public.current_tenant_id())) WITH CHECK ((tenant_id = public.current_tenant_id()));


--
-- Name: webhook_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.webhook_events ENABLE ROW LEVEL SECURITY;

--
-- Name: webhook_events webhook_events_tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY webhook_events_tenant_isolation ON public.webhook_events USING (((tenant_id IS NOT NULL) AND (tenant_id = public.current_tenant_id()))) WITH CHECK (((tenant_id IS NULL) OR (tenant_id = public.current_tenant_id())));


--
-- PostgreSQL database dump complete
--

\unrestrict 619ZbCoBLqPgV4ehq2lxuil7HaSBxEAVO5EE48ofUkCcccrf42QcpTPUMgSFX8P


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20260518200000'),
    ('20260518210000'),
    ('20260518220000'),
    ('20260518230000'),
    ('20260518240000'),
    ('20260518250000'),
    ('20260519130000'),
    ('20260519140000');
