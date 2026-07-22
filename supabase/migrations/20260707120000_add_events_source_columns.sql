-- Add external-id + source columns to public.events so the Yodel sync can
-- upsert on a stable key, mirroring public.places (place_id / source).
-- Existing curated rows keep source_id = NULL and are unaffected.
--
-- Idempotent: safe to run more than once. Also runnable as-is in the Supabase
-- SQL editor.

alter table public.events
  add column if not exists source_id text,
  add column if not exists source    text;

-- Unique constraint is the on_conflict target for the upsert. Multiple NULLs
-- are allowed (curated rows), uniqueness enforced only on non-null Yodel ids.
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'events_source_id_key'
  ) then
    alter table public.events
      add constraint events_source_id_key unique (source_id);
  end if;
end $$;

-- Supports the reconcile/deactivation queries that scope to source = 'yodel'.
create index if not exists events_source_idx on public.events (source);
