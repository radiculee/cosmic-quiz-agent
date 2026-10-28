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
--     Runs, page text, reports and rate limits are never readable with it; the one exception
--     is agent_stats() (migration 007), which returns aggregates of them and nothing else.

-- --- Tables ---------------------------------------------------------------------------------

-- One row per topic. News topics come from a feed and retire after a while; evergreen topics
-- and custom topics (typed by players, migration 004) never retire.
create table if not exists public.topics (
    id bigint generated always as identity primary key,
    name text not null check (length(btrim(name)) between 1 and 200),
    kind text not null,
    lead_url text,
    retire_after timestamptz,
    created_at timestamptz not null default now()
);
create unique index if not exists topics_name_key on public.topics (lower(name));
alter table public.topics drop constraint if exists topics_kind_check;
alter table public.topics
    add constraint topics_kind_check check (kind in ('evergreen', 'news', 'custom'));

-- One Curator invocation (python -m curator build | daily | complete), with its totals and log.
create table if not exists public.curator_runs (
    id bigint generated always as identity primary key,
    trigger text not null,
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
alter table public.curator_runs drop constraint if exists curator_runs_trigger_check;
alter table public.curator_runs
    add constraint curator_runs_trigger_check check (trigger in ('build', 'daily', 'complete'));

-- One agent run (research plus writing, then verification), whatever its outcome. Holds every
-- metric the analytics page needs (Session 9), with Anthropic and TypeSafe usage kept separate.
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
-- the server; 2 reports hide an item. A visitor sends at most 10 a day (api/report.py), and the
-- hash is cleared after 30 days by purge_visitor_hashes() (migration 008).
create table if not exists public.reports (
    id bigint generated always as identity primary key,
    item_id bigint not null references public.items (id) on delete cascade,
    user_hash text,  -- cleared after 30 days
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

-- One row per live run of a custom topic (migration 004). The per-user and global limits are
-- counted from it; a run that never finishes keeps counting at its reservation. Visitor hashes
-- are cleared after a day by purge_visitor_hashes() (migration 008), at most about two days.
create table if not exists public.on_demand_runs (
    id bigint generated always as identity primary key,
    user_hash text,  -- cleared after a day (migration 008)
    topic text not null,
    mode text not null check (mode in ('learn', 'quiz')),
    difficulty text not null check (difficulty in ('easy', 'medium', 'hard')),
    started_at timestamptz not null default now(),
    reserved_usd numeric(10, 6) not null check (reserved_usd >= 0),
    -- Set when the run ends; until then the reservation counts.
    finished_at timestamptz,
    spent_usd numeric(10, 6) check (spent_usd >= 0),
    outcome text check (outcome in ('published', 'review', 'discarded', 'failed')),
    run_id bigint references public.runs (id),
    -- The web page's search this run belongs to, as the id of the run that opened it (migration
    -- 006). Null on that first run, which is the one the daily search limits count.
    search_id bigint references public.on_demand_runs (id)
);
create index if not exists on_demand_runs_started_at on public.on_demand_runs (started_at);
create index if not exists on_demand_runs_user on public.on_demand_runs (user_hash, started_at);
create index if not exists on_demand_runs_search on public.on_demand_runs (search_id)
    where search_id is not null;

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

-- Every slot (mode and difficulty) a listed topic still lacks, with how many runs have tried it
-- and whether an item for it waits in review (migration 009). Learn and Quiz list a topic only
-- when it has none; `python -m curator complete` and `daily` fill them.
create or replace function public.missing_slots()
returns table (
    topic text,
    kind text,
    lead_url text,
    retire_after timestamptz,
    mode text,
    difficulty text,
    attempts integer,
    in_review boolean
)
language sql
stable
set search_path = ''
as $$
    -- A topic is listed once it has a visible item (published, fewer than 2 reports), and a slot
    -- is filled by a visible item. Runs that ended in a temporary API error are not tries.
    with listed as (
        select t.id, t.name, t.kind, t.lead_url, t.retire_after, t.created_at
        from public.topics t
        where (t.retire_after is null or t.retire_after > now())
          and exists (
              select 1 from public.items i
              where i.topic_id = t.id and i.status = 'published' and i.report_count < 2
          )
    ),
    slots as (
        select l.*, m.mode, m.mode_rank, d.difficulty, d.level_rank
        from listed l
        cross join (values ('learn', 1), ('quiz', 2)) as m (mode, mode_rank)
        cross join (values ('easy', 1), ('medium', 2), ('hard', 3)) as d (difficulty, level_rank)
    )
    select
        s.name,
        s.kind,
        s.lead_url,
        s.retire_after,
        s.mode,
        s.difficulty,
        (
            select count(*)::integer from public.runs r
            where r.topic_id = s.id and r.mode = s.mode and r.difficulty = s.difficulty
              and r.outcome <> 'llm_error'
        ),
        exists (
            select 1 from public.items i
            where i.topic_id = s.id and i.mode = s.mode and i.difficulty = s.difficulty
              and i.status = 'review'
        )
    from slots s
    where not exists (
        select 1 from public.items i
        where i.topic_id = s.id and i.mode = s.mode and i.difficulty = s.difficulty
          and i.status = 'published' and i.report_count < 2
    )
    order by s.created_at, s.id, s.mode_rank, s.level_rank;
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

-- Start a live run if every limit allows it (migration 006). A search on the web page is up to
-- four runs, one at a time; the daily limits count searches, by the run that opens each one,
-- and every run reserves the most it can cost against the dollar caps until it ends. Returns
-- {"ok": true, "id": ...} or {"ok": false, "limit": "user_day" | "day_searches" | "day_usd" |
-- "month_usd" | "search"}. "search" means a later run that cannot join its search. Starts are
-- serialised with a lock, so two at once cannot both take the last place.
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

-- Record how a live run ended and what it actually cost. Only the first call for a run counts.
create or replace function public.finish_on_demand_run(
    p_id bigint, p_spent_usd numeric, p_outcome text, p_run_id bigint
)
returns void
language sql
set search_path = ''
as $$
    update public.on_demand_runs
    set finished_at = now(), spent_usd = p_spent_usd, outcome = p_outcome, run_id = p_run_id
    where id = p_id and finished_at is null;
$$;

-- Count one API request for a visitor in the current clock hour. Returns
-- {"allowed": bool, "count": n, "retry_after": seconds until the next hour}.
create or replace function public.hit_request_limit(p_user_hash text, p_limit integer)
returns jsonb
language plpgsql
set search_path = ''
as $$
declare
    v_window timestamptz := date_trunc('hour', now(), 'UTC');
    v_count integer;
begin
    insert into public.rate_limits as r (user_hash, bucket, window_start, count)
    values (p_user_hash, 'requests_hour', v_window, 1)
    on conflict (user_hash, bucket, window_start) do update set count = r.count + 1
    returning r.count into v_count;

    -- Old windows are of no further use; clear them now and then rather than on every request.
    if random() < 0.01 then
        delete from public.rate_limits where window_start < now() - interval '2 days';
    end if;

    return jsonb_build_object(
        'allowed', v_count <= p_limit,
        'count', v_count,
        'retry_after', ceil(extract(epoch from (v_window + interval '1 hour' - now())))::integer
    );
end;
$$;

-- Clear visitor hashes past their time (migration 008), run every day by `python -m curator
-- upkeep` and `daily`, so the retention holds without traffic: live runs' hashes and request
-- windows after 1 day (the limits only count today's), report hashes after 30 days.
create or replace function public.purge_visitor_hashes()
returns jsonb
language plpgsql
set search_path = ''
as $$
declare
    v_runs integer;
    v_windows integer;
    v_reports integer;
begin
    update public.on_demand_runs set user_hash = null
    where user_hash is not null and started_at < now() - interval '1 day';
    get diagnostics v_runs = row_count;

    delete from public.rate_limits where window_start < now() - interval '1 day';
    get diagnostics v_windows = row_count;

    update public.reports set user_hash = null
    where user_hash is not null and created_at < now() - interval '30 days';
    get diagnostics v_reports = row_count;

    return jsonb_build_object(
        'runs', v_runs, 'rate_limit_windows', v_windows, 'reports', v_reports
    );
end;
$$;

-- Re-check an item whose Jev check failed (migration 005, `python -m curator rejev`).
create or replace function public.apply_jev_recheck(p_item_id bigint, p_status text, p_jev jsonb)
returns void
language plpgsql
set search_path = ''
as $$
declare
    v_run_id bigint;
    v_status text;
begin
    select i.run_id, i.status into v_run_id, v_status
    from public.items i where i.id = p_item_id
    for update;
    if not found then
        raise exception 'no item %', p_item_id;
    end if;
    if v_status <> 'review' then
        raise exception 'item % is %, not in review', p_item_id, v_status;
    end if;
    if p_status not in ('published', 'review', 'discarded') then
        raise exception 'not a gate decision: %', p_status;
    end if;

    delete from public.claim_checks where item_id = p_item_id and layer = 'jev';
    insert into public.claim_checks (
        item_id, layer, kind, claim, source_url, verdict, confidence, probabilities, reason, model
    )
    select
        p_item_id, 'jev', c.kind, c.claim, c.source_url, c.verdict, c.confidence,
        c.probabilities, c.reason, c.model
    from jsonb_to_recordset(coalesce(p_jev -> 'checks', '[]'::jsonb)) as c (
        kind text, claim text, source_url text, verdict text, confidence numeric,
        probabilities jsonb, reason text, model text
    );

    update public.runs r
    set jev_input_tokens = r.jev_input_tokens + (p_jev ->> 'input_tokens')::integer,
        jev_cost_usd = r.jev_cost_usd + (p_jev ->> 'cost_usd')::numeric,
        jev_seconds = r.jev_seconds + (p_jev ->> 'seconds')::numeric
    where r.id = v_run_id;

    update public.items
    set status = p_status,
        jev_verdict = p_jev ->> 'verdict',
        jev_reasons = array(select jsonb_array_elements_text(p_jev -> 'reasons')),
        jev_model = p_jev ->> 'model',
        jev_criteria = p_jev ->> 'criteria',
        jev_threshold = (p_jev ->> 'threshold')::numeric
    where id = p_item_id;
    -- The status trigger stamps reviewed_at when an item leaves review; this was not a person.
    update public.items set reviewed_at = null where id = p_item_id;
end;
$$;

-- --- Analytics for nerds (migration 007) ------------------------------------------------------

-- The agent's measured statistics as one jsonb document of aggregates (docs/PLAN.md Session 9).
-- security definer: it reads the private tables for the browser roles, and only aggregates leave
-- it. Filters are null for all; the grid follows p_source and p_days only, and the month's spend
-- ignores every filter. "gate" is what the publish gate decided when the run was stored; "bank"
-- is where those items are now.
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
alter table public.on_demand_runs enable row level security;

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

-- Defence in depth on top of RLS: the browser roles can read four tables and run agent_stats(),
-- and nothing else.
-- topics.lead_url is left out (migration 003): the news article may never have been read, and a
-- player may only see URLs read in a run. Browser queries on topics must name their columns.
revoke all on all tables in schema public from anon, authenticated;
grant select on public.items, public.sources, public.claim_checks to anon, authenticated;
grant select (id, name, kind, retire_after, created_at) on public.topics to anon, authenticated;

grant all on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to service_role;

revoke execute on function public.record_item(jsonb) from public, anon, authenticated;
revoke execute on function public.attempted_jobs(text[]) from public, anon, authenticated;
revoke execute on function public.retire_stale() from public, anon, authenticated;
grant execute on function public.record_item(jsonb) to service_role;
grant execute on function public.attempted_jobs(text[]) to service_role;
grant execute on function public.retire_stale() to service_role;
revoke execute on function public.missing_slots() from public, anon, authenticated;
grant execute on function public.missing_slots() to service_role;
revoke execute on function public.begin_on_demand_run(
    text, text, text, text, bigint, numeric, integer, integer, integer, numeric, numeric
) from public, anon, authenticated;
revoke execute on function public.finish_on_demand_run(bigint, numeric, text, bigint)
    from public, anon, authenticated;
revoke execute on function public.hit_request_limit(text, integer)
    from public, anon, authenticated;
grant execute on function public.begin_on_demand_run(
    text, text, text, text, bigint, numeric, integer, integer, integer, numeric, numeric
) to service_role;
grant execute on function public.finish_on_demand_run(bigint, numeric, text, bigint)
    to service_role;
grant execute on function public.hit_request_limit(text, integer) to service_role;
revoke execute on function public.apply_jev_recheck(bigint, text, jsonb)
    from public, anon, authenticated;
grant execute on function public.apply_jev_recheck(bigint, text, jsonb) to service_role;
revoke execute on function public.purge_visitor_hashes() from public, anon, authenticated;
grant execute on function public.purge_visitor_hashes() to service_role;
-- The one function the browser roles may run (migration 007).
revoke execute on function public.agent_stats(text, text, text, integer)
    from public, anon, authenticated;
grant execute on function public.agent_stats(text, text, text, integer)
    to anon, authenticated, service_role;
