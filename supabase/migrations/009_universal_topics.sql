-- 009: every topic at every level (2026-10-28, docs/PLAN.md "Universal topics").
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes the function for a fresh project; the renames are a one-off for the live bank.
--
-- Learn and Quiz now list a topic only when it has a published item in both modes at all three
-- levels (api/topics.py). Until now the Curator never retried a job it had run once, and a live
-- search made its explanation at one level only, so 27 of the 44 topics had gaps.
--
-- 1. missing_slots(): every slot (mode and difficulty) that a listed topic still lacks, with how
--    many runs have tried it and whether an item for it waits in review. `python -m curator
--    complete` and `daily` fill these; the try limit lives in curator/pipeline.py.
-- 2. curator_runs.trigger accepts 'complete', the command that fills them.
-- 3. Visitor-typed topic names tidied (decided by Vedant on 2026-10-28). "Bang" duplicates the
--    built-in "The Big Bang", so its runs and items move there and the empty topic is deleted.
--    on_demand_runs keeps the text each visitor typed, as history.

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

-- Server only, like attempted_jobs().
revoke execute on function public.missing_slots() from public, anon, authenticated;
grant execute on function public.missing_slots() to service_role;

alter table public.curator_runs drop constraint if exists curator_runs_trigger_check;
alter table public.curator_runs
    add constraint curator_runs_trigger_check check (trigger in ('build', 'daily', 'complete'));

-- --- One-off: tidy visitor-typed names ------------------------------------------------------

do $$
declare
    v_from bigint;
    v_into bigint;
begin
    select id into v_from from public.topics where name = 'Bang';
    select id into v_into from public.topics where name = 'The Big Bang';
    if v_from is not null and v_into is not null then
        update public.items set topic_id = v_into where topic_id = v_from;
        update public.runs set topic_id = v_into where topic_id = v_from;
        delete from public.topics where id = v_from;
    end if;
end;
$$;

-- Each rename runs only while the old name exists and the new one is free.
update public.topics t set name = r.new_name
from (
    values
        ('Meteroid', 'Meteoroids'),
        ('Red light shift index', 'Redshift'),
        ('Space Travel', 'Human spaceflight'),
        ('Cosmic clouds', 'Interstellar clouds'),
        ('Dark side of the moon', 'The far side of the Moon'),
        ('Wormhole', 'Wormholes'),
        ('Drake Equation', 'The Drake equation')
) as r (old_name, new_name)
where t.name = r.old_name
  and not exists (select 1 from public.topics o where lower(o.name) = lower(r.new_name));
