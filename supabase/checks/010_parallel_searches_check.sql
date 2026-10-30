-- Check migration 010 on the live bank (2026-10-30). Paste into the Supabase SQL editor after
-- 010 and run it once.
--
-- It calls begin_on_demand_search() for a made-up visitor and checks what it wrote, then always
-- ends by raising an error: an error undoes everything the block did, so no row it reserved is
-- kept, and no visitor's limits or the day's budget are touched. Read the error's text:
--   CHECK PASSED: ...  every check held (the rows are undone)
--   CHECK FAILED: ...  what went wrong (the rows are undone too)
do $$
declare
    v_plan jsonb := '[
        {"mode": "quiz", "difficulty": "easy"},
        {"mode": "quiz", "difficulty": "medium"},
        {"mode": "quiz", "difficulty": "hard"},
        {"mode": "learn", "difficulty": "easy"},
        {"mode": "learn", "difficulty": "medium"},
        {"mode": "learn", "difficulty": "hard"}
    ]';
    v_today numeric;
    v_reply jsonb;
    v_ids bigint[];
    v_rows text;
    v_raised boolean;
    v_estimates jsonb;
begin
    select coalesce(sum(coalesce(spent_usd, reserved_usd)), 0) into v_today
    from public.on_demand_runs where started_at >= date_trunc('day', now(), 'UTC');

    -- 1. A partial fit: a day cap with room for exactly 3 runs at $0.17 ($0.51 of $0.52).
    v_reply := public.begin_on_demand_search(
        'check-010', 'Check 010', v_plan, 0.17, 1000, 1000, 6, v_today + 0.52, 1000000
    );
    if not (v_reply ->> 'ok')::boolean or v_reply ->> 'limit' is distinct from 'day_usd' then
        raise exception 'CHECK FAILED: partial fit replied %', v_reply;
    end if;
    select array_agg(value::bigint order by ordinality) into v_ids
    from jsonb_array_elements_text(v_reply -> 'ids') with ordinality;
    if cardinality(v_ids) <> 3 then
        raise exception 'CHECK FAILED: % ids reserved, expected 3: %', cardinality(v_ids), v_reply;
    end if;

    -- 2. The rows are the first 3 items in plan order, the first opens the search and the others
    --    point at it, each reserving $0.17.
    select string_agg(
        format('%s-%s:%s:%s', r.mode, r.difficulty, coalesce(r.search_id::text, 'null'), r.reserved_usd),
        ' ' order by ids.position
    ) into v_rows
    from unnest(v_ids) with ordinality as ids (id, position)
    join public.on_demand_runs r on r.id = ids.id;
    if v_rows is distinct from format(
        'quiz-easy:null:0.170000 quiz-medium:%1$s:0.170000 quiz-hard:%1$s:0.170000', v_ids[1]
    ) then
        raise exception 'CHECK FAILED: rows were %', v_rows;
    end if;

    -- 3. The search counted once against the visitor: a second search over a limit of 1 is refused
    --    with nothing reserved.
    v_reply := public.begin_on_demand_search(
        'check-010', 'Check 010', v_plan, 0.17, 1, 1000, 6, 1000000, 1000000
    );
    if v_reply is distinct from '{"ok": false, "limit": "user_day"}'::jsonb then
        raise exception 'CHECK FAILED: the visitor limit replied %', v_reply;
    end if;

    -- 4. A bad call raises instead of reserving: an empty plan, and one longer than a search.
    v_raised := false;
    begin
        perform public.begin_on_demand_search(
            'check-010b', 'Check 010', '[]', 0.17, 1000, 1000, 6, 1000000, 1000000
        );
    exception when raise_exception then
        v_raised := true;
    end;
    if not v_raised then
        raise exception 'CHECK FAILED: an empty plan did not raise';
    end if;
    v_raised := false;
    begin
        perform public.begin_on_demand_search(
            'check-010b', 'Check 010', v_plan, 0.17, 1000, 1000, 5, 1000000, 1000000
        );
    exception when raise_exception then
        v_raised := true;
    end;
    if not v_raised then
        raise exception 'CHECK FAILED: a plan longer than a search did not raise';
    end if;

    -- 5. The estimates are an array of numbers per mode and level.
    v_estimates := public.live_run_estimates();
    if jsonb_typeof(v_estimates) is distinct from 'array' then
        raise exception 'CHECK FAILED: live_run_estimates() replied %', v_estimates;
    end if;

    raise exception 'CHECK PASSED: partial fit, plan order, the visitor limit and bad calls all held. Estimates: %',
        v_estimates;
end;
$$;
