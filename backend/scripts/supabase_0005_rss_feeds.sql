-- Apply once to the existing Supabase schema after verifying the current
-- datasets/posts columns match the deployed SIBERLENS schema.
ALTER TABLE public.posts
    ADD COLUMN IF NOT EXISTS source_url varchar(2048);

CREATE TABLE IF NOT EXISTS public.rss_feeds (
    id uuid PRIMARY KEY,
    name varchar(200) NOT NULL,
    url varchar(512) NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    dataset_id uuid UNIQUE REFERENCES public.datasets(id) ON DELETE SET NULL,
    last_synced_at timestamptz,
    last_sync_status varchar(20),
    last_sync_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_rss_feeds_url UNIQUE (url)
);

CREATE INDEX IF NOT EXISTS idx_rss_feeds_enabled
    ON public.rss_feeds (enabled);

ALTER TABLE public.rss_feeds ENABLE ROW LEVEL SECURITY;

INSERT INTO public.datasets (id, name, source_type, row_count, status)
VALUES
    ('00000000-0000-4000-8000-000000000501', 'CISA Cybersecurity Advisories', 'rss_feed', 0, 'waiting_for_sync'),
    ('00000000-0000-4000-8000-000000000502', 'UK NCSC Security Updates', 'rss_feed', 0, 'waiting_for_sync')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.rss_feeds (id, name, url, enabled, dataset_id)
VALUES
    ('00000000-0000-4000-8000-000000000401', 'CISA Cybersecurity Advisories', 'https://www.cisa.gov/cybersecurity-advisories/cybersecurity-advisories.xml', true, '00000000-0000-4000-8000-000000000501'),
    ('00000000-0000-4000-8000-000000000402', 'UK NCSC Security Updates', 'https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml', true, '00000000-0000-4000-8000-000000000502')
ON CONFLICT (id) DO NOTHING;
