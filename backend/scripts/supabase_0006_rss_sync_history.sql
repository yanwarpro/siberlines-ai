-- Additive synchronization history for an existing Supabase database.
CREATE TABLE IF NOT EXISTS public.rss_sync_runs (
    id uuid PRIMARY KEY,
    trigger_type varchar(20) NOT NULL,
    status varchar(20) NOT NULL,
    source_feed_id uuid REFERENCES public.rss_feeds(id) ON DELETE SET NULL,
    source_name varchar(200),
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    total_sources integer NOT NULL DEFAULT 0,
    successful_sources integer NOT NULL DEFAULT 0,
    failed_sources integer NOT NULL DEFAULT 0,
    items_received integer NOT NULL DEFAULT 0,
    new_articles integer NOT NULL DEFAULT 0,
    duplicate_articles integer NOT NULL DEFAULT 0,
    invalid_articles integer NOT NULL DEFAULT 0,
    error_summary text
);

CREATE INDEX IF NOT EXISTS idx_rss_sync_runs_started_at
    ON public.rss_sync_runs (started_at);
CREATE INDEX IF NOT EXISTS idx_rss_sync_runs_status
    ON public.rss_sync_runs (status);

ALTER TABLE public.rss_sync_runs ENABLE ROW LEVEL SECURITY;
