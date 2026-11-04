# Handoff: docs

Notes for the docs session (`docs/SESSIONS.md`). Branch `session/docs`, from `57771af`.

Last update: 2026-11-04

## Done

- `c051f5c` CHANGELOG.md and docs/DEVELOPMENT.md.
  - CHANGELOG: new entries for 4 November (56 picture rows, 28 locked, `TOPIC_IMAGES`) and 3 November
    (live on `curiosity.vedantgaikwad.ie`, redirects, prerendered pages, README rewrite, square
    320 x 320 cards, Learn card fixes, and the easy-first searches measured, n=1 each). The 2
    November "has not been measured yet" is now "measured on 3 November".
  - DEVELOPMENT: name and address on line 3; the redirects (seven subdomains plus the vercel.app
    address); the `TOPIC_IMAGES` condition on the image fill; the optional sign-in variables; the
    `requirements-media.txt` need and the 320 x 320 card in the images command; a `scripts/` row.
- `ff9a000` docs/DESIGN.md, for Vedant's approval (separate commit). Exact text below.

## In progress

Nothing.

## Left

- DESIGN.md line 1 still says "Cosmic Quiz Agent - design plan" (not in main's list; left).
- The November budget text ($20 live research, $32 Console limit, launch week 14 searches and $3.25
  a day) is not in DESIGN.md decision 9 or CLAUDE.md. It waits for Vedant, as briefed. DESIGN.md
  line 52 still says the launch week allows "20 searches and $2.50 a day" and line 58 still says
  "$10 limit" and "$4 a month". DEVELOPMENT.md line 11 still says the Anthropic limit is "$10 a
  month". All three are true again only after November.

## Blocked on

Vedant's approval of the DESIGN.md text.

## Needs from Vedant

Approve or change the exact DESIGN.md text below. Decide on the budget text above.

## DESIGN.md changes (commit `ff9a000`), old then new

Line 52 (decision 9, per-user limits). Old: "A search is up to 4 agent runs, one at a time: a
question at each level, the chosen level first, then the explanation at the chosen level (in that
order since 2026-10-10, so when a cap cuts a search short it is the explanation that is left out),
only for items the bank does not already have. Bank questions do not count. (Changed 2026-10-08 by
Vedant; it was 3 custom-topic runs of one item each,"

New: "A search is up to 6 agent runs, a question and an explanation at each level, only for items
the bank does not already have. The EASY question runs first and alone, and the other runs start
together when it ends; with the EASY question already in the bank, every run starts together. If
the EASY question fails with nothing spent, the others never start and the search does not count.
Bank questions do not count. (Changed 2026-10-28, 2026-10-30 and 2026-11-02 by Vedant,
`docs/PLAN.md`: it was up to 4 runs, one at a time, a question at each level and then the
explanation at the chosen level. Changed 2026-10-08 by Vedant; before that it was 3 custom-topic
runs of one item each,"

Line 58 (decision 9, global cap), first change. Old: "a search runs one at a time, so it never
reserves more than that."
New: "a search reserves all its runs when it starts, as many as the caps fit (since 2026-10-30; it
was one run at a time)."

Line 58, second change. Old: "Since a run starts only if today's spend plus its reservation fits
$0.50, 4 searches is a ceiling: the day's 4th search usually makes 1 or 2 items, or cannot start.
Kept as is (decided 2026-10-08)."
New: "Since a run starts only if today's spend plus its reservation fits the daily cap, 4 searches is
a ceiling. Changed 2026-10-30 (`docs/PLAN.md`, parallel search): the usual daily cap is $1.55, not
$0.50, so the day's last search can still make every item (3 searches at their real cost, $0.17
each, plus one whole reservation of 6 runs); real spend per search is unchanged, and the cap only
paces it."
(The sentence "4 searches and $0.50 a day" earlier on that line is unchanged, now followed by this
note.)

Line 121 (repo layout). Old: "ondemand.py  a guarded live search (up to 4 runs, one at a time),
streamed as events"
New: "ondemand.py  a guarded live search (up to 6 runs: the EASY question first, then the rest
together), streamed as events"

Line 156 (repo layout). Old: "public/og-v1.jpg       the link preview: the observatory scene with
the title and tagline"
New: "public/og-v2.jpg       the link preview: the Curiosity title and tagline (og-v1.jpg is the
earlier one)"

No locked decision is reopened. The changes record decisions already made (PLAN.md, SESSIONS.md).
Decisions 8 and 9 are otherwise untouched.

## Files changed

CHANGELOG.md, docs/DEVELOPMENT.md (`c051f5c`); docs/DESIGN.md (`ff9a000`); docs/handoff/docs.md.

## Checks run

- `pytest -q` with PYTHONPATH on this worktree, using the main virtualenv: all dots, no failure.
  The summary line did not print, so I did not read a pass count.
- `git cat-file -t` on every hash named in the CHANGELOG and here: all `commit`.
- Numbers (21.6 s, 97.0 s, $0.1561, 41.2 s, $0.1511, 56, 28, 320 x 320, 17 not yet listed, seven
  redirect hosts) checked against `docs/handoff/main.md`, `docs/handoff/readme.md`,
  `vercel.json`, `agent/limits.py` and `curator/images.py`. Search 115's 76.5 s and "5 of 6
  published" come from the brief only; no file in the repo holds them (README holds 41.2 s and
  $0.1511).
- Links: no new link was added. I did not run a link checker.
- Not checked: the live site, the bank, `pnpm` checks (no node_modules here), the README render.
