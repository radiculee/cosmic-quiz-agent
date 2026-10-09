# Next session

Written 2026-10-09, after the Session 9 code review fixes and the Session 10 plan. It holds what
is left to do and the prompt to paste into the next Claude Code session.

## Where things stand

- Session 9 (Analytics for nerds) is committed and deployed (`90ff820`, `6376826`, `619c5e9`),
  and migration 007 is applied.
- All 7 code review items are fixed (`docs/CODE_REVIEW_SESSION9.md`, "Fixed"), with a new
  read-only command, `python -m dev.check_stats`, that compares the live `agent_stats()` with a
  Python version of it (7 of 7 filter sets the same on 2026-10-09). 302 Python and 114 TypeScript
  tests pass, and a drive of 24 checks passed against the local servers. These changes are not
  committed until Vedant asks.
- The two live searches are not run yet, so the Session 8 and Session 9 gates are still open.
- Session 10 is planned as 10a (security audit and fixes) and 10b (history scan, public repo,
  domain, README, OG image, privacy page), with Vedant's decisions recorded in `docs/PLAN.md`.
- The local `TYPESAFE_API_KEY` is still rejected (HTTP 401), so live searches work only on
  production until it is replaced.

## Vedant, before the next session

1. **Commit and deploy the fixes** (say so to Claude Code), then check on production: open
   `/explore`, then Analytics for nerds; press Back, Forward, Close, then Back once more, which
   should leave the web page. Esc should close the panel and keep you on `/explore`.
2. **Run the two live searches** on https://cosmic-quiz-agent.vercel.app/explore, on a day your
   network has not used live research yet (the count resets at 01:00 Irish time). About $0.21
   together:
   - a new topic at MEDIUM (about $0.12): the explanation, then three questions labelled by
     difficulty, the next button waiting for each; the counter goes from 2 to 1;
   - "Black holes" at MEDIUM (about $0.09): 3 items made, the EASY question marked "From the
     bank, free"; then the limit message.
   After each one, open Analytics for nerds: the "This search" tab should show its cost, items
   made, time and pages read, and the runs under "Run by run". Note what it shows (a screenshot
   is easiest), so the next session can compare it with the stored runs.
3. **Optional:** replace the local `TYPESAFE_API_KEY`, so live searches work on localhost too.

## Prompt for the next session

Paste this, and edit the line in brackets to say whether the live searches are done:

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md, docs/NEXT_SESSION.md and
> docs/CODE_REVIEW_SESSION9.md. The Session 9 review fixes are committed and deployed.
>
> [I ran the two live searches on production on <date>, and the This search tab showed: <what it
> showed> / I have not run the live searches yet.] If this line is still in brackets, ask me.
>
> 1. If the live searches are done: check on_demand_runs read-only (each search's later runs
>    carry the id of the run that opened it, and every run's spent_usd is set), compare what the
>    "This search" tab showed with those runs, then record the Session 8 and Session 9 gates as
>    passed in docs/PLAN.md.
> 2. Start Session 10a (security audit and fixes) as planned in docs/PLAN.md. Ask me its
>    decisions first, each with a recommendation. Record every finding in docs/SECURITY_AUDIT.md
>    with its fix and test, and fix every finding.
> 3. Tests use the scripted fake model only (no paid calls). Run pnpm typecheck, pnpm test,
>    pnpm build, pytest, ruff and mypy --strict, and `python -m dev.check_stats` if
>    agent_stats() changes. Show me the changes before committing.
>
> Rules from CLAUDE.md apply: ask before adding any dependency, service or cost; no emojis;
> complete files; commit only when I ask.
