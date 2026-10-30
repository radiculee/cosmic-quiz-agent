-- 010: every run of a live search at once (2026-10-30, docs/PLAN.md "Faster live searches: every
-- run at once").
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes this for a fresh project. supabase/checks/010_parallel_searches_check.sql then
-- checks the new function on the live bank and undoes its own rows.
--
-- A search on the web page now runs all its items at once instead of one at a time, so it ends in
-- about 30 s instead of about 100 s. Each run still reserves the most it can cost ($0.17) until it
-- ends, so the dollar caps hold while runs are in flight; what changes is that a search reserves
-- all its runs together when it starts, in one call under the same lock.
--
-- 1. begin_on_demand_search(): opens a search and reserves its runs in plan order (the questions
--    easiest first, then the explanations easiest first) while the day's and the month's dollar
--    caps allow. It counts the search once against the visitor's and everyone's daily searches,
--    as begin_on_demand_run did for a search's first run. The rows keep 006's shape: the first
--    has a null search_id and is the one the search limits count; the others point at it. So the
--    quota, the purge (008) and agent_stats() (007) read them unchanged.
-- 2. live_run_estimates(): how long one item usually takes, per mode and level, for the page's
--    progress rows. Numbers only.
--
-- Additive: no table, column or existing function changes. begin_on_demand_run (006) stays, so the
-- deployed site keeps working after this is pasted and a rollback is a Vercel revert. A migration
-- after the launch drops it.

-- Open a live search and reserve its runs. p_items is a JSON array of {"mode", "difficulty"} in
-- plan order. Returns {"ok": true, "ids": [...], "limit": null | "day_usd" | "month_usd"} with the
-- ids of the items reserved, in plan order (the first n of p_items), and the cap that refused the
-- rest; or {"ok": false, "limit": "user_day" | "day_searches" | "day_usd" | "month_usd"} when
-- nothing could be reserved. An empty array, or one longer than p_search_runs, is a bug in the
-- caller (it serves the bank when there is nothing to make), so it raises instead of returning a
-- limit. Starts are serialised with the same lock as begin_on_demand_run, so two searches at once
-- cannot both take the last place under a cap, even while both functions are deployed.
create or replace function public.begin_on_demand_search(
    p_user_hash text,
    p_topic text,
    p_items jsonb,
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
    v_day_usd numeric;
    v_month_usd numeric;
    v_item record;
    v_search_id bigint;
    v_id bigint;
    v_ids bigint[] := '{}';
    v_limit text;
begin
    -- Nested, because SQL does not promise to test the conditions of an "or" in order.
    if jsonb_typeof(p_items) is distinct from 'array' then
        raise exception 'begin_on_demand_search: p_items must be a JSON array';
    end if;
    if jsonb_array_length(p_items) not between 1 and p_search_runs then
        raise exception 'begin_on_demand_search: % items; a search has 1 to %',
            jsonb_array_length(p_items), p_search_runs;
    end if;

    perform pg_advisory_xact_lock(hashtext('public.on_demand_runs'));

    update public.on_demand_runs set user_hash = null
    where user_hash is not null and started_at < now() - interval '2 days';

    -- The search counts once, against the visitor's searches today and everyone's.
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

    -- A run still going counts what it reserved; an ended one, what it spent.
    select coalesce(sum(coalesce(spent_usd, reserved_usd)), 0) into v_day_usd
    from public.on_demand_runs where started_at >= v_day;
    select coalesce(sum(coalesce(spent_usd, reserved_usd)), 0) into v_month_usd
    from public.on_demand_runs where started_at >= v_month;

    -- Every run must fit today's and this month's dollar caps; the first that does not ends the
    -- reservation, so the items a cap leaves out are always the last in plan order.
    for v_item in
        select e.item ->> 'mode' as mode, e.item ->> 'difficulty' as difficulty
        from jsonb_array_elements(p_items) with ordinality as e (item, position)
        order by e.position
    loop
        if v_day_usd + p_reserve_usd > p_day_usd then
            v_limit := 'day_usd';
            exit;
        end if;
        if v_month_usd + p_reserve_usd > p_month_usd then
            v_limit := 'month_usd';
            exit;
        end if;
        insert into public.on_demand_runs (
            user_hash, topic, mode, difficulty, reserved_usd, search_id
        )
        values (
            p_user_hash, p_topic, v_item.mode, v_item.difficulty, p_reserve_usd, v_search_id
        )
        returning id into v_id;
        v_search_id := coalesce(v_search_id, v_id);
        v_ids := v_ids || v_id;
        v_day_usd := v_day_usd + p_reserve_usd;
        v_month_usd := v_month_usd + p_reserve_usd;
    end loop;

    if cardinality(v_ids) = 0 then
        return jsonb_build_object('ok', false, 'limit', v_limit);
    end if;
    return jsonb_build_object('ok', true, 'ids', to_jsonb(v_ids), 'limit', v_limit);
end;
$$;

revoke execute on function public.begin_on_demand_search(
    text, text, jsonb, numeric, integer, integer, integer, numeric, numeric
) from public, anon, authenticated;
grant execute on function public.begin_on_demand_search(
    text, text, jsonb, numeric, integer, integer, integer, numeric, numeric
) to service_role;

-- How long one item usually takes, per mode and level: the median over the last 30 days of runs
-- of the agent's time plus the verifiers' (Jev runs beside the Haiku verifier, so the longer of
-- the two), with how many runs it is drawn from. Runs that ended in a temporary API error are
-- left out. Returns [{"mode", "difficulty", "median_seconds", "runs"}]. The site reads it at most
-- once an hour per server and uses 17 s for a level with fewer than 5 runs (agent/ondemand.py).
create or replace function public.live_run_estimates()
returns jsonb
language sql
stable
set search_path = ''
as $$
    select coalesce(
        jsonb_agg(
            jsonb_build_object(
                'mode', cells.mode,
                'difficulty', cells.difficulty,
                'median_seconds', round(cells.median::numeric, 1),
                'runs', cells.runs
            )
            order by cells.mode, cells.difficulty
        ),
        '[]'::jsonb
    )
    from (
        select
            r.mode,
            r.difficulty,
            percentile_cont(0.5) within group (
                order by (r.seconds + greatest(r.verifier_seconds, r.jev_seconds))::double precision
            ) as median,
            count(*) as runs
        from public.runs r
        where r.created_at >= now() - interval '30 days'
          and r.outcome <> 'llm_error'
        group by r.mode, r.difficulty
    ) as cells;
$$;

revoke execute on function public.live_run_estimates() from public, anon, authenticated;
grant execute on function public.live_run_estimates() to service_role;
