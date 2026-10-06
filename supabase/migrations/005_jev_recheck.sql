-- 005: re-check an item whose Jev check failed (2026-10-06).
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes this for a fresh project.
--
-- When Jev cannot be reached (an outage, a wrong key), the gate sends the item to review with a
-- Jev verdict of 'error'. `python -m curator rejev` runs Jev again on the page text stored with
-- the run, applies the same gate rule, and stores the result here in one transaction: Jev's claim
-- checks replace any earlier ones, the run's Jev cost grows by the re-check's, and the item gets
-- its new Jev verdict and status. The gate moved the item, not a person, so reviewed_at (which
-- records human decisions, migration 002) stays empty.

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

revoke execute on function public.apply_jev_recheck(bigint, text, jsonb)
    from public, anon, authenticated;
grant execute on function public.apply_jev_recheck(bigint, text, jsonb) to service_role;
