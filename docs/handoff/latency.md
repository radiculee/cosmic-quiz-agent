# Handoff: latency

Notes for the latency session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for
this session. Update them before finishing, and commit them on `session/latency`.

Last update: 2026-10-28 (the plan written; nothing built)

## Current goal

Parallel search and the cost guard, shipped before the 3 November LinkedIn launch (go/no-go on
Sunday 1 November; see Decisions in `docs/SESSIONS.md`).

## Done

- Measured why a search is slow: about 17 s an item (Session 3 eval, 111 quiz runs), run one at
  a time only so a search never reserves more than $0.17. A real item costs a median $0.027.
- Planned with Vedant in a grill-me session, for the six-item search of universal topics:
  `docs/PLAN.md`, "Faster live searches: every run at once", with the build list and the prompt
  for the build session. The decisions are appended in `docs/SESSIONS.md`.

## Next

1. Universal topics lands on `main` (now on `session/explore`, 3 commits); then rebase this
   branch onto `main`.
2. November's budget is decided (`docs/PLAN.md`, the section before this plan). Its numbers
   assume about $0.12 a search; six items are about $0.17, so they need redoing.
3. Build the plan's list, then 2 real searches locally and 1 live (about $0.50, each asked).

## Blockers

- Universal topics is not on `main` yet, and this plan builds on it.
- November's budget sets the launch week's daily cap (about $4.25 at 20 searches, $2.90 at 12).

## Files touched

- `docs/PLAN.md` (the new section and a session-log line only; the uncommitted 2026-10-22
  November budget section in the main folder is left as it was)
- `docs/SESSIONS.md` (this session's row, the open question answered, Decisions appended)
- `docs/handoff/latency.md`
