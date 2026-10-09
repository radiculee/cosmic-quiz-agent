# Next session

Written 2026-10-09 at the end of Session 9. It holds what is left to do and the prompt to paste
into the next Claude Code session.

## Where things stand

- Session 9 (Analytics for nerds) is committed: `90ff820` (migration 007), `6376826` (the stats
  event, `/api/stats`, the eval export) and `619c5e9` (the panel), plus a docs commit. It is
  pushed to `main`, so Vercel deploys it to https://cosmic-quiz-agent.vercel.app.
- Migration 007 is applied. The live `agent_stats()` matched a Python re-implementation on 7
  filter sets, and `/api/stats` answers 200 locally.
- A code review left 7 items, none critical: `docs/CODE_REVIEW_SESSION9.md`.
- The local `TYPESAFE_API_KEY` is still rejected (HTTP 401), so live searches work only on
  production until it is replaced.

## Vedant, before the next session

1. **Check the panel on production** once the deploy finishes: open `/explore`, then Analytics
   for nerds. The agent tab should open on four figures (published, cost per published item,
   median run, October spend) with seven closed rows; try the Filter button, open and close a
   row, Esc, Back, and `/explore/stats` as a direct link.
2. **Run the two live searches** for the Session 8 gate on
   https://cosmic-quiz-agent.vercel.app/explore, on a day your network has not used live research
   yet (the count resets at 01:00 Irish time). About $0.21 together:
   - a new topic at MEDIUM (about $0.12): the explanation, then three questions labelled by
     difficulty, the next button waiting for each; the counter goes from 2 to 1;
   - "Black holes" at MEDIUM (about $0.09): 3 items made, the EASY question marked "From the
     bank, free"; then the limit message.
   After each one, open Analytics for nerds: the "This search" tab should show its cost, items
   made, time and pages read, and the runs under "Run by run". This is the first real check of
   the stats event, since only production can run live searches.
3. **Optional:** replace the local `TYPESAFE_API_KEY`, so live searches work on localhost too.

## Prompt for the next session

Paste this, and edit the line in brackets to say whether the live searches are done:

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md, docs/NEXT_SESSION.md and
> docs/CODE_REVIEW_SESSION9.md. Session 9 (Analytics for nerds) is committed and deployed, and
> migration 007 is applied and checked.
>
> [I ran the two live searches on production on <date> / I have not run the live searches yet.]
>
> 1. Fix items 1, 2, 3, 5, 6 and 7 in docs/CODE_REVIEW_SESSION9.md. Before item 4 (moving the
>    stats comparison and the browser drives into dev/), ask me, with a recommendation. Tests
>    use the scripted fake model only (no paid calls).
> 2. Run pnpm typecheck, pnpm test, pnpm build, pytest, ruff and mypy --strict, and drive the
>    panel against the local servers, including Back, Forward, Close, Back. Show me the changes
>    before committing.
> 3. If the live searches are done: check on_demand_runs read-only (each search's later runs
>    carry the id of the run that opened it, and every run's spent_usd is set), compare what the
>    "This search" tab showed with those runs, then record the Session 8 and Session 9 gates as
>    passed in docs/PLAN.md.
> 4. Then plan Session 10 (security audit, public repo, domain, launch), with the two audit notes
>    from docs/CODE_REVIEW_SESSION9.md on its list. Plan only; ask me the Session 10 decisions.
>
> Rules from CLAUDE.md apply: ask before adding any dependency, service or cost; no emojis;
> complete files; commit only when I ask.
