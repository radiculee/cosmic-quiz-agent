-- Check migration 013 on the live bank (2026-11-01). Paste into the Supabase SQL editor after 013
-- and run it once.
--
-- It opens searches for made-up visitors, settles their runs and checks how they count, then
-- always ends by raising an error: an error undoes everything the block did, so no row it wrote is
-- kept, and no visitor's limits or the day's budget are touched. Read the error's text:
--   CHECK PASSED: ...  every check held (the rows are undone)
--   CHECK FAILED: ...  what went wrong (the rows are undone too)
do $$
declare
    v_day timestamptz := date_trunc('day', now(), 'UTC');
    v_plan jsonb := '[
        {"mode": "quiz", "difficulty": "easy"},
        {"mode": "quiz", "difficulty": "medium"}
    ]';
    v_counted integer;
    v_today numeric;
    v_reply jsonb;
    v_ids bigint[];
begin
    -- Everyone's searches today as the function counts them, before this check adds any.
    select count(*) into v_counted from public.on_demand_runs
    where search_id is null and started_at >= v_day and public.on_demand_search_counts(id);

    -- 1. A search still running counts, for the visitor and for everyone.
    v_reply := public.begin_on_demand_search(
        'check-013', 'Check 013', v_plan, 0.17, 1, v_counted + 1, 6, 1000000, 1000000
    );
    if not (v_reply ->> 'ok')::boolean then
        raise exception 'CHECK FAILED: the first search replied %', v_reply;
    end if;
    select array_agg(value::bigint order by ordinality) into v_ids
    from jsonb_array_elements_text(v_reply -> 'ids') with ordinality;
    v_reply := public.begin_on_demand_search(
        'check-013', 'Check 013', v_plan, 0.17, 1, 1000000, 6, 1000000, 1000000
    );
    if v_reply is distinct from '{"ok": false, "limit": "user_day"}'::jsonb then
        raise exception 'CHECK FAILED: a running search, the visitor limit replied %', v_reply;
    end if;
    v_reply := public.begin_on_demand_search(
        'check-013b', 'Check 013', v_plan, 0.17, 1000, v_counted + 1, 6, 1000000, 1000000
    );
    if v_reply is distinct from '{"ok": false, "limit": "day_searches"}'::jsonb then
        raise exception 'CHECK FAILED: a running search, the global limit replied %', v_reply;
    end if;

    -- 2. With one run failed for free and one still going, it still counts.
    perform public.finish_on_demand_run(v_ids[1], 0, 'failed', null);
    if not public.on_demand_search_counts(v_ids[1]) then
        raise exception 'CHECK FAILED: a search with a run still going did not count';
    end if;

    -- 3. Every run failed with nothing spent: it no longer counts, for the visitor or for everyone.
    --    A new search under the same limits now starts. It is left running, so it fills them again.
    perform public.finish_on_demand_run(v_ids[2], 0, 'failed', null);
    if public.on_demand_search_counts(v_ids[1]) then
        raise exception 'CHECK FAILED: a search that failed whole for free still counted';
    end if;
    v_reply := public.begin_on_demand_search(
        'check-013', 'Check 013', v_plan, 0.17, 1, v_counted + 1, 6, 1000000, 1000000
    );
    if not (v_reply ->> 'ok')::boolean then
        raise exception 'CHECK FAILED: after a free search, the same limits replied %', v_reply;
    end if;
    select array_agg(value::bigint order by ordinality) into v_ids
    from jsonb_array_elements_text(v_reply -> 'ids') with ordinality;

    -- 4. A failed run that was billed counts: the model was reached.
    perform public.finish_on_demand_run(v_ids[1], 0, 'failed', null);
    perform public.finish_on_demand_run(v_ids[2], 0.02, 'failed', null);
    if not public.on_demand_search_counts(v_ids[1]) then
        raise exception 'CHECK FAILED: a search with a billed run did not count';
    end if;

    -- 5. A run with another outcome counts, whatever it spent.
    v_reply := public.begin_on_demand_search(
        'check-013c', 'Check 013', v_plan, 0.17, 1000, 1000000, 6, 1000000, 1000000
    );
    select array_agg(value::bigint order by ordinality) into v_ids
    from jsonb_array_elements_text(v_reply -> 'ids') with ordinality;
    perform public.finish_on_demand_run(v_ids[1], 0, 'failed', null);
    perform public.finish_on_demand_run(v_ids[2], 0, 'discarded', null);
    if not public.on_demand_search_counts(v_ids[1]) then
        raise exception 'CHECK FAILED: a search with a discarded run did not count';
    end if;

    -- 6. The dollar caps are as they were: a run still going holds its reservation, whatever the
    --    search counts. With room for one more run ($0.17 of $0.17), the search reserves one; a
    --    further search then finds no room.
    select coalesce(sum(coalesce(spent_usd, reserved_usd)), 0) into v_today
    from public.on_demand_runs where started_at >= v_day;
    v_reply := public.begin_on_demand_search(
        'check-013d', 'Check 013', v_plan, 0.17, 1000, 1000000, 6, v_today + 0.17, 1000000
    );
    if jsonb_array_length(v_reply -> 'ids') <> 1 or v_reply ->> 'limit' is distinct from 'day_usd' then
        raise exception 'CHECK FAILED: the day cap replied %', v_reply;
    end if;
    v_reply := public.begin_on_demand_search(
        'check-013e', 'Check 013', v_plan, 0.17, 1000, 1000000, 6, v_today + 0.17, 1000000
    );
    if v_reply is distinct from '{"ok": false, "limit": "day_usd"}'::jsonb then
        raise exception 'CHECK FAILED: the day cap with a reservation held replied %', v_reply;
    end if;

    raise exception 'CHECK PASSED: running, partly failed, free, billed and discarded searches count as they should, and the dollar caps hold.';
end;
$$;
