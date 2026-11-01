-- 013: a search that failed whole with nothing spent does not count (2026-11-01, decided by
-- Vedant, docs/SESSIONS.md).
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes this for a fresh project. supabase/checks/013_free_failed_searches_check.sql
-- then checks it on the live bank and undoes its own rows.
--
-- On 2026-11-01 the live key was refused: two searches ran, each of their twelve runs failed with
-- nothing spent, and both still took one of the visitor's searches and one of everyone's. So:
--
-- 1. on_demand_search_counts(): whether a search counts. It does unless every run of it has ended
--    as failed with nothing spent. A search still running counts, because its runs have no outcome
--    yet, and so does a stale one whose run was killed.
-- 2. begin_on_demand_search(): counts only such searches, for the visitor's limit and everyone's.
--    Nothing else in it changes. The dollar caps count each run's spend or reservation as before.
--
-- agent/store.py `on_demand_usage` counts the same way, for the quota and the check before a
-- paid step. Paste this before that code is deployed: until then the function counts more than
-- the code does, so the page offers a search the database refuses. The other way round is safe:
-- with this pasted and the old code, the old code only refuses sooner.
--
-- Additive: one new function, and the same signature for the changed one, so the deployed site
-- keeps working and a rollback pastes the function back from 010. begin_on_demand_run (006) is
-- not changed: no code calls it now, and a migration after the launch drops it.

-- Whether a live search counts against the daily search limits. A search counts unless every run
-- of it has ended as failed with nothing spent, which is what a refused key or a model outage
-- leaves (migration 013). A run still going has no outcome yet, so a search still running counts,
-- and so does a stale one whose run was killed. agent/store.py `_counted_searches` is the same
-- rule. The dollar caps do not use it: they count each run's spend or reservation as before.
create or replace function public.on_demand_search_counts(p_search_id bigint)
returns boolean
language sql
stable
set search_path = ''
as $$
    select exists (
        select 1 from public.on_demand_runs r
        where (r.id = p_search_id or r.search_id = p_search_id)
          and (r.outcome is distinct from 'failed' or r.spent_usd is distinct from 0)
    );
$$;

-- Open a live search and reserve its runs. Only the counting of searches differs from 010.
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

    -- The search counts once, against the visitor's searches today and everyone's. A search that
    -- failed whole with nothing spent is not counted (migration 013).
    select count(*) into v_count from public.on_demand_runs
    where user_hash = p_user_hash and search_id is null and started_at >= v_day
      and public.on_demand_search_counts(id);
    if v_count >= p_user_day_searches then
        return jsonb_build_object('ok', false, 'limit', 'user_day');
    end if;
    select count(*) into v_count from public.on_demand_runs
    where search_id is null and started_at >= v_day
      and public.on_demand_search_counts(id);
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

revoke execute on function public.on_demand_search_counts(bigint)
    from public, anon, authenticated;
grant execute on function public.on_demand_search_counts(bigint) to service_role;
