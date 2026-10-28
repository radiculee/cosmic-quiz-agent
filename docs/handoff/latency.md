# Handoff: latency

Notes for the latency session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for
this session. Update them before finishing, and commit them on `session/latency`.

Last update: 2026-10-28 (the plan written and the worktree set up; nothing built)

## Current goal

Make a live search on the Explore page run all its items at once instead of one at a time, so
it ends in about 25 to 35 s instead of about 100 s, shipped before the LinkedIn launch on
Tuesday 3 November. Go/no-go on Sunday 1 November: if it is not deployed and verified on the
live site by then, the launch runs on the current version.

The full plan is in `docs/PLAN.md`, "Faster live searches: every run at once" (2026-10-28),
with its measurements, every decision, the build list and the prompt for the build session.
The decisions are also appended in `docs/SESSIONS.md` (Decisions, the 2026-10-28 latency
entries). Read both before building.

## Where things stand

- **This folder:** `../cqa-latency` (`C:\Users\vedan\cqa-latency`), a git worktree on
  `session/latency`. Its own `.venv` (Python 3.12.10, `requirements-dev.txt` installed), its own
  `node_modules` (`pnpm install`), and a copy of `.env` (ignored by git; load it with
  python-dotenv, never `source` it).
- **The main folder** (`cosmic-quiz-agent`) is back on `main` at `21a74b5` (the parallel-session
  setup), one commit ahead of `origin/main` and not pushed. It has no uncommitted work.
- **`session/explore`** (in `../cqa-explore`) holds universal topics and Surprise me (`f1934b0`,
  `1036a3f`, `27fa151`), not on `main` yet.
- **`session/latency`** is `21a74b5` plus docs only:
  - `6dfd883` the plan in `docs/PLAN.md`, the decisions in `docs/SESSIONS.md`, these notes;
  - `289a0cd` the 2026-10-22 code review and November's budget (`docs/PLAN.md` and
    `docs/NEXT_SESSION.md`, which is frozen from here on);
  - `5b8d866` this session's row (`../cqa-latency`) and "Uncommitted work" marked resolved;
  - the commit with these notes.
- **Checks, run here on 2026-10-28** (the commands in `.github/workflows/checks.yml`): pytest
  347 passed, `ruff check` clean, `ruff format --check` clean (96 files), `mypy --strict` clean
  (80 files), `pnpm typecheck` clean, `pnpm test` 148 passed (13 files), `pnpm build` built.
  Nothing spent.

## The plan in brief

- **Why it is slow:** an item takes about 17 s (Session 3 eval, 111 quiz runs: agent median
  13.3 s, p90 23.0 s; Haiku verifier 3.3 s; Jev 0.3 s beside it). About 90% of that is model
  calls. `_run_search` in `agent/ondemand.py` runs the items one at a time, only so a search
  never reserves more than one run's $0.17 and fits the $0.50 day. A real item costs a median
  $0.027 and at most $0.049.
- **Runs per search:** six (universal topics: a question then an explanation at each level,
  easiest first), building on `session/explore`'s work once it is on `main`.
- **Cost guard:** every run reserved together at the start, each at its evaluated $0.17, so
  $1.02 a search. Daily cap: at least (searches_per_day - 1) x $0.17 + $1.02, so $1.55 for the
  usual 4 searches, and for the launch week $4.25 at 20 searches or $2.90 at 12, whichever
  November's budget settles. Monthly caps unchanged. If the caps cannot fit every run, one
  database call reserves what fits in plan order, and the rest are "not started".
- **Page:** questions played easiest first even when a harder one finishes first; the agent
  log becomes one stream with an item tag on each line (EASY Q, HARD EXPL) instead of headings.
- **Rate limits:** no new limit; each live run logs how many 429s it met.
- **Database:** an additive migration (the next number after `009_universal_topics.sql`) adds
  `begin_on_demand_search`; `begin_on_demand_run` stays until the deploy, so rollback is a
  Vercel revert, and a later migration drops it. Row shape unchanged (the first run's
  `search_id` is null). Vedant pastes the migration into the Supabase SQL editor.
- **Removed:** `RUN_START_SECONDS`, `run_budget`, `_later_slot` and the "Time" log line, which
  can no longer trigger. `SEARCH_SECONDS` stays.
- **Verification:** the free tests and a headless drive against the stub API, then 2 real
  searches locally and 1 live, about $0.50 in all, each asked for first.
- **Deferred:** a shared research pass, after the launch (it needs its own eval).

## Next

1. Wait for universal topics to land on `main` (Vedant decides). Do not rebase before then.
   Then: `git fetch`, `git rebase main` (local `main` is ahead of `origin/main`), and run every
   check again.
2. November's budget is decided first (`docs/PLAN.md`, "The launch week's code review and
   November's budget"). Its options assume about $0.12 a search; with six items a search is
   about $0.17, so the numbers need redoing then. The launch week's daily cap here follows it.
3. Build the list in the plan, explaining the migration to Vedant before writing it. Then every
   check, the drive, and the real searches (ask before each).
4. Docs as the plan lists them, the before and after search times (from `on_demand_runs`), and
   these notes.

## Blockers

- Universal topics is not on `main`, and this work builds on it.
- November's budget sets the launch week's daily cap.
- Vedant: check the account's rate-limit tier in the Anthropic Console before 1 November.

## Rules to keep in mind

- Edit only the files this session owns (`docs/SESSIONS.md`, "latency owns"); for any other,
  stop and ask Vedant. `docs/DESIGN.md` and `CLAUDE.md` belong to Vedant: decision 9 in
  DESIGN.md changes with this work, so ask before editing it.
- Stage by path. Never `git add -A`, `git stash`, `git reset --hard` or `git checkout -- <file>`.
- One session at a time runs the dev servers (every worktree's site sends `/api` to port 8787);
  never stop a server this session did not start.
- No emojis; commit only when Vedant asks; append each new decision to `docs/SESSIONS.md`.

## Files touched

- `docs/PLAN.md` (the plan's section and a session-log line in `6dfd883`; the 2026-10-22
  section in `289a0cd`)
- `docs/NEXT_SESSION.md` (the 2026-10-22 update in `289a0cd`; frozen since)
- `docs/SESSIONS.md` (this session's row, the open question answered, Decisions appended, the
  uncommitted work marked resolved)
- `docs/handoff/latency.md`
