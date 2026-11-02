# Changelog

What changed on the live site and in the repo since the README was rewritten for the public
release. Everything before that, session by session with its decisions, checks and costs, is in
[`docs/PLAN.md`](docs/PLAN.md).

## 2026-11-02

- **The EASY question goes first.** A search now makes the EASY question alone, and starts its other
  items when it ends. With that question already in the bank, every live item starts together. If the
  first run fails with nothing spent, the model is out of reach, so the others never start and the
  search does not count. Reservations and caps are unchanged. Expect a new topic to take up to about
  90 s; this order has not been measured yet.
- **Every item at once, measured.** Before the change above, this was the time with every item
  started together. A new topic's six items used to run one after another:
  a median of 145.2 s (118.9 to 171.6 s, 4 searches, 2026-10-28 to 2026-10-30, last run finished
  less first run started). The first search to succeed since the change took 61.3 s, with its first
  item at 35 s and its first question at 49 s. That is one search (n=1), "Light speed", not a median.
  About 20 s of it looks like a one-time cost, not the search itself: the first model call after more
  than a day without a run took about 20 s, once for each kind of item, which fits the API compiling
  the strict tool schemas again. Without those first calls this search would have taken about 41 s,
  but no search has yet been measured that way.

## 2026-11-01

- **A search the model never answered is free.** A search counts against the daily limits unless
  every run of it failed with nothing spent, as a refused key or an outage leaves it. The dollar caps
  are unchanged. The page says the agent is unavailable, and each run says it could not reach the
  model. (Migration 013, `55fc118`, `e2ed90f`, `6a4c6eb`)
- **A daily run that never reached the model fails.** When every job of the daily Curator ended with
  no item and nothing spent, the workflow now goes red. A refused key had left that day's run green.
  (`c55ba49`)

## 2026-10-30

- **November's budget for the launch.** Live research gets $20 for the calendar month of
  November 2026 (usually $4), so the launch cannot use up the month in its first days. The launch
  week (the UTC days 3 to 9 November) now allows 14 searches and $3.25 a day for everyone (was 20
  and $2.50), still 5 a visitor: at about $0.17 a six-item search, the whole week at full use
  costs about $17. Both windows are dated in code (`limits_at` in `agent/limits.py`), so the usual
  limits come back after 9 November, and the $4 month on 1 December, with no deploy. The
  Anthropic Console limit is $32 for November ($20 here, about $5 for the daily Curator, $5 to
  fill the bank with 30 likely topics, $2 spare) and goes back to $10 on 1 December. Mission
  Control shows the caps in force, so November shows $20 for live research and $32 for the
  Anthropic limit. Also from the launch code review: a refusal message can no longer fail on a
  stray brace.

## 2026-10-28

- **Every topic at every level.** Learn and Quiz now list a topic only once it has an
  explanation and a question at easy, medium and hard, so each level offers the same topics.
  The new `python -m curator complete` fills the gaps, and the daily run fills up to six a day.
  Seven visitor-typed topic names were tidied, and "Bang" merged into "The Big Bang".
  (`f1934b0`, `1036a3f`)
- **Explore researches every level.** The difficulty control is gone: a search makes a question
  and an explanation at each level, and after the questions the explanations open in EASY,
  MEDIUM and HARD tabs. Whatever a search's time limit leaves out, the agent writes overnight.
  (`27fa151`)
- **Surprise me.** A button on Explore asks the agent to pick a topic the bank does not have yet,
  then researches it. It uses one search, and a pick that fails counts nothing. (`27fa151`)
- **The bank filled for every level.** Two Curator runs and a re-check of the items the Jev
  outage had held, each item in doubt read against its sources: 37 of the 44 topics now have an
  explanation and a question at every level; 7 stay off Learn and Quiz until their last slot is
  filled.

## 2026-10-21

- **Launch week for the LinkedIn post.** For the UTC days 3 to 9 November 2026, each visitor
  gets 5 live searches a day (usually 2), and everyone together 20 searches and $2.50 a day
  (usually 4 and $0.50). The $4 monthly cap on live research is unchanged, so the launch never
  spends more than a usual month. The dates are in code (`limits_at` in `agent/limits.py`), so
  the window opens and closes by itself, with no deploy. (`3765728`)
- **Review queue cleared.** The 9 items the publish gate was unsure about were judged against
  their sources: 5 published, 4 discarded (one had two right answers, one a false claim in its
  explanation, one presented unconfirmed galaxy candidates as confirmed, one a "wrong" option
  that is a real mechanism). The bank holds 190 published items. (`0cbcf4f`)

## 2026-10-19

- **Version 1 complete, and the repo public** under the MIT licence, after one more secret scan
  of the whole history (clean). Secret scanning with push protection and Dependabot alerts are
  on. (`b6f60cd`)
- **The header's GitHub icon** links to the repo instead of the author's profile. (`3389a49`)
- **Local Python updated** to 3.12.10 and the virtualenv rebuilt (security audit finding S16).
  (`5dffe9f`)

## 2026-10-17

- **Difficulty is a dropdown** on Learn, each topic, Quiz and Explore, built on the browser's
  own select, so a phone shows its native picker. The Learn bar is one row at every width
  (74 px tall on a phone, was 130 px). (`1304f0c`)
- **No more zoom on iPhone forms.** A test now fails if any text field is under 16 px, which
  makes iOS zoom in; it caught the Report box, now 16 px. (`1304f0c`)

## 2026-10-13

- **"Analytics for nerds" is now "Mission Control"**, everywhere on the site. (`024f0fe`)
- **The README rewritten** for recruiters first, then engineers, with three screenshots of the
  live site and every number checked against its source; setup and the repo map moved to
  [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). (`52b98d2`)
- **Checks on every push and pull request** in GitHub Actions: the Python tests, lint, format
  and types, and the site's typecheck, tests and build, with no secrets and no paid calls.
  pnpm is pinned to 11.5.0 for CI and Vercel alike. (`4883f3c`)
