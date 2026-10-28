# Next session

Written 2026-10-19, when version 1 closed; updated 2026-10-22 after the launch week's code
review. It holds where things stand, what is left for Vedant, the November budget to decide
first, and the prompts for the next sessions.

## Where things stand

- **Version 1 is done.** Session 10b's gate passed on 2026-10-19 (`docs/PLAN.md`, 10b).
- **Live** at https://cosmic.vedantgaikwad.ie; the old `cosmic-quiz-agent.vercel.app` address
  redirects every path there (308).
- **Public:** https://github.com/radiculee/cosmic-quiz-agent, under MIT (the scene art, the
  link preview and the screenshots excepted; see `NOTICE`). Secret scanning with push
  protection and Dependabot alerts are on; Dependabot's automatic fix pull requests are off.
  The description is the tagline and the homepage the site. The header's GitHub icon links to
  the repo.
- **Checks** run on every push and pull request (`.github/workflows/checks.yml`); the badge
  reads "passing" signed out. 342 Python and 148 TypeScript tests.
- **The Curator** runs `upkeep` (free) every day until 31 October; from 1 November it runs
  `daily` (about $0.17 a day, capped at $0.40) without any change. Every run since the README
  session has passed, including the first after GitHub began moving `ubuntu-latest` to
  Ubuntu 26 (2026-10-19).
- **The bank:** 40 topics and 190 published items; the review queue is empty (reviewed on
  2026-10-21: 5 published, 4 discarded).
- **The LinkedIn launch week:** Vedant posts on Tuesday 3 November at 9:30. For the UTC days 3
  to 9 November, 5 live searches a visitor and 20 and $2.50 a day for everyone; the $4 monthly
  cap is unchanged. It ends by itself (`agent/limits.py`). The code review on 2026-10-22 found
  that the $4 cap runs out on the launch's second day, so November's budget is open (below).

## Vedant's own items

- The review queue: empty since 2026-10-21; `python -m curator review` when it fills again.
- Done on 2026-10-19: the project is on his portfolio, and the local Python is 3.12.10 with a
  rebuilt `.venv` (S16 fixed; `docs/SECURITY_AUDIT.md`).
- Dependabot alerts now arrive by email and in the repo's Security tab; each needs a look.
- Spend: the Console's October figure under the $10 limit, and the TypeSafe balance.

## First: November's budget (decide before 3 November)

Vedant wants a higher cap for November only, so everyone who comes from the LinkedIn post can
try a live search. As built, the $4 monthly cap is spent by about 4 November and live research
pauses until 1 December. Raising the app's cap is not enough on its own: the Console's $10
limit covers the Curator (about $5 in November) and live research together, so it has to go up
for November too, an exception to hard rule 1. Full numbers, the code review's other findings
and the build list are in `docs/PLAN.md`, "The launch week's code review and November's budget".

- **(Recommended)** $20 for live research in November with the Console at $27; the launch
  numbers stay, and nothing pauses after the launch week.
- **Cheaper:** $12 in November with the Console at $19; the launch days become 12 searches and
  $1.50 a day.

Either way the cap runs for the whole calendar month (not only 3 to 9 November), ends by itself
on 1 December, and Vedant raises the Console limit himself before 3 November and lowers it
again on 1 December.

## Then: plan version 2

Version 2 is the newsletter produced by the same agent (email through Resend, then WhatsApp),
decided together with accounts, so players keep their progress across devices (`docs/PLAN.md`,
"Later - v2: Newsletter"). Nothing is planned in detail yet; Vedant usually wants a plan-only
session first.

## Prompt for the next session

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md and docs/NEXT_SESSION.md.
>
> This session raises the live-search budget for November 2026 only, for the LinkedIn launch.
> Start by asking me to choose between the two options in docs/NEXT_SESSION.md ("First:
> November's budget"), with your recommendation. Then build the list in docs/PLAN.md under
> "The launch week's code review and November's budget": the November cap in agent/limits.py
> with its tests, findings 2 and 3, and the docs, including a dated November exception to the
> $10 rule in CLAUDE.md. Run every check. Remind me to raise the Console limit before
> 3 November.
>
> Rules from CLAUDE.md apply: no emojis; complete files; commit only when I ask.

## Prompt for the session after

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md and docs/NEXT_SESSION.md.
>
> Version 1 is done and public. This is a plan-only session for version 2 (the newsletter and
> accounts). Ask me the open questions one at a time, each with a recommendation, and state the
> free tier or price of every service before suggesting it. Write the plan into docs/PLAN.md;
> build nothing yet.
>
> Rules from CLAUDE.md apply: no emojis; complete files; commit only when I ask.
