# Handoff: latency

Notes for the latency session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for
this session. Update them before finishing, and commit them on `session/latency`.

Last update: 2026-10-30. November's budget is committed and ready for review. Parallel search is
in progress.

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
  me (the explore session, now closed) and this session's docs. `session/latency` started the
  2026-10-30 work at `main` (`200185a`).
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
    $20 for live research in November, ending on 1 December; Console at $32 for the month (changed 2026-10-30).
  - Parallel search: reserve every run at the start ($0.17 each, $1.02 a search), the usual
    daily cap $1.55, partial fit in plan order, questions played easiest first, a tagged agent
    log, one log line for every 429 (Vedant agreed to this in place of a count per run).

## Done

- `fef385f`: handoff state recorded.
- `afcfe33`: November's $20 month cap; launch week 5 a visitor, 14 searches, $3.25 a day; review findings 2, 3, 4.
- `37a6696`: Mission Control reads the live month cap through `limits_at`; November shows $20.
- `48c49c5`: README, CHANGELOG, PLAN.md and SESSIONS.md (row, decision) record November's budget.
- November's budget is ready for main's review: `git diff main...session/latency`.
- Vedant decided (2026-10-30, via main): Console $32 in November; the fill counts against the Console only.
- Accepted: the worst case ($22.75 in the launch week) pauses live search late in the week.
- Checks pass: 366 Python tests, 149 TypeScript tests, ruff, ruff format, mypy, typecheck, build.

## Next

1. Explain migration 010 to Vedant (now with the medians function), then write it.
2. Parallel search: `agent/store.py`, `agent/limits.py` ($1.55 usual daily cap), `agent/ondemand.py` (a thread per item).
3. 429 logging: a response hook on the Anthropic client, built in `api/research.py`.
4. Progress events: `estimate_seconds` per planned item, a `progress` event, in `src/types.ts` and `src/search.ts`.
5. `src/components/AgentLog.tsx`: tagged lines and an `open` prop.
6. Tests, every check, the headless drive, then 3 real searches (asked one by one).
7. `docs/DEVELOPMENT.md` for parallel search (approved).
8. Deploy hook: once per Curator run that published anything, with its `curator.yml` env line (approved).
9. The 30-topic fill: list the topics for Vedant first.
10. Per-account limits, folding 011 and 012, other sessions' changelog text.

## Blockers

- Main's review of November's budget (not blocking parallel search).
- Migration 010: Vedant hears the explanation before it is written.
- Per-account limits: wait for data's `agent/auth.py` and `src/session.ts` on `main`.
- Migrations 011 and 012: wait for data and media.
- `CLAUDE.md` and `docs/DESIGN.md` drafts: wait for Vedant's approval.
- Vedant: Console to $32 before 3 November; back to $10 on 1 December.
- Vedant: check the Anthropic rate-limit tier before the go/no-go.
- Mission Control still shows the $10 Anthropic limit in November (`agent/config.py`, not owned). Not fixed; asked.
- October's Anthropic budget is nearly used. Paid work waits for 1 November 00:00 UTC, except small runs.

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
- 2026-10-30, committed: `agent/limits.py`, `agent/ondemand.py`, `tests/test_quota.py`,
  `tests/test_ondemand.py` (`afcfe33`); `agent/stats.py`, `tests/test_stats.py` (`37a6696`);
  `README.md`, `CHANGELOG.md`, `docs/PLAN.md`, `docs/SESSIONS.md` (`48c49c5`);
  `docs/handoff/latency.md`.

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

## Drafts for Vedant's files (not applied; approve or change the text)

`CLAUDE.md`, hard rule 1, after "(Changed 2026-10-01; ... See `docs/PLAN.md`.)":

> Dated exceptions, decided by Vedant: October 2026's limit was raised by about $2 on 2026-10-28,
> when the bank fill met it; November 2026's is $32 ($20 for the launch month's live research,
> about $5 for the daily Curator, $5 for the 30-topic Curator fill, $2 spare), back to $10 on
> 1 December. Both are in
> `docs/PLAN.md`, "The launch week's code review and November's budget".

`docs/DESIGN.md`, decision 8, the cost line, after "(capped at $10 a month)":

> (dated exceptions: October 2026 about $12, November 2026 $32 for the launch; decided by
> Vedant on 2026-10-28)

`docs/DESIGN.md`, decision 9, the launch sentence, replacing "5 searches a visitor and 20
searches and $2.50 a day for everyone; the $4 monthly cap is unchanged":

> 5 searches a visitor and 14 searches and $3.25 a day for everyone, and live research has $20
> for the calendar month of November (changed 2026-10-28 by Vedant; it was 20 searches and $2.50
> a day under the usual $4 month)
