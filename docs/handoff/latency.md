# Handoff: latency

Notes for the latency session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for
this session. Update them before finishing, and commit them on `session/latency`.

Last update: 2026-10-28 (universal topics landed and migration 009 applied; steps 1 and 2 of
the plan done; no code changed yet)

## Current goal

Make a live search on the Explore page run all six items at once instead of one at a time, so
it ends in about 25 to 35 s instead of about 100 s, and build November's budget, both before
the LinkedIn launch on Tuesday 3 November. Go/no-go on Sunday 1 November: if parallel search is
not deployed and verified on the live site by then, the launch runs on the current version.

Read first: `docs/PLAN.md`, "Faster live searches: every run at once" (the plan, its
measurements and decisions) and "The launch week's code review and November's budget" (the
build list, and the decision recorded at its end), and the 2026-10-28 latency entries under
Decisions in `docs/SESSIONS.md`.

## Where things stand

- **This folder:** `../cqa-latency` (`C:\Users\vedan\cqa-latency`), a git worktree on
  `session/latency`, with its own `.venv` (Python 3.12.10), `node_modules` and a copy of `.env`
  (load it with python-dotenv and an explicit path, `load_dotenv(".env")`; never `source` it).
- **`main` (local)** is at `19e2640`: universal topics and Surprise me, landed by fast-forward
  from `session/explore` on 2026-10-28. Not pushed: `origin/main` is still `81c05d1`, so the live
  site does not have it yet.
- **Migration 009 is applied** on the live bank (Vedant, 2026-10-28). Read-only check:
  `missing_slots()` gives 67 slots in 27 topics (66 open to a retry, 1 in review); "Bang" and
  "Meteroid" are gone.
- **`session/latency`** is `main` plus docs only: the plan (`665c11c`), the 2026-10-22 review and
  November's budget (`e42e710`), the worktree move (`fee2180`), the first handoff (`a41f51b`),
  November's decision (`9981aa2`), the explore text folded into `docs/PLAN.md` and `CHANGELOG.md`
  (`30fafd2`), and the commit with these notes. It fast-forwards `main`.
- **Checks after the rebase** (`.github/workflows/checks.yml`): pytest 361 passed, ruff check
  and format clean (98 files), mypy --strict clean (82 files), pnpm typecheck clean, pnpm test
  149 passed, pnpm build built.
- **Decided, not yet built:**
  - November: option A. Launch days 14 searches a day for everyone, 5 a visitor, $3.25 a day;
    $20 for live research in November, ending on 1 December; Console at $27 for the month.
  - Parallel search: reserve every run at the start ($0.17 each, $1.02 a search), the usual
    daily cap $1.55, partial fit in plan order, a tagged agent log, one log line for every 429
    (Vedant agreed to this in place of a count per run).

## Next

The plan's steps, with 1 (rebase) and 2 (the explore text) done:

3. **November's budget**, in its own commits so it can ship even if parallel search does not:
   `agent/limits.py` (a November window with `usd_per_month` $20 from 1 to 30 November; the
   launch limits 14 searches, $3.25 a day, 5 a visitor), the 2026-10-22 review's findings 2 to
   4, tests for both ends of November and $4 again on 1 December, and the README and
   `CHANGELOG.md`. Draft the dated November exception to the $10 rule for `CLAUDE.md`, and the
   cost line and decision 9 for `docs/DESIGN.md`, and ask Vedant before editing either (his
   files).
4. **Parallel search**, as listed in the plan: migration `010_parallel_searches.sql` with
   `begin_on_demand_search` (explain it to Vedant before writing it; additive, so
   `begin_on_demand_run` stays until the deploy), `agent/store.py`, `agent/limits.py` (usual
   daily cap $1.55; the `"search"` limit name goes), `agent/ondemand.py` (a thread per item;
   `RUN_START_SECONDS`, `VERIFY_SECONDS`, `run_budget`, `_later_slot`, `_NotStarted` and the
   "Time" line go), `agent/llm.py` (a response hook on `anthropic.DefaultHttpxClient`, which is
   `httpx2`, logging each 429), `src/components/AgentLog.tsx` with `itemTag` in `src/search.ts`,
   tests, and docs (`docs/DEVELOPMENT.md` has no owner: ask first).
5. **Verification:** every check, a headless drive against the stub API (ask Vedant before
   starting dev servers on 5173 and 8787; the explore session may need them), then 2 real
   searches locally and 1 live, about $0.17 each, asked for one by one.

## Blockers and things to watch

- **Before `main` is pushed** (Vedant's call; pushing deploys and the scheduled Curator runs
  from `main`): `python -m curator complete` (about $1.85, capped at $3; the explore session's
  step) so Learn and Quiz do not hide 27 topics, and the explore session's unfinished browser
  check (`docs/handoff/explore.md`, Next 2).
- **The explore browser check** sets `ondemand.RUN_START_SECONDS`, which step 4 removes. It
  should run before step 4 lands on `main`, or be planned without it.
- Vedant: check the account's rate-limit tier in the Anthropic Console before 1 November; raise
  the Console limit to $27 before 3 November; paste migration 010 when it is ready.

## Rules to keep in mind

- Edit only the files this session owns (`docs/SESSIONS.md`, "latency owns"); for any other,
  stop and ask Vedant. `docs/DESIGN.md` and `CLAUDE.md` are his.
- Stage by path. Never `git add -A`, `git stash`, `git reset --hard` or `git checkout -- <file>`.
- One session at a time runs the dev servers; never stop a server this session did not start.
- No emojis; commit only when Vedant asks; append each new decision to `docs/SESSIONS.md`.

## Files touched

- `docs/PLAN.md`: the parallel-search plan; the 2026-10-22 section and November's decision at
  its end; the Universal topics section (from the explore handoff) with its landing note; the
  session log.
- `CHANGELOG.md`: the 2026-10-28 entry (from the explore handoff).
- `docs/NEXT_SESSION.md`: the 2026-10-22 update; frozen since.
- `docs/SESSIONS.md`: this session's row, the open questions answered, Decisions appended, the
  uncommitted work marked resolved.
- `docs/handoff/latency.md`.
