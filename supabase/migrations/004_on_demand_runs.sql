-- 004: custom topics run on demand, with per-user limits and a global cap (2026-10-04).
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes this for a fresh project.
--
-- Every live run is a row in on_demand_runs, so the limits are counted from one place and can be
-- audited: per user per day, all users per day (runs and dollars) and per month (dollars). A run
-- reserves the most it can cost when it starts and records what it actually cost when it ends; a
-- run that never ends (a crash, a timeout) keeps counting at its reservation. The limits
-- themselves are passed in by the server (agent/limits.py), so they live in reviewed code.
--
-- Visitors are salted hashes of their IP address. They are kept only as long as the limits need
-- them: hashes older than two days are removed from both tables.

-- Players' typed topics are a third kind of topic. Like evergreen topics they never retire.
alter table public.topics drop constraint if exists topics_kind_check;
alter table public.topics
    add constraint topics_kind_check check (kind in ('evergreen', 'news', 'custom'));

create table if not exists public.on_demand_runs (
    id bigint generated always as identity primary key,
    user_hash text,  -- removed after two days
    topic text not null,
    mode text not null check (mode in ('learn', 'quiz')),
    difficulty text not null check (difficulty in ('easy', 'medium', 'hard')),
    started_at timestamptz not null default now(),
    reserved_usd numeric(10, 6) not null check (reserved_usd >= 0),
    -- Set when the run ends; until then the reservation counts.
    finished_at timestamptz,
    spent_usd numeric(10, 6) check (spent_usd >= 0),
    outcome text check (outcome in ('published', 'review', 'discarded', 'failed')),
    run_id bigint references public.runs (id)
);
create index if not exists on_demand_runs_started_at on public.on_demand_runs (started_at);
create index if not exists on_demand_runs_user on public.on_demand_runs (user_hash, started_at);

alter table public.on_demand_runs enable row level security;

-- Start a live run if every limit allows it. Returns {"ok": true, "id": ...} or
-- {"ok": false, "limit": "user_day" | "day_runs" | "day_usd" | "month_usd"}.
-- Starts are serialised with a lock, so two at once cannot both take the last place.
create or replace function public.begin_on_demand_run(
    p_user_hash text,
    p_topic text,
    p_mode text,
    p_difficulty text,
    p_reserve_usd numeric,
    p_user_day_runs integer,
    p_day_runs integer,
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
    v_user_runs integer;
    v_day_runs integer;
    v_day_usd numeric;
    v_month_usd numeric;
    v_id bigint;
begin
    perform pg_advisory_xact_lock(hashtext('public.on_demand_runs'));

    update public.on_demand_runs set user_hash = null
    where user_hash is not null and started_at < now() - interval '2 days';

    select count(*) into v_user_runs from public.on_demand_runs
    where user_hash = p_user_hash and started_at >= v_day;
    if v_user_runs >= p_user_day_runs then
        return jsonb_build_object('ok', false, 'limit', 'user_day');
    end if;

    select count(*), coalesce(sum(coalesce(spent_usd, reserved_usd)), 0)
    into v_day_runs, v_day_usd
    from public.on_demand_runs where started_at >= v_day;
    if v_day_runs >= p_day_runs then
        return jsonb_build_object('ok', false, 'limit', 'day_runs');
    end if;
    if v_day_usd + p_reserve_usd > p_day_usd then
        return jsonb_build_object('ok', false, 'limit', 'day_usd');
    end if;

    select coalesce(sum(coalesce(spent_usd, reserved_usd)), 0) into v_month_usd
    from public.on_demand_runs where started_at >= v_month;
    if v_month_usd + p_reserve_usd > p_month_usd then
        return jsonb_build_object('ok', false, 'limit', 'month_usd');
    end if;

    insert into public.on_demand_runs (user_hash, topic, mode, difficulty, reserved_usd)
    values (p_user_hash, p_topic, p_mode, p_difficulty, p_reserve_usd)
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

revoke all on public.on_demand_runs from anon, authenticated;
grant all on public.on_demand_runs to service_role;
grant usage, select on all sequences in schema public to service_role;

revoke execute on function public.begin_on_demand_run(
    text, text, text, text, numeric, integer, integer, numeric, numeric
) from public, anon, authenticated;
revoke execute on function public.finish_on_demand_run(bigint, numeric, text, bigint)
    from public, anon, authenticated;
revoke execute on function public.hit_request_limit(text, integer)
    from public, anon, authenticated;
grant execute on function public.begin_on_demand_run(
    text, text, text, text, numeric, integer, integer, numeric, numeric
) to service_role;
grant execute on function public.finish_on_demand_run(bigint, numeric, text, bigint)
    to service_role;
grant execute on function public.hit_request_limit(text, integer) to service_role;
