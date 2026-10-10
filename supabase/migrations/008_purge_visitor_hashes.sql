-- 008: visitor hashes cleared on a timer (2026-10-09, docs/SECURITY_AUDIT.md S13).
--
-- Paste into the Supabase SQL editor and run it once; it is safe to run again. supabase/schema.sql
-- already includes this for a fresh project.
--
-- Until now, live runs' visitor hashes were cleared only when a live run started, and old request
-- windows were deleted on 1 request in 100, so on a quiet week hashes stayed for a week. Report
-- hashes were kept with no end date. purge_visitor_hashes() clears them on a timer instead, and
-- `python -m curator upkeep` and `daily` run it every day:
--
--   * on_demand_runs.user_hash: cleared after 1 day. The limits only count today's runs (UTC),
--     and a row more than a day old is never today's, so the limits are unchanged. With the daily
--     run, no hash is kept more than about two days.
--   * rate_limits: windows older than 1 day are deleted (only the current hour is used).
--   * reports.user_hash: cleared after 30 days (decided by Vedant on 2026-10-09). The report and
--     the item's count stay. While the hash is kept, the unique rule stops a visitor reporting an
--     item twice; the column becomes nullable so the hash can be cleared.
--
-- The lazy clean-ups in begin_on_demand_run and hit_request_limit stay as they are.

alter table public.reports alter column user_hash drop not null;

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

-- Server only. Supabase grants new functions to anon and authenticated by default, so execute is
-- revoked from everyone first and granted back to the secret key's role.
revoke execute on function public.purge_visitor_hashes() from public, anon, authenticated;
grant execute on function public.purge_visitor_hashes() to service_role;
