# Handoff: latency

Notes for the latency session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for
this session. Update them before finishing, and commit them on `session/latency`.

Last update: 2026-10-28, session ended (universal topics and its bank fill on `main` and pushed;
parallel search and November's budget planned and decided, not built)

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
- **`main`** has everything so far and was pushed on 2026-10-28: universal topics and Surprise
  me (the explore session, now closed) and this session's docs. `session/latency` is the same
  commit as `main`; start new work on it.
- **The live bank:** migration 009 applied. After two fills, a Jev re-check and the review
  queue, 37 of 44 topics are on every level. 8 slots are missing on 7 topics: 2 open to a retry
  (the daily run takes them) and 6 out of tries, listed in `docs/PLAN.md` under "Universal
  topics", waiting for Vedant to decide what to do with them. The review queue is empty.
- **Keys and limits:** Vedant changed the TypeSafe key on 2026-10-28 (the old one returns
  401); the new one is in all three local `.env` files, Vercel and the GitHub Actions secrets.
  The Anthropic workspace hit its October limit; Vedant raised it by about $2 (an exception to
  hard rule 1). October's spend after this session's runs is close to that new limit, so keep
  paid work small until 1 November.
- **Checks** (`.github/workflows/checks.yml`), run here before the push: see the session log in
  `docs/PLAN.md`.
- **Decided, not yet built:**
  - November: option A. Launch days 14 searches a day for everyone, 5 a visitor, $3.25 a day;
    $20 for live research in November, ending on 1 December; Console at $27 for the month.
  - Parallel search: reserve every run at the start ($0.17 each, $1.02 a search), the usual
    daily cap $1.55, partial fit in plan order, questions played easiest first, a tagged agent
    log, one log line for every 429 (Vedant agreed to this in place of a count per run).

## Next

The plan's steps 1 (rebase) and 2 (the explore text) are done.

3. **November's budget**, in its own commits so it can ship even if parallel search does not:
   `agent/limits.py` (a November window with `usd_per_month` $20 from 1 to 30 November; the
   launch limits 14 searches, $3.25 a day, 5 a visitor), the 2026-10-22 review's findings 2 to
   4, tests for both ends of November and $4 again on 1 December, and the README and
   `CHANGELOG.md`. Draft the dated November exception to the $10 rule for `CLAUDE.md` (and note
   October's $2 exception there too), and the cost line and decision 9 for `docs/DESIGN.md`;
   ask Vedant before editing either (his files). It must be deployed before 3 November.
4. **Parallel search**, as listed in the plan: migration `010_parallel_searches.sql` with
   `begin_on_demand_search` (explain it to Vedant before writing it; additive, so
   `begin_on_demand_run` stays until the deploy), `agent/store.py`, `agent/limits.py` (usual
   daily cap $1.55; the `"search"` limit name goes), `agent/ondemand.py` (a thread per item;
   `RUN_START_SECONDS`, `VERIFY_SECONDS`, `run_budget`, `_later_slot`, `_NotStarted` and the
   "Time" line go), `agent/llm.py` (a response hook on `anthropic.DefaultHttpxClient`, which is
   `httpx2`, logging each 429), `src/components/AgentLog.tsx` with `itemTag` in `src/search.ts`,
   tests, and docs (`docs/DEVELOPMENT.md` has no owner: ask first).
5. **Verification:** every check, a headless drive against the stub API (ask Vedant before
   starting dev servers on 5173 and 8787), then 2 real searches locally and 1 live, about
   $0.17 each, asked for one by one.

Later, not part of this plan: keep `<sup>` as `^` in `agent/tools/fetch.py` (superscripts are
lost, so 10^9 reads as "109"; no session owns that file, so ask Vedant), and the 6 slots out of
tries.

## Blockers and things to watch

- October's Anthropic budget is nearly used: the 2 local real searches (about $0.34) fit, but
  little else does before 1 November 00:00 UTC.
- Vedant: check the account's rate-limit tier in the Anthropic Console before 1 November; raise
  the Console limit to $27 before 3 November and back to $10 on 1 December; paste migration
  010 when it is ready.

## Rules to keep in mind

- Edit only the files this session owns (`docs/SESSIONS.md`, "latency owns"); for any other,
  stop and ask Vedant. `docs/DESIGN.md` and `CLAUDE.md` are his.
- Stage by path. Never `git add -A`, `git stash`, `git reset --hard` or `git checkout -- <file>`.
- One session at a time runs the dev servers; never stop a server this session did not start.
- No emojis; commit only when Vedant asks; append each new decision to `docs/SESSIONS.md`.

## Files touched

- `docs/PLAN.md`: the parallel-search plan; the 2026-10-22 section and November's decision at
  its end; the Universal topics section (from the explore handoff) with its landing, the fills,
  the Jev re-check, the review queue and the superscript finding; the session log.
- `CHANGELOG.md`: the 2026-10-28 entry (from the explore handoff) and the bank fill.
- `docs/NEXT_SESSION.md`: the 2026-10-22 update; frozen since.
- `docs/SESSIONS.md`: this session's row, the open questions answered, Decisions appended, the
  uncommitted work marked resolved.
- `docs/handoff/latency.md`.
- Outside git: `TYPESAFE_API_KEY` in the three local `.env` files.

## Pre-launch overhaul additions (brief from main, 2026-10-30)

The 2026-10-30 grill-me (`docs/SESSIONS.md`, Decisions, and `docs/handoff/main.md`) added work
to this session and four new sessions beside it: data (accounts), ui (header, cards, progress
rows, ranks), seo (the rename to Curiosity, metadata, prerendering, redirects) and media (topic
images). Everything ships before the launch; code freeze **Monday 2 November 18:00 Dublin**.
This session stays on the critical path; November's budget and parallel search come first and
are must-ship.

On Windows, the existing worktree `C:\Users\vedan\cqa-latency` carries on: with a clean
`git status`, run `git rebase main` there after pulling `main` (its 2026-10-28 work is already
on `main`). On a machine without it, `dev/new-session.sh latency` makes a fresh one.

### Added to "Next"

1. **November's budget** (step 3 above): merged and deployed by **Saturday 31 October**.
2. **Parallel search** (step 4 above), with migration **010** (the number is reserved for you;
   data has 011 and media 012). Go/no-go Sunday 1 November as decided.
3. **Progress events** for ui's new progress rows: each item's stage as it changes (search,
   fetch, write, verify, done or failed) and an estimate in seconds from the measured median for
   its mode and level (the `run_stats` data; say which query or constant, and how it is kept
   current). The event types go in `src/types.ts`, which you own; ui reads them. Keep the
   existing log lines.
4. **`AgentLog.tsx`**: a prop or hook so ui can put it behind "Show details".
5. **Likely-topic fill** (Q20): 30 topics, about $5, on or after 1 November, from November's
   budget (say which cap it counts against). Choose them from what visitors have typed
   (`on_demand_runs`) plus the classics, and list them for Vedant before running.
6. **Deploy hook:** after the Curator publishes a new topic, call the Vercel deploy hook
   (secret `VERCEL_DEPLOY_HOOK_URL` in GitHub Actions, made by Vedant) so seo's prerendered
   pages pick it up. At most once per Curator run.
7. **Per-account limits** (Q5), once data's `agent/auth.py` and `src/session.ts` are on `main`:
   `api/research.py` and `api/quota.py` key a signed-in visitor's limits by account (same numbers),
   guests by the salted IP hash as now; `src/api.ts` sends data's `authHeader()`. Global caps
   unchanged. This is part of accounts, so it is cut with them if they are late.
8. **Fold migrations 011 and 012** into `supabase/schema.sql` as they land.
9. **Docs:** `docs/PLAN.md`, `CHANGELOG.md` and `README.md` stay yours, except the README rename,
   which seo makes. Fold in the other sessions' changelog text.

### Ownership changes

- `api/topics.py` passes to media for the image fields.
- `supabase/migrations/011_*.sql` and `012_*.sql` are written by data and media; you keep
  `schema.sql` and `010`.
