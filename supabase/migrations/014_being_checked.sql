-- 014: a "Being checked" flag on items (2026-11-04, decided by Vedant, docs/handoff/latency.md).
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes this for a fresh project.
--
-- On 2026-11-04, a review queue was cleared in bulk, not read one by one, and 60 of those items
-- are published, so the site shows a small "Being checked" label on an item with
-- this flag set until an audit clears it. Main sets the flag on the 60 rows; this file only adds
-- the column. New items start unflagged.
--
-- Paste this BEFORE the code that selects the column is deployed: the bank reader names
-- being_checked in its select, and a select of a missing column is refused. The other way round is
-- safe: with this pasted and the old code, the old code ignores the column.
--
-- Additive: one new column with a default, so the deployed site keeps working. items already
-- grants select on every column to the browser roles, so the new column is readable without a
-- grant. A rollback is: alter table public.items drop column being_checked;

alter table public.items add column if not exists being_checked boolean not null default false;

-- Read-only check, to run after pasting. Expect one row, data_type boolean, is_nullable NO,
-- column_default false; then the count of flagged items (0 until main sets the 60 rows):
--
--   select column_name, data_type, is_nullable, column_default
--     from information_schema.columns
--    where table_schema = 'public' and table_name = 'items' and column_name = 'being_checked';
--   select count(*) filter (where being_checked) as flagged, count(*) as items from public.items;
