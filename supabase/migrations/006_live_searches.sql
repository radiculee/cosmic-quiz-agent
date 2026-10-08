-- 006: the web page's live searches (2026-10-08).
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes this for a fresh project.
--
-- A search on the web page makes up to four items, one agent run at a time: the explanation at
-- the chosen level and a question at each level (docs/PLAN.md Session 8, "The web page makes
-- whole topics"). The daily limits now count searches, 2 a day per visitor and 4 for everyone,
-- while the dollar caps still count every run: each run reserves the most it can cost until it
-- ends, exactly as in migration 004.
--
-- A run's search is the id of the run that opened it. The first run of a search has no
-- search_id, so it is the one counted; every run before this migration was a search of its own
-- and is counted the same way. A later run passes the search's id and is not counted again. The
-- database still checks that it belongs to the same visitor's search, that the search's earlier
-- runs have ended (one at a time, so a search never reserves more than one run's bound), and that
-- the search has fewer than the most runs a search may have.
--
-- The 9-argument begin_on_demand_run from 004 is left in place, so the deployed site keeps
-- working until this change is deployed. Its runs have no search_id, so they count as searches
-- here. The next migration drops it.

alter table public.on_demand_runs
    add column if not exists search_id bigint references public.on_demand_runs (id);
create index if not exists on_demand_runs_search on public.on_demand_runs (search_id)
    where search_id is not null;

-- Start a live run if every limit allows it. Returns {"ok": true, "id": ...} or {"ok": false,
-- "limit": "user_day" | "day_searches" | "day_usd" | "month_usd" | "search"}. "search" means a
-- later run that cannot join its search. Starts are serialised with a lock, so two at once
-- cannot both take the last place.
create or replace function public.begin_on_demand_run(
    p_user_hash text,
    p_topic text,
    p_mode text,
    p_difficulty text,
    p_search_id bigint,  -- null opens a new search
    p_reserve_usd numeric,
    p_user_day_searches integer,
    p_day_searches integer,
    p_search_runs integer,
    p_day_usd numeric,
    p_month_usd numeric
)
returns jsonb
language plpgsql
set search_path = ''
as $$
declare
    v_day timestamptz := date_trunc('day', now(), 'UTC');
    v_month timestamptz := date_trunc('month', now(), 'UTC');
    v_count integer;
    v_usd numeric;
    v_id bigint;
begin
    perform pg_advisory_xact_lock(hashtext('public.on_demand_runs'));

    update public.on_demand_runs set user_hash = null
    where user_hash is not null and started_at < now() - interval '2 days';

    if p_search_id is null then
        -- A new search counts once, against the visitor's searches today and everyone's.
        select count(*) into v_count from public.on_demand_runs
        where user_hash = p_user_hash and search_id is null and started_at >= v_day;
        if v_count >= p_user_day_searches then
            return jsonb_build_object('ok', false, 'limit', 'user_day');
        end if;
        select count(*) into v_count from public.on_demand_runs
        where search_id is null and started_at >= v_day;
        if v_count >= p_day_searches then
            return jsonb_build_object('ok', false, 'limit', 'day_searches');
        end if;
    else
        -- A later run of a search already counted: the same visitor's search, its earlier runs
        -- ended, and room for one more run.
        if not exists (
            select 1 from public.on_demand_runs
            where id = p_search_id and search_id is null and user_hash = p_user_hash
        ) then
            return jsonb_build_object('ok', false, 'limit', 'search');
        end if;
        select count(*) into v_count from public.on_demand_runs
        where id = p_search_id or search_id = p_search_id;
        if v_count >= p_search_runs or exists (
            select 1 from public.on_demand_runs
            where (id = p_search_id or search_id = p_search_id) and finished_at is null
        ) then
            return jsonb_build_object('ok', false, 'limit', 'search');
        end if;
    end if;

    -- Every run, first or later, must fit today's and this month's dollar caps.
    select coalesce(sum(coalesce(spent_usd, reserved_usd)), 0) into v_usd
    from public.on_demand_runs where started_at >= v_day;
    if v_usd + p_reserve_usd > p_day_usd then
        return jsonb_build_object('ok', false, 'limit', 'day_usd');
    end if;
    select coalesce(sum(coalesce(spent_usd, reserved_usd)), 0) into v_usd
    from public.on_demand_runs where started_at >= v_month;
    if v_usd + p_reserve_usd > p_month_usd then
        return jsonb_build_object('ok', false, 'limit', 'month_usd');
    end if;

    insert into public.on_demand_runs (
        user_hash, topic, mode, difficulty, reserved_usd, search_id
    )
    values (p_user_hash, p_topic, p_mode, p_difficulty, p_reserve_usd, p_search_id)
    returning id into v_id;
    return jsonb_build_object('ok', true, 'id', v_id);
end;
$$;

revoke execute on function public.begin_on_demand_run(
    text, text, text, text, bigint, numeric, integer, integer, integer, numeric, numeric
) from public, anon, authenticated;
grant execute on function public.begin_on_demand_run(
    text, text, text, text, bigint, numeric, integer, integer, integer, numeric, numeric
) to service_role;
