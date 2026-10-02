-- Cosmic Quiz Agent: the question bank and the agent's run history.
--
-- Paste the whole file into the Supabase SQL editor and run it. It is safe to run again: tables
-- and indexes are created only if missing, and functions, triggers and policies are replaced.
-- Later changes go in numbered files under supabase/migrations/.
--
-- Who can do what:
--   * The secret key (service_role) is used only by the Curator and server functions. It
--     bypasses row-level security and writes everything through record_item().
--   * The publishable key (anon) is used by the browser. It can only read published items that
--     have fewer than 2 reports, their sources and checks, and the topics that have such items.
--     Runs, page text, reports and rate limits are never readable with it.

-- --- Tables ---------------------------------------------------------------------------------

-- One row per topic. News topics come from a feed and retire after a while; evergreen topics
-- never retire.
create table if not exists public.topics (
    id bigint generated always as identity primary key,
    name text not null check (length(btrim(name)) between 1 and 200),
    kind text not null check (kind in ('evergreen', 'news')),
    lead_url text,
    retire_after timestamptz,
    created_at timestamptz not null default now()
);
create unique index if not exists topics_name_key on public.topics (lower(name));

-- One Curator invocation (python -m curator build | daily), with its totals and log.
create table if not exists public.curator_runs (
    id bigint generated always as identity primary key,
    trigger text not null check (trigger in ('build', 'daily')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    topics text[] not null default '{}',
    dollar_cap numeric(8, 4) not null,
    jobs_planned integer not null default 0,
    jobs_skipped integer not null default 0,
    jobs_run integer not null default 0,
    published integer not null default 0,
    review integer not null default 0,
    discarded integer not null default 0,
    no_item integer not null default 0,
    retired integer not null default 0,
    anthropic_cost_usd numeric(10, 6) not null default 0,
    typesafe_cost_usd numeric(10, 6) not null default 0,
    stopped_reason text,
    log jsonb not null default '[]'
);

-- One agent run (research plus writing, then verification), whatever its outcome. Holds every
-- metric the v2 analytics page needs, with Anthropic and TypeSafe usage kept separate.
create table if not exists public.runs (
    id bigint generated always as identity primary key,
    -- Made by the Curator once per run, so a payload sent twice is stored once (migration 002).
    client_id uuid,
    topic_id bigint not null references public.topics (id),
    curator_run_id bigint references public.curator_runs (id),
    source text not null check (source in ('curator', 'on_demand')),
    mode text not null check (mode in ('learn', 'quiz')),
    difficulty text not null check (difficulty in ('easy', 'medium', 'hard')),
    model text not null,
    outcome text not null
        check (outcome in ('passed', 'failed_checks', 'no_answer', 'budget_exceeded', 'llm_error')),
    detail text not null default '',
    budget_reason text,
    -- Agent loop (Anthropic)
    model_calls integer not null,
    nudges integer not null default 0,
    input_tokens integer not null,
    output_tokens integer not null,
    cache_write_tokens integer not null,
    cache_read_tokens integer not null,
    agent_cost_usd numeric(10, 6) not null,
    seconds numeric(8, 2) not null,
    tool_calls jsonb not null default '{}',
    tool_errors integer not null default 0,
    pages_by_domain jsonb not null default '{}',
    fetched_urls text[] not null default '{}',
    steps jsonb not null default '[]',
    -- Layer 2 verifier (Anthropic)
    verifier_input_tokens integer not null default 0,
    verifier_output_tokens integer not null default 0,
    verifier_cost_usd numeric(10, 6) not null default 0,
    verifier_seconds numeric(8, 2) not null default 0,
    -- Layer 3 Jev (TypeSafe)
    jev_input_tokens integer not null default 0,
    jev_cost_usd numeric(12, 8) not null default 0,
    jev_seconds numeric(8, 2) not null default 0,
    -- The full stored record minus page text, so the publish decision can be re-scored later.
    record jsonb not null,
    created_at timestamptz not null default now()
);
create unique index if not exists runs_client_id_key on public.runs (client_id);
create index if not exists runs_topic_idx on public.runs (topic_id);
create index if not exists runs_curator_run_idx on public.runs (curator_run_id);
create index if not exists runs_created_idx on public.runs (created_at);

-- The text of each cited page exactly as the agent read it: for audits and re-verification.
-- Never served to the browser.
create table if not exists public.cited_pages (
    run_id bigint not null references public.runs (id) on delete cascade,
    url text not null,
    page_text text not null,
    primary key (run_id, url)
);

-- The bank: one LEARN explanation or one QUIZ question, with every layer's verdict.
create table if not exists public.items (
    id bigint generated always as identity primary key,
    topic_id bigint not null references public.topics (id),
    run_id bigint not null references public.runs (id),
    mode text not null check (mode in ('learn', 'quiz')),
    difficulty text not null check (difficulty in ('easy', 'medium', 'hard')),
    status text not null check (status in ('published', 'review', 'discarded', 'retired')),
    question text,
    options text[],
    correct_index smallint check (correct_index between 0 and 3),
    explanation text not null,
    -- Publish gate (agent/gate.py)
    gate_rule text,
    code_passed boolean not null,
    code_problems text[] not null default '{}',
    haiku_verdict text check (haiku_verdict in ('pass', 'borderline', 'fail', 'error')),
    haiku_reasons text[] not null default '{}',
    jev_verdict text check (jev_verdict in ('pass', 'borderline', 'fail', 'error')),
    jev_reasons text[] not null default '{}',
    jev_model text,
    jev_criteria text,
    jev_threshold numeric(4, 3),
    report_count integer not null default 0,
    created_at timestamptz not null default now(),
    published_at timestamptz,
    retired_at timestamptz,
    reviewed_at timestamptz,  -- when a person moved it out of review (migration 002)
    constraint items_quiz_fields check (
        (mode = 'quiz') = (question is not null and options is not null and correct_index is not null)
    ),
    constraint items_four_options check (options is null or cardinality(options) = 4)
);
create index if not exists items_serving_idx on public.items (status, mode, difficulty);
create index if not exists items_topic_idx on public.items (topic_id);

-- The citations shown with an item: only URLs fetched in its run (enforced in agent/verify.py).
create table if not exists public.sources (
    id bigint generated always as identity primary key,
    item_id bigint not null references public.items (id) on delete cascade,
    ordinal smallint not null,
    url text not null,
    quote text not null,
    unique (item_id, ordinal)
);

-- Every layer's result per claim:
--   code:  each citation (kept, unfetched, misquoted) and each unsupported number
--   haiku: the correct answer (supported, contradicted, not_found), each distractor (wrong,
--          also_correct, unclear) and each explanation problem
--   jev:   each claim (supports, contradicts, says_nothing) with confidence and probabilities
create table if not exists public.claim_checks (
    id bigint generated always as identity primary key,
    item_id bigint not null references public.items (id) on delete cascade,
    layer text not null check (layer in ('code', 'haiku', 'jev')),
    kind text not null
        check (kind in ('citation', 'number', 'correct_answer', 'distractor', 'sentence', 'explanation')),
    claim text not null,
    source_url text,
    verdict text not null,
    confidence numeric(5, 4),
    probabilities jsonb,
    reason text,
    model text
);
create index if not exists claim_checks_item_idx on public.claim_checks (item_id);

-- Player reports. Users are salted hashes of IP addresses, never raw IPs (GDPR). Written only by
-- the server; 2 reports hide an item.
create table if not exists public.reports (
    id bigint generated always as identity primary key,
    item_id bigint not null references public.items (id) on delete cascade,
    user_hash text not null,
    reason text,
    created_at timestamptz not null default now(),
    unique (item_id, user_hash)
);

-- Per-user counters for the on-demand guardrails (Session 6), shared across serverless instances.
create table if not exists public.rate_limits (
    user_hash text not null,
    bucket text not null check (bucket in ('custom_topic_day', 'requests_hour')),
    window_start timestamptz not null,
    count integer not null default 0,
    primary key (user_hash, bucket, window_start)
);

-- --- Triggers -------------------------------------------------------------------------------

-- Keep published_at, retired_at and reviewed_at right when the status changes, including by hand
-- in the table editor.
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

drop trigger if exists items_stamp_status on public.items;
create trigger items_stamp_status
    before insert or update of status on public.items
    for each row execute function public.stamp_item_status();

create or replace function public.count_report()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    update public.items set report_count = report_count + 1 where id = new.item_id;
    return new;
end;
$$;

drop trigger if exists reports_count on public.reports;
create trigger reports_count
    after insert on public.reports
    for each row execute function public.count_report();

-- --- Functions called by the Curator (secret key only) ---------------------------------------

-- Save one agent run and, if it produced an answer, its item, sources and checks, in a single
-- transaction. The payload is built and validated in agent/store.py. A payload whose run was
-- already stored (same client_id) is not stored again: its existing ids are returned.
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

-- Which (topic, mode, difficulty) jobs the Curator has already run, so a build can resume
-- without paying twice. A run that ended in a temporary API error (llm_error) does not count, so
-- the next run retries it.
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

-- Retire published and review items whose topic is past its retire_after date.
create or replace function public.retire_stale()
returns integer
language sql
set search_path = ''
as $$
    with retired as (
        update public.items i
        set status = 'retired'
        from public.topics t
        where t.id = i.topic_id
          and t.retire_after is not null
          and t.retire_after <= now()
          and i.status in ('published', 'review')
        returning i.id
    )
    select count(*)::integer from retired;
$$;

-- --- Row-level security and grants -----------------------------------------------------------

alter table public.topics enable row level security;
alter table public.curator_runs enable row level security;
alter table public.runs enable row level security;
alter table public.cited_pages enable row level security;
alter table public.items enable row level security;
alter table public.sources enable row level security;
alter table public.claim_checks enable row level security;
alter table public.reports enable row level security;
alter table public.rate_limits enable row level security;

drop policy if exists "Published items are readable" on public.items;
create policy "Published items are readable" on public.items
    for select to anon, authenticated
    using (status = 'published' and report_count < 2);

drop policy if exists "Sources of readable items are readable" on public.sources;
create policy "Sources of readable items are readable" on public.sources
    for select to anon, authenticated
    using (exists (
        select 1 from public.items i
        where i.id = sources.item_id and i.status = 'published' and i.report_count < 2
    ));

drop policy if exists "Checks of readable items are readable" on public.claim_checks;
create policy "Checks of readable items are readable" on public.claim_checks
    for select to anon, authenticated
    using (exists (
        select 1 from public.items i
        where i.id = claim_checks.item_id and i.status = 'published' and i.report_count < 2
    ));

drop policy if exists "Topics with readable items are readable" on public.topics;
create policy "Topics with readable items are readable" on public.topics
    for select to anon, authenticated
    using (exists (
        select 1 from public.items i
        where i.topic_id = topics.id and i.status = 'published' and i.report_count < 2
    ));

-- Defence in depth on top of RLS: the browser roles can read four tables and nothing else.
revoke all on all tables in schema public from anon, authenticated;
grant select on public.topics, public.items, public.sources, public.claim_checks
    to anon, authenticated;

grant all on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to service_role;

revoke execute on function public.record_item(jsonb) from public, anon, authenticated;
revoke execute on function public.attempted_jobs(text[]) from public, anon, authenticated;
revoke execute on function public.retire_stale() from public, anon, authenticated;
grant execute on function public.record_item(jsonb) to service_role;
grant execute on function public.attempted_jobs(text[]) to service_role;
grant execute on function public.retire_stale() to service_role;
