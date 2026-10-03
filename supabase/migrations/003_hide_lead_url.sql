-- 003: hide news topics' article links from the browser (2026-10-02).
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes this for a fresh project.
--
-- topics.lead_url is the feed article a news topic came from. The agent is pointed at it but may
-- never read it (a blocked page, a redirect off the allow-list), and the citation rule says a
-- player may only see URLs read in a run. So the browser roles get every topics column except
-- lead_url; the Curator (secret key) still reads it. Browser queries must name their columns:
-- `select=*` on topics is refused for them.

revoke select on public.topics from anon, authenticated;
grant select (id, name, kind, retire_after, created_at) on public.topics to anon, authenticated;
