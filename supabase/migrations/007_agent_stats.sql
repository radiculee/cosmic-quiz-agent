-- 007: Analytics for nerds (2026-10-08).
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes this for a fresh project.
--
-- agent_stats() returns the agent's measured statistics (docs/PLAN.md Session 9) as one jsonb
-- document of aggregates: counts, sums, medians, percentiles and histograms. It is `security
-- definer`, so it reads the private tables (runs, items, claim_checks, on_demand_runs) on the
-- caller's behalf, and it is the only way the browser roles can see anything of them. No row,
-- topic name, URL, visitor hash, step log or page text ever leaves it.
--
-- Filters, each null for all: p_mode ('learn' | 'quiz'), p_difficulty ('easy' | 'medium' |
-- 'hard'), p_source ('curator' | 'on_demand') and p_days (the last p_days days; null for all
-- time). The mode-and-difficulty grid follows p_source and p_days only, and the month's spend
-- ignores every filter: it is set against the monthly caps.
--
-- "gate" counts what the publish gate decided when each run was stored (runs.record); "bank"
-- counts where those items are now, after people decided the review queue. The verifier
-- verdicts are also the gate's, as stored with the run. Jev's claim checks are the current ones
-- (`curator rejev` replaces checks that failed to run, migration 005).
--
-- It also drops the 9-argument begin_on_demand_run from 004, which 006 kept for the site that
-- was deployed before the searches change. The searches change is deployed (4d5fd8f), and it
-- calls the 11-argument version only.

