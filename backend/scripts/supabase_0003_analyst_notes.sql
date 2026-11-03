-- Supabase SQL equivalent of Alembic revision 0003_analysis_analyst_notes.
--
-- Why this exists: the hosted Supabase database was created outside Alembic and
-- has no alembic_version table, so `alembic upgrade head` cannot be applied to it
-- directly. Run this script in the Supabase SQL editor (or psql) instead, once,
-- before deploying the backend revision that reads and writes analyses.notes_json.
--
-- This script is idempotent: re-running it is a no-op.

ALTER TABLE public.analyses
    ADD COLUMN IF NOT EXISTS notes_json jsonb NOT NULL DEFAULT '[]'::jsonb;

-- Existing saved runs must keep working. The column default above backfills every
-- existing row with an empty array, so no separate UPDATE is required.

-- Verify the result:
--   SELECT column_name, data_type, is_nullable, column_default
--   FROM information_schema.columns
--   WHERE table_schema = 'public'
--     AND table_name = 'analyses'
--     AND column_name = 'notes_json';
--
-- Expected: data_type = jsonb, is_nullable = NO, column_default = '[]'::jsonb

-- Rollback (only if the notes feature is removed):
--   ALTER TABLE public.analyses DROP COLUMN IF EXISTS notes_json;
