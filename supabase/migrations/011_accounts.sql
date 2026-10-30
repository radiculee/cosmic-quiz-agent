-- 011: optional accounts (2026-10-30, docs/SESSIONS.md, Decisions, 2026-10-30, data).
--
-- Paste into the Supabase SQL editor and run it once, after 010; it is safe to run again.
-- supabase/schema.sql will include it for a fresh project once latency folds it in.
--
-- A signed-in player's progress, one row per thing that happened, so the browser can rebuild the
-- profile by replaying it through the pure functions in src/profile.ts (points, streaks,
-- trophies, and the topics played, read and seen all come out of the replay):
--
--   * player_answers:   one quiz answer.
--   * player_reads:     one explanation read in LEARN or on the web page.
--   * player_runs:      one quiz run answered to the last question, with its clock time.
--   * player_searches:  one live search on the web page that made something.
--   * player_baselines: what one browser held before it kept a history (a profile saved before
--                       accounts), added once when that browser first signs in.
--
-- Each event row's id is a UUID made in the browser, and the browser inserts with "on conflict
-- do nothing", so sending a row twice (a retry, or signing in again) changes nothing. A baseline
-- is keyed on (user_id, guest_id); the browser makes a new guest id after each merge, so later
-- guest progress in the same browser is never mistaken for one already added.
--
-- Access: every row belongs to auth.users and goes when the account is deleted (on delete
-- cascade; api/account.py deletes the auth user with the secret key after agent/auth.py checks
-- the player's token). Signed-in players may read and add their own rows and nothing else: no
-- update and no delete, and visitors who are not signed in get nothing.
--
-- Retention: rows are kept until the player deletes the account (decided by Vedant on
-- 2026-10-30; a purge of long-inactive accounts is a follow-up after the launch). The limits on
-- live searches key a signed-in player by a salted hash of the user id, never the id itself, in
-- on_demand_runs.user_hash; those rows are not player data and stay after an account is deleted,
-- and purge_visitor_hashes() (008) clears the hash after a day as for any visitor.
--
-- Row caps, so a scripted account cannot fill the free tier's 500 MB. Far above what a person
-- plays; counted per account from midnight UTC, except baselines:
--
--   * player_answers    2,000 a day
--   * player_reads        500 a day
--   * player_runs         200 a day
--   * player_searches      50 a day
--   * player_baselines     20 in all
--
-- A row over its cap is refused with SQLSTATE CQ001 (PostgREST answers HTTP 400 with "code":
-- "CQ001"). The browser treats that as final: it drops the row, logs it once and does not retry.
-- Two inserts at the same moment can both pass the count, so a cap can be passed by a row or two.

-- --- Tables --------------------------------------------------------------------------------------

-- correct and points are what the browser worked out, kept so the profile can be replayed. They
-- are not trusted: a future leaderboard must re-score every answer on the server from item_id and
-- choice (against items.correct_index), never from these two columns. item_id is the source of
-- truth for the topic; topic is a snapshot of its name when answered, since topics get renamed
-- (009 renamed seven). Items are never deleted, only given a new status, so the reference holds.
create table if not exists public.player_answers (
    id uuid primary key,
    user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    item_id bigint not null references public.items (id),
    topic text not null check (char_length(topic) between 1 and 200),
    difficulty text not null check (difficulty in ('easy', 'medium', 'hard')),
    -- The option picked, 0 to 3; null until the pages send it.
    choice smallint check (choice between 0 and 3),
    correct boolean not null,
    seconds real not null check (seconds >= 0),
    -- The streak including this answer, and the points it earned (src/game.ts scoreAnswer: at most
    -- 300 base x2 for a streak, plus a 75 speed bonus).
    streak integer not null check (streak >= 0),
    points integer not null check (points between 0 and 675),
    -- When it happened in the browser (the replay's order); created_at is when it reached the
    -- server, set by check_player_row() whatever the browser sends.
    at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create table if not exists public.player_reads (
    id uuid primary key,
    user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    item_id bigint not null references public.items (id),
    topic text not null check (char_length(topic) between 1 and 200),
    at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

create table if not exists public.player_runs (
    id uuid primary key,
    user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    difficulty text not null check (difficulty in ('easy', 'medium', 'hard')),
    length smallint not null check (length in (10, 30, 60)),
    correct smallint not null check (correct >= 0),
    -- The run clock at the last answer.
    seconds real not null check (seconds >= 0),
    at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    check (correct <= length)
);

create table if not exists public.player_searches (
    id uuid primary key,
    user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    at timestamptz not null default now(),
    created_at timestamptz not null default now()
);

-- The totals and lists of a profile saved before accounts (src/profile.ts version 2), which has
-- no history to replay. The replay starts from the sum of an account's baselines.
-- The browser reports these totals, so a future leaderboard must ignore baselines too.
create table if not exists public.player_baselines (
    user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    guest_id uuid not null,
    points integer not null check (points >= 0),
    answered integer not null check (answered >= 0),
    correct integer not null check (correct >= 0),
    best_streak integer not null check (best_streak >= 0),
    finished_runs integer not null check (finished_runs >= 0),
    live_runs integer not null check (live_runs >= 0),
    -- Trophy id to tier, as src/trophies.ts.
    trophies jsonb not null default '{}'
        check (jsonb_typeof(trophies) = 'object' and octet_length(trophies::text) <= 2048),
    -- Difficulty to topic names, newest first.
    played jsonb not null default '{}'
        check (jsonb_typeof(played) = 'object' and octet_length(played::text) <= 65536),
    learned jsonb not null default '[]'
        check (jsonb_typeof(learned) = 'array' and octet_length(learned::text) <= 65536),
    -- Item ids, newest first (the browser keeps 500).
    seen_items jsonb not null default '[]'
        check (jsonb_typeof(seen_items) = 'array' and octet_length(seen_items::text) <= 16384),
    at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    primary key (user_id, guest_id),
    check (correct <= answered)
);

-- One index per table serves both the caps and reading an account's rows.
create index if not exists player_answers_user_created on public.player_answers (user_id, created_at);
create index if not exists player_reads_user_created on public.player_reads (user_id, created_at);
create index if not exists player_runs_user_created on public.player_runs (user_id, created_at);
create index if not exists player_searches_user_created on public.player_searches (user_id, created_at);

-- --- Server time and row caps --------------------------------------------------------------------

-- Before each insert: created_at becomes the server's time, a browser time in the future becomes
-- now, and a row over its cap (see the header) is refused with SQLSTATE CQ001. It runs as the
-- player, so under row-level security it counts only that player's rows, which is what a cap
-- needs. A trigger function cannot be called on its own, so it needs no revoke.
create or replace function public.check_player_row()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    v_day_start timestamptz := date_trunc('day', now(), 'UTC');
    v_cap integer;
    v_count integer;
begin
    new.created_at := now();
    new.at := least(new.at, now());

    case tg_table_name
        when 'player_answers' then
            v_cap := 2000;
            select count(*) into v_count from public.player_answers
            where user_id = new.user_id and created_at >= v_day_start;
        when 'player_reads' then
            v_cap := 500;
            select count(*) into v_count from public.player_reads
            where user_id = new.user_id and created_at >= v_day_start;
        when 'player_runs' then
            v_cap := 200;
            select count(*) into v_count from public.player_runs
            where user_id = new.user_id and created_at >= v_day_start;
        when 'player_searches' then
            v_cap := 50;
            select count(*) into v_count from public.player_searches
            where user_id = new.user_id and created_at >= v_day_start;
        when 'player_baselines' then
            v_cap := 20;
            select count(*) into v_count from public.player_baselines
            where user_id = new.user_id;
    end case;

    if v_count >= v_cap then
        raise exception 'row cap reached on %', tg_table_name
            using errcode = 'CQ001',
                  detail = format('An account adds at most %s rows to %s.', v_cap, tg_table_name);
    end if;
    return new;
end;
$$;

drop trigger if exists check_player_row on public.player_answers;
create trigger check_player_row before insert on public.player_answers
    for each row execute function public.check_player_row();
drop trigger if exists check_player_row on public.player_reads;
create trigger check_player_row before insert on public.player_reads
    for each row execute function public.check_player_row();
drop trigger if exists check_player_row on public.player_runs;
create trigger check_player_row before insert on public.player_runs
    for each row execute function public.check_player_row();
drop trigger if exists check_player_row on public.player_searches;
create trigger check_player_row before insert on public.player_searches
    for each row execute function public.check_player_row();
drop trigger if exists check_player_row on public.player_baselines;
create trigger check_player_row before insert on public.player_baselines
    for each row execute function public.check_player_row();

-- --- Row-level security and grants ---------------------------------------------------------------

alter table public.player_answers enable row level security;
alter table public.player_reads enable row level security;
alter table public.player_runs enable row level security;
alter table public.player_searches enable row level security;
alter table public.player_baselines enable row level security;

-- Two policies a table: a signed-in player reads and adds only their own rows. auth.uid() sits
-- in a sub-select so Postgres works it out once a query, not once a row.
drop policy if exists "Players read their own answers" on public.player_answers;
create policy "Players read their own answers" on public.player_answers
    for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "Players add their own answers" on public.player_answers;
create policy "Players add their own answers" on public.player_answers
    for insert to authenticated with check (user_id = (select auth.uid()));

drop policy if exists "Players read their own reads" on public.player_reads;
create policy "Players read their own reads" on public.player_reads
    for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "Players add their own reads" on public.player_reads;
create policy "Players add their own reads" on public.player_reads
    for insert to authenticated with check (user_id = (select auth.uid()));

drop policy if exists "Players read their own runs" on public.player_runs;
create policy "Players read their own runs" on public.player_runs
    for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "Players add their own runs" on public.player_runs;
create policy "Players add their own runs" on public.player_runs
    for insert to authenticated with check (user_id = (select auth.uid()));

drop policy if exists "Players read their own searches" on public.player_searches;
create policy "Players read their own searches" on public.player_searches
    for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "Players add their own searches" on public.player_searches;
create policy "Players add their own searches" on public.player_searches
    for insert to authenticated with check (user_id = (select auth.uid()));

drop policy if exists "Players read their own baselines" on public.player_baselines;
create policy "Players read their own baselines" on public.player_baselines
    for select to authenticated using (user_id = (select auth.uid()));
drop policy if exists "Players add their own baselines" on public.player_baselines;
create policy "Players add their own baselines" on public.player_baselines
    for insert to authenticated with check (user_id = (select auth.uid()));

-- Supabase grants new tables to anon and authenticated by default, so every privilege is revoked
-- first and only select and insert are granted back, to signed-in players. The secret key's role
-- keeps everything, as for every other table.
revoke all on table
    public.player_answers, public.player_reads, public.player_runs, public.player_searches,
    public.player_baselines
from anon, authenticated;
grant select, insert on table
    public.player_answers, public.player_reads, public.player_runs, public.player_searches,
    public.player_baselines
to authenticated;
grant all on table
    public.player_answers, public.player_reads, public.player_runs, public.player_searches,
    public.player_baselines
to service_role;
