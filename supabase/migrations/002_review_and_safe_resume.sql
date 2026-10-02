-- 002: review timestamps, safe re-sends and retries (2026-10-02). Replaces the earlier
-- 002_reviewed_at.sql, which was never applied.
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes all of this for a fresh project.
--
-- 1. items.reviewed_at: set by the status trigger whenever an item moves from review to published
--    or discarded, whether through `python -m curator review` or by hand in the table editor.
-- 2. runs.client_id: a key the Curator makes once per run. record_item() returns the stored rows
--    instead of inserting again when a payload is re-sent after an unclear failure.
-- 3. attempted_jobs(): a run that ended in a temporary API error (llm_error) no longer counts as
--    done, so the next build retries it.

alter table public.items add column if not exists reviewed_at timestamptz;
alter table public.runs add column if not exists client_id uuid;
create unique index if not exists runs_client_id_key on public.runs (client_id);

create or replace function public.stamp_item_status()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    if new.status = 'published' and new.published_at is null then
        new.published_at := now();
    end if;
    if new.status = 'retired' and new.retired_at is null then
        new.retired_at := now();
    end if;
    if tg_op = 'UPDATE' and old.status = 'review' and new.status in ('published', 'discarded') then
        new.reviewed_at := now();
    end if;
    return new;
end;
$$;

create or replace function public.record_item(payload jsonb)
returns jsonb
language plpgsql
set search_path = ''
as $$
declare
    v_topic_id bigint;
    v_run_id bigint;
    v_item_id bigint;
begin
    select r.id, r.topic_id into v_run_id, v_topic_id
    from public.runs r
    where r.client_id = (payload -> 'run' ->> 'client_id')::uuid;
    if found then
        select i.id into v_item_id from public.items i where i.run_id = v_run_id;
        return jsonb_build_object(
            'topic_id', v_topic_id, 'run_id', v_run_id, 'item_id', v_item_id, 'duplicate', true
        );
    end if;

    -- An existing topic is reused as it is; the no-op update makes RETURNING give its id.
    insert into public.topics as existing (name, kind, lead_url, retire_after)
    select t.name, t.kind, t.lead_url, t.retire_after
    from jsonb_to_record(payload -> 'topic')
        as t (name text, kind text, lead_url text, retire_after timestamptz)
    on conflict ((lower(name))) do update set name = existing.name
    returning id into v_topic_id;

    insert into public.runs (
        client_id, topic_id, curator_run_id, source, mode, difficulty, model, outcome, detail,
        budget_reason, model_calls, nudges, input_tokens, output_tokens, cache_write_tokens,
        cache_read_tokens, agent_cost_usd, seconds, tool_calls, tool_errors, pages_by_domain,
        fetched_urls, steps, verifier_input_tokens, verifier_output_tokens, verifier_cost_usd,
        verifier_seconds, jev_input_tokens, jev_cost_usd, jev_seconds, record
    )
    select
        r.client_id, v_topic_id, r.curator_run_id, r.source, r.mode, r.difficulty, r.model, r.outcome,
        r.detail, r.budget_reason, r.model_calls, r.nudges, r.input_tokens, r.output_tokens,
        r.cache_write_tokens, r.cache_read_tokens, r.agent_cost_usd, r.seconds, r.tool_calls,
        r.tool_errors, r.pages_by_domain, r.fetched_urls, r.steps, r.verifier_input_tokens,
        r.verifier_output_tokens, r.verifier_cost_usd, r.verifier_seconds, r.jev_input_tokens,
        r.jev_cost_usd, r.jev_seconds, r.record
    from jsonb_to_record(payload -> 'run') as r (
        client_id uuid, curator_run_id bigint, source text, mode text, difficulty text, model text,
        outcome text, detail text, budget_reason text, model_calls integer, nudges integer,
        input_tokens integer, output_tokens integer, cache_write_tokens integer,
        cache_read_tokens integer, agent_cost_usd numeric, seconds numeric, tool_calls jsonb,
        tool_errors integer, pages_by_domain jsonb, fetched_urls text[], steps jsonb,
        verifier_input_tokens integer, verifier_output_tokens integer,
        verifier_cost_usd numeric, verifier_seconds numeric, jev_input_tokens integer,
        jev_cost_usd numeric, jev_seconds numeric, record jsonb
    )
    returning id into v_run_id;

    insert into public.cited_pages (run_id, url, page_text)
    select v_run_id, p.url, p.page_text
    from jsonb_to_recordset(coalesce(payload -> 'cited_pages', '[]'::jsonb))
        as p (url text, page_text text);

    if jsonb_typeof(payload -> 'item') = 'object' then
        insert into public.items (
            topic_id, run_id, mode, difficulty, status, question, options, correct_index,
            explanation, gate_rule, code_passed, code_problems, haiku_verdict, haiku_reasons,
            jev_verdict, jev_reasons, jev_model, jev_criteria, jev_threshold
        )
        select
            v_topic_id, v_run_id, i.mode, i.difficulty, i.status, i.question, i.options,
            i.correct_index, i.explanation, i.gate_rule, i.code_passed, i.code_problems,
            i.haiku_verdict, i.haiku_reasons, i.jev_verdict, i.jev_reasons, i.jev_model,
            i.jev_criteria, i.jev_threshold
        from jsonb_to_record(payload -> 'item') as i (
            mode text, difficulty text, status text, question text, options text[],
            correct_index smallint, explanation text, gate_rule text, code_passed boolean,
            code_problems text[], haiku_verdict text, haiku_reasons text[], jev_verdict text,
            jev_reasons text[], jev_model text, jev_criteria text, jev_threshold numeric
        )
        returning id into v_item_id;

        insert into public.sources (item_id, ordinal, url, quote)
        select v_item_id, s.ordinal, s.url, s.quote
        from jsonb_to_recordset(payload -> 'item' -> 'sources')
            as s (ordinal smallint, url text, quote text);

        insert into public.claim_checks (
            item_id, layer, kind, claim, source_url, verdict, confidence, probabilities, reason,
            model
        )
        select
            v_item_id, c.layer, c.kind, c.claim, c.source_url, c.verdict, c.confidence,
            c.probabilities, c.reason, c.model
        from jsonb_to_recordset(payload -> 'item' -> 'claim_checks') as c (
            layer text, kind text, claim text, source_url text, verdict text,
            confidence numeric, probabilities jsonb, reason text, model text
        );
    end if;

    return jsonb_build_object(
        'topic_id', v_topic_id, 'run_id', v_run_id, 'item_id', v_item_id, 'duplicate', false
    );
end;
$$;

create or replace function public.attempted_jobs(topic_names text[])
returns table (topic text, mode text, difficulty text)
language sql
stable
set search_path = ''
as $$
    select distinct t.name, r.mode, r.difficulty
    from public.runs r
    join public.topics t on t.id = r.topic_id
    where r.source = 'curator'
      and r.outcome <> 'llm_error'
      and lower(t.name) in (select lower(n) from unnest(topic_names) as n);
$$;

revoke execute on function public.record_item(jsonb) from public, anon, authenticated;
revoke execute on function public.attempted_jobs(text[]) from public, anon, authenticated;
grant execute on function public.record_item(jsonb) to service_role;
grant execute on function public.attempted_jobs(text[]) to service_role;