create or replace function public.agent_stats(
    p_mode text default null,
    p_difficulty text default null,
    p_source text default null,
    p_days integer default null
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
    v_since timestamptz := '-infinity';
    v_month timestamptz := date_trunc('month', now(), 'UTC');
begin
    if p_mode is not null and p_mode not in ('learn', 'quiz') then
        raise exception 'p_mode must be learn, quiz or null';
    end if;
    if p_difficulty is not null and p_difficulty not in ('easy', 'medium', 'hard') then
        raise exception 'p_difficulty must be easy, medium, hard or null';
    end if;
    if p_source is not null and p_source not in ('curator', 'on_demand') then
        raise exception 'p_source must be curator, on_demand or null';
    end if;
    if p_days is not null and p_days not between 1 and 3660 then
        raise exception 'p_days must be between 1 and 3660, or null';
    end if;
    if p_days is not null then
        v_since := now() - make_interval(days => p_days);
    end if;

    return (
        with
        -- The runs in the period and source. Only the columns the figures need: the stored
        -- record is large, so just the gate's decision and verdicts are taken from it.
        scope as (
            select
                r.id, r.mode, r.difficulty, r.model, r.outcome, r.budget_reason,
                r.model_calls, r.nudges, r.input_tokens, r.output_tokens,
                r.cache_write_tokens, r.cache_read_tokens, r.agent_cost_usd, r.seconds,
                r.pages_by_domain, r.steps, r.verifier_input_tokens, r.verifier_output_tokens,
                r.verifier_cost_usd, r.verifier_seconds, r.jev_input_tokens, r.jev_cost_usd,
                r.jev_seconds, r.created_at,
                r.record ->> 'status' as gate_status,
                r.record -> 'verification' -> 'haiku' as haiku,
                r.record -> 'verification' -> 'jev' ->> 'verdict' as jev_verdict
            from public.runs r
            where r.created_at >= v_since
              and (p_source is null or r.source = p_source)
        ),
        -- The runs every figure except the grid is built from.
        picked as (
            select * from scope
            where (p_mode is null or mode = p_mode)
              and (p_difficulty is null or difficulty = p_difficulty)
        ),
        -- Every logged step of those runs: model calls and tool calls.
        steps as (
            select
                s ->> 'kind' as kind,
                s ->> 'tool' as tool,
                (s ->> 'seconds')::double precision as seconds,
                coalesce((s ->> 'is_error')::boolean, false) as is_error,
                -- A model step's summary is "tool_a, tool_b (stop: tool_use)".
                split_part(s ->> 'summary', ' (stop:', 1) as called
            from picked p
            cross join lateral jsonb_array_elements(p.steps) as s
        ),
        answers as (
            select i.id, i.status
            from public.items i
            join picked p on p.id = i.run_id
        ),
        checks as (
            select c.item_id, c.layer, c.kind, c.verdict, c.confidence
            from public.claim_checks c
            join answers a on a.id = c.item_id
        ),
        volume as (
            select jsonb_build_object(
                'runs', count(*),
                'first_run_at', min(created_at),
                'last_run_at', max(created_at),
                'outcomes', jsonb_build_object(
                    'passed', count(*) filter (where outcome = 'passed'),
                    'failed_checks', count(*) filter (where outcome = 'failed_checks'),
                    'no_answer', count(*) filter (where outcome = 'no_answer'),
                    'budget_exceeded', count(*) filter (where outcome = 'budget_exceeded'),
                    'llm_error', count(*) filter (where outcome = 'llm_error')
                ),
                'gate', jsonb_build_object(
                    'published', count(*) filter (where gate_status = 'published'),
                    'review', count(*) filter (where gate_status = 'review'),
                    'discarded', count(*) filter (where gate_status = 'discarded')
                ),
                'cost', jsonb_build_object(
                    'agent_usd', coalesce(sum(agent_cost_usd), 0),
                    'verifier_usd', coalesce(sum(verifier_cost_usd), 0),
                    'jev_usd', coalesce(sum(jev_cost_usd), 0)
                )
            ) as doc
            from picked
        ),
        bank as (
            select jsonb_build_object(
                'published', count(*) filter (where status = 'published'),
                'review', count(*) filter (where status = 'review'),
                'discarded', count(*) filter (where status = 'discarded'),
                'retired', count(*) filter (where status = 'retired')
            ) as doc
            from answers
        ),
        -- Token sums per model, so the API can price the caching savings from config.
        models as (
            select coalesce(
                jsonb_agg(
                    jsonb_build_object(
                        'model', m.model,
                        'runs', m.runs,
                        'input_tokens', m.input_tokens,
                        'output_tokens', m.output_tokens,
                        'cache_write_tokens', m.cache_write_tokens,
                        'cache_read_tokens', m.cache_read_tokens,
                        'agent_usd', m.agent_usd
                    )
                    order by m.runs desc, m.model
                ),
                '[]'::jsonb
            ) as doc
            from (
                select
                    model,
                    count(*) as runs,
                    sum(input_tokens) as input_tokens,
                    sum(output_tokens) as output_tokens,
                    sum(cache_write_tokens) as cache_write_tokens,
                    sum(cache_read_tokens) as cache_read_tokens,
                    sum(agent_cost_usd) as agent_usd
                from picked
                group by model
            ) as m
        ),
        tokens as (
            select jsonb_build_object(
                'by_model', (select doc from models),
                'verifier_input_tokens', coalesce(sum(verifier_input_tokens), 0),
                'verifier_output_tokens', coalesce(sum(verifier_output_tokens), 0),
                'jev_input_tokens', coalesce(sum(jev_input_tokens), 0)
            ) as doc
            from picked
        ),
        tools as (
            select coalesce(
                jsonb_agg(
                    jsonb_build_object(
                        'tool', t.tool,
                        'calls', t.calls,
                        'errors', t.errors,
                        'median', t.median,
                        'p95', t.p95
                    )
                    order by t.calls desc, t.tool
                ),
                '[]'::jsonb
            ) as doc
            from (
                select
                    tool,
                    count(*) as calls,
                    count(*) filter (where is_error) as errors,
                    percentile_cont(0.5) within group (order by seconds) as median,
                    percentile_cont(0.95) within group (order by seconds) as p95
                from steps
                where kind = 'tool' and tool is not null
                group by tool
            ) as t
        ),
        speed as (
            select jsonb_build_object(
                'run_seconds', (
                    select jsonb_build_object(
                        'median', percentile_cont(0.5) within group (order by seconds::double precision),
                        'p95', percentile_cont(0.95) within group (order by seconds::double precision)
                    )
                    from picked
                ),
                'total_seconds', (
                    select jsonb_build_object(
                        'median', percentile_cont(0.5) within group (
                            order by (seconds + verifier_seconds + jev_seconds)::double precision
                        ),
                        'p95', percentile_cont(0.95) within group (
                            order by (seconds + verifier_seconds + jev_seconds)::double precision
                        )
                    )
                    from picked
                ),
                'model_call_seconds', (
                    select jsonb_build_object(
                        'median', percentile_cont(0.5) within group (order by seconds),
                        'p95', percentile_cont(0.95) within group (order by seconds)
                    )
                    from steps
                    where kind = 'model'
                ),
                'verifier_seconds', (
                    select jsonb_build_object(
                        'median', percentile_cont(0.5) within group (order by verifier_seconds::double precision),
                        'p95', percentile_cont(0.95) within group (order by verifier_seconds::double precision)
                    )
                    from picked
                    where verifier_seconds > 0
                ),
                'jev_seconds', (
                    select jsonb_build_object(
                        'median', percentile_cont(0.5) within group (order by jev_seconds::double precision),
                        'p95', percentile_cont(0.95) within group (order by jev_seconds::double precision)
                    )
                    from picked
                    where jev_seconds > 0
                ),
                'tools', (select doc from tools)
            ) as doc
        ),
        behaviour as (
            select jsonb_build_object(
                -- How many runs made each number of model calls.
                'model_calls', (
                    select coalesce(
                        jsonb_agg(jsonb_build_object('calls', h.calls, 'runs', h.runs) order by h.calls),
                        '[]'::jsonb
                    )
                    from (
                        select model_calls as calls, count(*) as runs
                        from picked
                        group by model_calls
                    ) as h
                ),
                'model_steps', (select count(*) from steps where kind = 'model'),
                'tool_steps', (
                    select count(*) from steps where kind = 'model' and called <> 'no tool calls'
                ),
                -- Model calls that asked for two or more tools at once.
                'parallel_steps', (
                    select count(*) from steps where kind = 'model' and called like '%, %'
                ),
                'pages_by_domain', (
                    select coalesce(
                        jsonb_agg(
                            jsonb_build_object('domain', d.domain, 'pages', d.pages)
                            order by d.pages desc, d.domain
                        ),
                        '[]'::jsonb
                    )
                    from (
                        select e.key as domain, sum(e.value::integer) as pages
                        from picked p
                        cross join lateral jsonb_each_text(p.pages_by_domain) as e
                        group by e.key
                    ) as d
                ),
                'nudges', (select coalesce(sum(nudges), 0) from picked),
                'nudged_runs', (select count(*) from picked where nudges > 0),
                -- Which budget ran out: "step", "time" or "token" (agent/loop.py).
                'budgets', (
                    select coalesce(
                        jsonb_agg(jsonb_build_object('budget', b.budget, 'runs', b.runs) order by b.budget),
                        '[]'::jsonb
                    )
                    from (
                        select split_part(budget_reason, ' ', 1) as budget, count(*) as runs
                        from picked
                        where outcome = 'budget_exceeded' and budget_reason is not null
                        group by 1
                    ) as b
                ),
                'answers', (select count(*) from answers),
                'citations', (
                    select jsonb_build_object(
                        'kept', count(*) filter (where verdict = 'kept'),
                        'misquoted', count(*) filter (where verdict = 'misquoted'),
                        'unfetched', count(*) filter (where verdict = 'unfetched')
                    )
                    from checks
                    where layer = 'code' and kind = 'citation'
                ),
                -- Answers with a number that none of the pages read contains.
                'unsupported_number_answers', (
                    select count(distinct item_id)
                    from checks
                    where layer = 'code' and kind = 'number'
                )
            ) as doc
        ),
        verifiers as (
            select jsonb_build_object(
                'haiku', (
                    select jsonb_build_object(
                        'pass', count(*) filter (where haiku ->> 'verdict' = 'pass'),
                        'borderline', count(*) filter (where haiku ->> 'verdict' = 'borderline'),
                        'fail', count(*) filter (where haiku ->> 'verdict' = 'fail'),
                        'error', count(*) filter (where haiku ->> 'verdict' = 'error')
                    )
                    from picked
                    where jsonb_typeof(haiku) = 'object'
                ),
                'jev', (
                    select jsonb_build_object(
                        'pass', count(*) filter (where jev_verdict = 'pass'),
                        'borderline', count(*) filter (where jev_verdict = 'borderline'),
                        'fail', count(*) filter (where jev_verdict = 'fail'),
                        'error', count(*) filter (where jev_verdict = 'error')
                    )
                    from picked
                    where jev_verdict is not null
                ),
                -- Haiku's verdict against Jev's, for items both layers judged.
                'agreement', (
                    select coalesce(
                        jsonb_agg(
                            jsonb_build_object('haiku', a.haiku, 'jev', a.jev, 'items', a.items)
                            order by a.haiku, a.jev
                        ),
                        '[]'::jsonb
                    )
                    from (
                        select haiku ->> 'verdict' as haiku, jev_verdict as jev, count(*) as items
                        from picked
                        where jsonb_typeof(haiku) = 'object' and jev_verdict is not null
                        group by 1, 2
                    ) as a
                ),
                'jev_claims', (
                    select coalesce(
                        jsonb_agg(
                            jsonb_build_object('kind', j.kind, 'verdict', j.verdict, 'checks', j.checks)
                            order by j.kind, j.verdict
                        ),
                        '[]'::jsonb
                    )
                    from (
                        select kind, verdict, count(*) as checks
                        from checks
                        where layer = 'jev'
                        group by kind, verdict
                    ) as j
                ),
                -- Jev's confidence in ten bins of 0.1; the last bin includes 1.0.
                'jev_confidence', (
                    select jsonb_build_object(
                        'bins', (
                            select jsonb_agg(coalesce(b.checks, 0) order by g.bin)
                            from generate_series(1, 10) as g (bin)
                            left join (
                                select least(width_bucket(confidence, 0, 1, 10), 10) as bin,
                                       count(*) as checks
                                from checks
                                where layer = 'jev' and confidence is not null
                                group by 1
                            ) as b on b.bin = g.bin
                        ),
                        'exactly_one', (
                            select count(*) from checks where layer = 'jev' and confidence = 1
                        )
                    )
                ),
                -- Why the gate sent items to review. An item can have several reasons.
                'review', (
                    select jsonb_build_object(
                        'items', count(*),
                        'haiku_doubt', count(*) filter (where haiku ->> 'verdict' = 'borderline'),
                        'jev_doubt', count(*) filter (where jev_verdict = 'borderline'),
                        'verifier_error', count(*) filter (
                            where haiku ->> 'verdict' = 'error'
                               or jev_verdict = 'error'
                               or jev_verdict is null
                        ),
                        'explanation', count(*) filter (
                            where jsonb_array_length(
                                coalesce(haiku -> 'explanation_problems', '[]'::jsonb)
                            ) > 0
                        ),
                        -- A wrong option Haiku could not settle from the sources.
                        'unsettled_option', count(*) filter (
                            where coalesce(haiku -> 'distractors', '[]'::jsonb)
                                @> '[{"verdict": "unclear"}]'::jsonb
                        ),
                        'verifier_quote', count(*) filter (
                            where haiku ->> 'answer_verdict' = 'supported'
                              and (haiku ->> 'answer_quote_verbatim')::boolean is false
                        )
                    )
                    from picked
                    where gate_status = 'review'
                )
            ) as doc
        ),
        -- Every mode and difficulty side by side, in the chosen source and period.
        grid as (
            select coalesce(
                jsonb_agg(
                    jsonb_build_object(
                        'mode', g.mode,
                        'difficulty', g.difficulty,
                        'runs', g.runs,
                        'published', g.published,
                        'anthropic_usd', g.anthropic_usd,
                        'jev_usd', g.jev_usd,
                        'median_seconds', g.median_seconds
                    )
                    order by g.mode, array_position(array['easy', 'medium', 'hard'], g.difficulty)
                ),
                '[]'::jsonb
            ) as doc
            from (
                select
                    mode,
                    difficulty,
                    count(*) as runs,
                    count(*) filter (where gate_status = 'published') as published,
                    sum(agent_cost_usd + verifier_cost_usd) as anthropic_usd,
                    sum(jev_cost_usd) as jev_usd,
                    percentile_cont(0.5) within group (order by seconds::double precision)
                        as median_seconds
                from scope
                group by mode, difficulty
            ) as g
        ),
        -- This month's recorded spend in UTC, whatever the filters, for the monthly caps. Live
        -- research is counted as begin_on_demand_run counts it.
        budget as (
            select jsonb_build_object(
                'month_start', v_month,
                'anthropic_usd', coalesce((
                    select sum(agent_cost_usd + verifier_cost_usd)
                    from public.runs
                    where created_at >= v_month
                ), 0),
                'typesafe_usd', coalesce((
                    select sum(jev_cost_usd) from public.runs where created_at >= v_month
                ), 0),
                'typesafe_all_time_usd', coalesce((select sum(jev_cost_usd) from public.runs), 0),
                'live_usd', coalesce((
                    select sum(coalesce(spent_usd, reserved_usd))
                    from public.on_demand_runs
                    where started_at >= v_month
                ), 0)
            ) as doc
        )
        select jsonb_build_object(
            'filters', jsonb_build_object(
                'mode', p_mode, 'difficulty', p_difficulty, 'source', p_source, 'days', p_days
            ),
            'generated_at', now(),
            'volume', (select doc from volume),
            'bank', (select doc from bank),
            'tokens', (select doc from tokens),
            'speed', (select doc from speed),
            'behaviour', (select doc from behaviour),
            'verifiers', (select doc from verifiers),
            'grid', (select doc from grid),
            'budget', (select doc from budget)
        )
    );
end;
$$;

-- The one function the browser roles may run. Supabase grants new functions to anon and
-- authenticated by default, so execute is revoked from everyone first and granted back by name.
revoke execute on function public.agent_stats(text, text, text, integer)
    from public, anon, authenticated;
grant execute on function public.agent_stats(text, text, text, integer)
    to anon, authenticated, service_role;

-- The 004 version, which counted live runs rather than searches. Nothing calls it any more.
drop function if exists public.begin_on_demand_run(
    text, text, text, text, numeric, integer, integer, numeric, numeric
);
