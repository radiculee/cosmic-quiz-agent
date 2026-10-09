# Next session

Written 2026-10-09, at the close of Session 9. It holds what is left to do and the prompt to paste
into the next Claude Code session.

## Where things stand

- Session 9 (Analytics for nerds) is closed, pushed and deployed. The code review's 7 items are
  fixed, with a read-only command, `python -m dev.check_stats`, that compares the live
  `agent_stats()` with a Python version of it (7 of 7 filter sets the same). 302 Python and 114
  TypeScript tests pass.
- The Session 8 and Session 9 gates passed (2026-10-09). Both live searches on production are
  checked read-only, and "This search" matched the stored runs each time:
  - Antimatter (a topic the bank had in part): 2 runs, $0.067, 1 item in review;
  - "Red light shift index" (new): 4 runs, $0.152, 2 items in review, then the limit message.
- One small fix after the deploy, committed and pushed (`f48400e`): a run row in "This search"
  said "1 pages"; `src/components/stats/SearchTab.tsx` now uses the file's `plural()`.
- Session 10 is planned as 10a (security audit and fixes) and 10b (history scan, public repo,
  domain, README, OG image, privacy page), with Vedant's decisions in `docs/PLAN.md`.
- The local `TYPESAFE_API_KEY` is still rejected (HTTP 401), so live searches work only on
  production until it is replaced.

## Vedant, before the next session

1. **Optional:** decide the review queue with `python -m curator review`: items 198
   (Antimatter, QUIZ MEDIUM), 202 and 203 ("Red light shift index", QUIZ MEDIUM and HARD).
2. **Optional:** replace the local `TYPESAFE_API_KEY`, so live searches work on localhost too.

## Prompt for the next session

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md and docs/NEXT_SESSION.md. Session 9 is closed,
> and its gates passed.
>
> 1. Start Session 10a (security audit and fixes) as planned in docs/PLAN.md, with the two audit
>    notes from docs/CODE_REVIEW_SESSION9.md on its list. Ask me its decisions first, each with a
>    recommendation.
> 2. Audit every area on the 10a list and record each finding in docs/SECURITY_AUDIT.md with
>    its severity, where it is, and the fix you propose. Show me that list before fixing
>    anything, and ask about any fix that needs a new tool, a paid feature or a change to a
>    locked decision.
> 3. Then fix every finding I approve, each with a test. Tests use the scripted fake model only
>    (no paid calls). Run pnpm typecheck, pnpm test, pnpm build, pytest, ruff and
>    mypy --strict, and `python -m dev.check_stats` if agent_stats() changes. Show me the
>    changes before committing.
>
> Rules from CLAUDE.md apply: ask before adding any dependency, service or cost; no emojis;
> complete files; commit only when I ask.
