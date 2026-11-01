# Parallel sessions

How several Claude Code sessions work on this repo at once without stepping on each other. Each
session has its own git worktree (a separate folder on its own branch, sharing one `.git`), owns
a set of files, and leaves notes in `docs/handoff/<session>.md`. Set up on 2026-10-28; the rules
are also in `CLAUDE.md`, "Parallel sessions".

A new session: `dev/new-session.sh <name>` (Git Bash) or `dev/new-session.ps1 <name>`
(PowerShell) makes the worktree, then claim a row below.

---

## Active sessions

| Session | Branch | Worktree path | Owns (files/dirs) | Status | Last update |
| --- | --- | --- | --- | --- | --- |
| latency | `session/latency` | `../cqa-latency` | The live-search backend, the bank schema and the shared docs: see "latency owns" | Active: parallel search live; after time and the fill list waiting (`docs/handoff/latency.md`) | 2026-11-01 |
| explore | `session/explore` (landed on `main`) | `../cqa-explore` | The Explore page's frontend: see "explore owns" | Done: universal topics and Surprise me are on `main`; follow-ups in `docs/handoff/explore.md`. Its files pass to ui and media (2026-10-30) | 2026-10-30 |
| main | `main` | the main folder | Coordination only, no code: this file, `docs/handoff/*.md` briefs, reviews | Active: the pre-launch overhaul (`docs/handoff/main.md`) | 2026-10-30 |
| data | `session/data` | `../cqa-data` | Accounts: see "data owns" | Active: migration 011 written; `agent/auth.py` next (`docs/handoff/data.md`) | 2026-10-30 |
| ui | `session/ui` | `../cqa-ui` | Header, cards, progress rows, ranks: see "ui owns" | Briefed, not started (`docs/handoff/ui.md`) | 2026-10-30 |
| seo | `session/seo` | `../cqa-seo` | The rename, metadata, prerendering, redirects: see "seo owns" | Briefed, not started (`docs/handoff/seo.md`) | 2026-10-30 |
| media | `session/media` | `../cqa-media` | Topic images: see "media owns" | Built and tested; dry run for Vedant to read, then migration 012 and the real fill (`docs/handoff/media.md`) | 2026-10-30 |

Both sessions were still running in the main folder on `main` when this file was written, so
until they move, their uncommitted changes share one working tree ("Uncommitted work" below).

### latency owns

Parallel search and the cost guard.

- `agent/ondemand.py`, `agent/limits.py`, `agent/store.py`, `agent/bank.py`, `agent/topic_pick.py`
- `api/research.py`, `api/quota.py`, `api/topics.py`
- `supabase/**` (sole owner)
- `curator/**` (it holds the uncommitted universal-topics work; see below)
- `tests/test_ondemand.py`, `tests/test_quota.py`, `tests/test_store.py`, `tests/test_api.py`,
  `tests/test_curator.py`
- `src/search.ts`, `src/quota.ts`, `src/useQuota.ts`, `src/api.ts`, `src/types.ts`,
  `src/components/AgentLog.tsx`, and their tests (the live-search stream and the quota on the page)
- `docs/PLAN.md`, `CHANGELOG.md`, `README.md` (sole owner; see "Do-not-touch / shared files")
- `docs/handoff/latency.md`

### explore owns

Random topics on the Explore page (`/explore`).

- `src/pages/ExplorePage.tsx`
- `src/components/TopicInput.tsx`, `src/components/DiceIcon.tsx`
- `src/topics.ts`, `src/useTopics.ts`, `src/topics.test.ts`
- `docs/handoff/explore.md`

### The pre-launch overhaul (2026-10-30)

Five sessions, briefed by main in `docs/handoff/<name>.md`. latency keeps everything above,
except `api/topics.py` (to media). explore's files pass to ui (`ExplorePage.tsx`,
`TopicInput.tsx`, `DiceIcon.tsx`) and media (`src/topics.ts`, `src/useTopics.ts`,
`src/topics.test.ts`). Migrations have reserved numbers: **010 latency, 011 data, 012 media**;
each writes only its own file, and latency folds them into `supabase/schema.sql`.

**data owns:** `supabase/migrations/011_*.sql`, `agent/auth.py`, `api/account.py`,
`src/session.ts`, `src/useSession.ts`, `src/profile.ts`, `src/useProfile.ts`,
`src/profile.test.ts`, `src/pages/AccountPage.tsx`, `src/components/SignInButton.tsx`,
`src/pages/PrivacyPage.tsx`, their tests, `docs/handoff/data.md`.

**ui owns:** `src/App.tsx`, `src/game.ts` (ranks), `src/index.css`, every page in `src/pages/`
except `NotFoundPage.tsx` (seo), `PrivacyPage.tsx` and `AccountPage.tsx` (data), every component
in `src/components/` except `AgentLog.tsx` (latency) and `SignInButton.tsx` (data), the new
`SearchProgress.tsx` and `FactCard.tsx`, their tests, `docs/handoff/ui.md`.

**seo owns:** `src/brand.ts`, `index.html`, `vercel.json` (sole editor), `public/robots.txt`,
the favicon set and web manifest, the sitemap and prerender scripts, `src/router.ts`,
`src/router.test.ts`, `src/pages/NotFoundPage.tsx`, the close-match module, the README rename
only, `docs/handoff/seo.md`. Its first pass, the brand-string replacement across `src/`, merges
before ui edits those files.

**media owns:** `curator/images.py`, `supabase/migrations/012_*.sql`, `api/topics.py`,
`src/topics.ts`, `src/useTopics.ts`, `src/topics.test.ts`, `tests/test_images.py`,
`docs/handoff/media.md`.

### Files both could plausibly touch

The default owner edits; the other session stops and asks Vedant.

| File | latency's reason | explore's reason | Default owner |
| --- | --- | --- | --- |
| `api/research.py`, `agent/ondemand.py` | Parallel runs and reserving every run up front | Surprise me (`{"surprise": true}`), already mixed into the same uncommitted diff | latency |
| `agent/topic_pick.py` | Sits in its files (the picker is a paid run under the caps) | The random-topic picker itself | latency, until Vedant says otherwise |
| `src/api.ts`, `src/types.ts` | The streamed event types change with parallel runs | The request body (`surprise`, no `difficulty`) | latency |
| `src/search.ts` | The live-search client state | Starting a Surprise me search | latency |
| `src/pages/ExplorePage.tsx` | Showing parallel progress | The page itself | explore |
| `src/components/AgentLog.tsx` | Interleaved steps from parallel runs | How a picked topic is announced | latency |
| `tests/test_api.py` | `/api/research` and `/api/topics` tests | Surprise me request tests | latency |

---

## Uncommitted work in the main folder (2026-10-28)

Found when this file was written; setup touched none of it. None of it is parallel-search code
yet. It is two strands, mixed in the same files, so it should be committed by one session, not
split hunk by hunk:

1. **Universal topics** (every topic at every level, decided 2026-10-28): `runs_per_search` 4 to
   6, a search makes all three levels, `/api/topics` lists only complete topics, and
   `python -m curator complete`. Files: `agent/limits.py`, `agent/ondemand.py`, `agent/store.py`,
   `api/topics.py`, `api/research.py`, `curator/__main__.py`, `curator/pipeline.py`,
   `supabase/schema.sql`, `supabase/migrations/009_universal_topics.sql` (new),
   `tests/test_curator.py`, `tests/test_store.py`, `tests/test_api.py`.
2. **Surprise me** (the agent picks a topic the bank lacks): `agent/topic_pick.py` (new),
   `agent/bank.py`, and hunks in `agent/ondemand.py` and `api/research.py`.
3. **Docs from 2026-10-22** (the launch week's code review and November's budget):
   `docs/PLAN.md`, `docs/NEXT_SESSION.md`.

Resolved 2026-10-28: universal topics and Surprise me are committed on `session/explore`, and
the 2026-10-22 docs on `session/latency` (`289a0cd`). The main folder has no uncommitted work.

### Open questions for Vedant

- **Runs per search.** The cost-guard decision below reserves 4 runs at $0.17 each ($0.68 a
  search). The uncommitted `agent/limits.py` sets `runs_per_search = 6` with "about $0.17 for all
  six". These cannot both hold; the cost guard needs one number. Answered 2026-10-28: six (see
  Decisions).
- **Migration 009** cites `docs/PLAN.md` "Universal topics", and PLAN.md has no such section yet.
  Answered 2026-10-28: the section is in `docs/PLAN.md` on `session/latency` (`30fafd2`).
- **Dev servers.** `vite.config.ts` sends `/api` to port 8787 for every worktree, so two
  worktrees cannot run the site against their own API at once. Until that changes, one session
  at a time runs the dev servers, and no session stops a server it did not start.

---

## Decisions (append-only)

Add new entries at the bottom: the date, the session, and the decision. Never edit or remove an
entry; record a reversal as a new one.

- 2026-10-28, latency: Ship parallel search before the 3 November LinkedIn launch. Go/no-go on
  Sunday 1 November: if it is not deployed and verified on live by then, launch on the current
  version.
- 2026-10-28, latency: Cost guard: reserve all 4 runs up front at $0.17 each ($0.68 a search).
  The daily cap is about $1.05 normally and about $2.90 in the launch week; the $4 monthly cap
  is unchanged.
- 2026-10-28, latency: When the day's budget cannot fit all of a search's runs, reserve what fits
  in plan order (the chosen-level question, the other questions, the explanation); the rest are
  reported as "not started".
- 2026-10-28, explore: Universal topics and Surprise me (Vedant, grill-me session), on `main`:
  - Learn and Quiz list a topic only when it has every level in both modes.
  - A slot gets 3 tries; a slot with an item in review waits for the review queue.
  - Explore has no difficulty and makes all six items.
  - `runs_per_search` is 6, with the dollar caps unchanged.
  - `python -m curator complete` fills the gaps under a $3 cap; `daily` fills 6 slots a day
    before its news topic.
  - SURPRISE ME is a Haiku pick that counts as a search and skips Jev.
  - Seven visitor-typed names were tidied, and "Bang" merged into "The Big Bang".
  - The full list is in `docs/handoff/explore.md`.
- 2026-10-28, latency: Runs per search: six, on universal topics, which lands on `main` first;
  latency builds on it. This replaces the numbers in the cost-guard entry above: reserve 6 runs at
  $0.17 ($1.02 a search); the daily cap is about $1.55 usually, and in the launch week about $4.25
  at 20 searches or $2.90 at 12, whichever November's budget settles. The monthly cap is
  unchanged. Plan order is the questions, easiest first, then the explanations, easiest first.
- 2026-10-28, latency: Play order: the questions are played easiest first, as universal topics
  has them, even when a harder one finishes first. (The grill chose "the chosen level first"
  for the four-run search, which has a difficulty a search no longer has.)
- 2026-10-28, latency: Agent log: one stream in the order things happen, each line tagged with
  its item (EASY Q, HARD EXPL and so on) in place of the item headings.
- 2026-10-28, latency: Rate limits: no new limit. Vedant checks the account's tier in the
  Anthropic Console before the go/no-go; each live run logs how many 429s it met.
- 2026-10-28, latency: Verification: tests with the scripted model and fake Jev, a headless
  drive against the stub API, then 2 real searches locally and 1 on the live site, about $0.50.
- 2026-10-28, latency: Scope: no Mission Control change. Before and after search times come from
  one query on `on_demand_runs`, recorded in `docs/PLAN.md` and the changelog.
- 2026-10-28, latency: A shared research pass (research once, write every item from it) waits
  until after the launch; it needs its own eval.
- 2026-10-28, latency: November's budget, redone at about $0.17 a search (six items): option A.
  The launch days (3 to 9 November) allow 14 searches a day for everyone (was 20), still 5 a
  visitor, with a daily cap of $3.25 under the parallel cost guard. Live research has $20 for the
  calendar month of November, ending by itself on 1 December. Vedant raises the Console limit to
  $27 before 3 November and lowers it to $10 on 1 December. At full use the launch week costs
  $18.02 with 1 and 2 November.
- 2026-10-28, latency: Universal topics lands on `main` by Vedant (`git merge --ff-only
  session/explore` in the main folder) once the explore session is done; latency then runs
  `git rebase main`. The explore handoff's text for `docs/PLAN.md` and `CHANGELOG.md` is folded
  in once that session has written it.
- 2026-10-28, latency: Done. Universal topics landed on `main` by fast-forward to `19e2640`
  (run by Claude Code on Vedant's word; not pushed), and Vedant applied migration 009; the live
  bank shows 67 missing slots in 27 topics, as counted. `session/latency` rebased onto it, and
  the explore text is folded into `docs/PLAN.md` and `CHANGELOG.md` (`30fafd2`).
- 2026-10-28, latency: The Anthropic workspace reached its monthly limit during the fill (access
  back on 1 November 00:00 UTC). Vedant raises October's limit by about $2, a dated exception to
  hard rule 1, so live research, the Curator and the parallel-search real searches work before
  the go/no-go. The review queue is decided: 17 published, 9 discarded.
- 2026-10-28, latency: The second fill's 10 review items decided (5 published, 5 discarded); the
  queue is empty and 37 of 44 topics are on every level. Vedant asked to end the session clean
  and push: `session/latency` rebased onto the explore close, `main` fast-forwarded and pushed.
  Parallel search and November's budget (steps 3 to 5) continue in the next latency session.
- 2026-10-30, main: The pre-launch overhaul (Vedant, grill-me session; each the recommendation
  unless noted). Briefs in `docs/handoff/{latency,data,ui,seo,media}.md`; coordination in
  `docs/handoff/main.md`.
  - Accounts: optional, guests as now; Google and an email link (Resend), no passwords; private
    profiles with one row per answer (leaderboard-ready); guest progress added to the account on
    sign-in, no prompt; signed-in limits per account, same numbers, global caps unchanged.
  - Speed: parallel search as planned, plus a Curator fill of 30 likely topics (about $5, from
    November's budget, on or after 1 November). Jev cannot crawl; model calls are 90% of a run.
  - Progress: one row per item, moved by real streamed steps, time left from measured medians, a
    status line naming the real work, the agent log behind "Show details".
  - Topic cards: real NASA or Wikimedia images (public domain or CC only, credited, code-only
    fill, no model calls), WebP in Supabase Storage served from the site's own origin; a fact
    card where none fits; no AI art.
  - Controls: a sticky header with navigation, sign-in and each page's settings; each question's
    actions on its card ("Read the explanation", "Sources (n)", "Next"), the panels closed but
    remembering the last choice, also on web search cards.
  - Search: prerendered Learn pages, /quiz and /explore with JSON-LD, rebuilt by a deploy hook
    after the Curator publishes; subdomain aliases and close-match paths for typos; no
    look-alike domains.
  - Name (Vedant's own idea, after the Mars rovers): **Curiosity**, at
    `curiosity.vedantgaikwad.ie`, with `cosmic.` and the aliases redirecting (301); the repo
    keeps its name. The title tag is decided last, on Monday 2 November (Vedant's direction: "the
    wonders beyond Earth"). Ranks become the six rovers in launch order, each with a cited fact.
  - Link previews: Vedant makes the site-wide `og-v2.jpg`; each topic's is generated at build.
  - Timing (Vedant's call, against the recommendation to ship some after launch): everything
    before the launch. Code freeze Monday 2 November 18:00 Dublin; if late, cut accounts, then
    prerendering, then image cards.
  - Sessions: five (latency, data, ui, seo, media) in Vedant's terminal tabs; main writes the
    briefs and reviews every branch, and edits no code.
- 2026-10-30, latency: November's budget built (Vedant's answers, relayed by main). The Console
  limit for November is $32: $20 live research, about $5 for the daily Curator, $5 for the
  30-topic fill, $2 spare; back to $10 on 1 December. The fill counts against the Console only,
  not the $20 live cap. The worst case ($3.25 a day for 7 days, $22.75) is accepted: the $20 cap
  holds and pauses live search late in the launch week. Mission Control reads the live cap
  through `limits_at`. Progress estimates come from a SQL function in migration 010 (medians of
  the last 30 days of runs). The deploy hook fires once per Curator run that published anything.
  latency may edit `.github/workflows/curator.yml` (one env line), `agent/stats.py` (the cap
  line) and `docs/DEVELOPMENT.md` (parallel search).
- 2026-10-30, latency: Migration 010 written on Vedant's go, with main's notes: a plan that is
  not an array, is empty or is longer than a search raises (a bug, not a limit), so the "search"
  limit name is gone; items are read `with ordinality` and ids return in plan order; a stale
  reservation (a run killed by a crash or the 300 s timeout) keeps holding its money, now up to
  $1.02 a search, kept as the safe side of hard rule 1, with a read-only query in
  `docs/PLAN.md`; Surprise me's pick before the reservation can cost a refused visitor about
  $0.003, accepted. Estimates: `percentile_cont(0.5)`, `llm_error` left out, 5 runs minimum, 17 s
  fallback. Threads named `live-search-<id>-<key>`.

- 2026-10-30, data: Accounts, how they are built (Vedant, each the recommendation):
  - The browser signs in with `@supabase/auth-js` (MIT, free, 24 KB gzipped), loaded only when
    a visitor signs in, returns from a sign-in or already has a session; table reads and writes
    are plain `fetch` calls to PostgREST. Not `supabase-js` (56 KB gzipped).
  - `agent/auth.py` checks a token by calling Supabase's `/auth/v1/user` with `httpx2`: no new
    dependency, and a deleted or signed-out user is refused at once. Not a local JWT check.
  - On sign-in, the guest profile moves into the account and the browser's guest profile is
    emptied; after sign-out the browser starts as a fresh guest.
  - The sign-in email carries both a link and a 6-digit code, so it works from another browser
    or device.
  - The account is recalculated by replaying its history through the pure functions in
    `src/profile.ts`: each guest's earlier totals as a baseline, then every answer, finished run,
    read and live search in time order. Each event has a client-made UUID, so merging twice
    changes nothing. Migration 011 therefore holds `player_answers`, `player_reads`,
    `player_runs`, `player_searches` and `player_baselines`, in place of the brief's `profiles`,
    `answers`, `learned` and `seen` (seen and played topics come out of the replay).

- 2026-10-30, data: Migration 011 approved by Vedant with eight changes:
  - The browser makes a new guest id after each successful merge (a test covers sign in, sign
    out, play as a guest, sign in again).
  - All privileges on the five tables are revoked from `anon` and `authenticated`; only select
    and insert are granted to `authenticated`. RLS stays on with its two policies a table.
  - The row caps are listed in the migration and refused with SQLSTATE `CQ001`; the browser
    drops such a row, logs it once and does not retry. Other errors keep the retry.
  - `correct` and `points` stay, but a future leaderboard re-scores on the server from
    `item_id` and `choice`. `item_id` is the source of truth for the topic; `topic` is a
    snapshot.
  - The per-account limit key in `on_demand_runs` is a salted hash of the user id, never the
    id. Those rows stay after an account is deleted, and the privacy page says so.
  - No delete policy: `api/account.py` deletes with the secret key after `agent/auth.py` checks
    the token, and the account page asks the player to confirm.
  - Rows are kept until the player deletes the account. A purge of inactive accounts is a
    follow-up after the launch.

- 2026-10-30, media: Plan answered by Vedant (each the recommendation):
  - `agent/bank.py` and `src/types.ts` (latency's) get small additive edits: optional `image` and
    `fact` on `BankTopic`, with the `TopicImage` and `TopicFact` types. Nothing else in them changes.
  - Pillow 13.0.0 (free, HPND licence) is approved as a Curator-only dependency in the new
    `requirements-media.txt`, kept out of `requirements.txt` and `pyproject.toml`. `requirements-dev.txt`
    includes it so the tests run; `tests/test_images.py` checks it never reaches the Vercel lists.
  - The step in `.github/workflows/curator.yml` is written as text in `docs/handoff/media.md`; latency
    adds it.
  - Order of work: code and tests, then `python -m curator.images --dry-run` for Vedant to read,
    then migration 012 and the real fill. Nothing is uploaded or written before that.
- 2026-10-30, media: Design choices inside the brief: images are in a `topic_images` table (not
  columns on `topics`); a card is 640 x 360 WebP (16:9, about 40 KB), a link preview 1200 x 630
  (up to 120 KB, only when the source is big enough); Commons' `Attribution` field is the credit;
  CC BY-SA IGO is accepted as a CC BY-SA variant; a NASA library result passes only if every
  credit it names is NASA's and nothing claims copyright; `/api/topics` leaves `image` and
  `fact` out when a topic has neither.
- 2026-11-01, latency: The likely-topic fill (Vedant, relayed by main).
  - The fill is approved: the 30 topics in `docs/handoff/latency.md`, as listed, with `--cap 5.00`.
    The 5 reserves stay reserves.
  - The eval overlap stays, all 13 names. No code in `evals/` reads the bank.
  - Vedant reviews the queue before 3 November.
  - It runs only after Vedant fixes the GitHub `ANTHROPIC_API_KEY`, after one cheap key test, and
    after main gives the word.
- 2026-11-01, latency: A search that failed whole with no spend does not count (Vedant, relayed
  by main), after a refused key took two of his searches.
  - A search counts unless every run of it has ended as `failed` with `spent_usd` 0, for the
    visitor's daily limit and everyone's. A search still running counts. The dollar caps are as
    they were.
  - Migration 013 (`on_demand_search_counts`, `begin_on_demand_search`) and `on_demand_usage` use
    the same rule. Paste 013 and run its check before the code is deployed.
  - A search that reserved runs ends with a new event, `{"type": "end", "unavailable": bool}`;
    ui changes the text on the page.
- 2026-11-01, latency: Main's review of free failed searches. 013 is approved. A run that failed
  with nothing spent sends `missed` with reason `failed` and the text "The agent could not reach
  the model." The ui text stays as Vedant chose it, and the rare failed write is accepted. The
  cost while the model is out of reach (one on-topic check per try) is accepted. Vedant pastes 013
  and runs its check; main deploys the code after "CHECK PASSED".

---

## Do-not-touch / shared files

Only the listed owner edits these. Any other session that needs a change writes the exact text
it wants in its own `docs/handoff/<session>.md` and asks Vedant.

| File | Owner | Why |
| --- | --- | --- |
| `supabase/schema.sql`, `supabase/migrations/**` | latency (011 data, 012 media, from 2026-10-30) | Migrations are numbered and run once on the live bank; two sessions picking the same number breaks it, hence the reserved numbers |
| `docs/PLAN.md` | latency | Nearly 2,000 lines, edited in many places; parallel edits conflict |
| `CHANGELOG.md`, `README.md` | latency (the README rename: seo) | One voice for what shipped |
| `vercel.json` | seo | Redirects, rewrites and the CSP in one place; data and media send seo the exact change |
| `CLAUDE.md` | Vedant | Changes only with his approval, from one session at a time |
| `docs/NEXT_SESSION.md` | none (frozen) | Replaced by `docs/handoff/<session>.md`; left as it stands |
| `docs/DESIGN.md` | Vedant | Locked decisions; reopen only after flagging it to him |
| `agent/limits.py` | latency | Every dollar cap lives here, under hard rule 1 |
| `package.json`, `pnpm-lock.yaml`, `requirements*.txt` | Ask first | A dependency change reaches every session, and hard rule 1 needs its price stated |
| `.env` | Nobody commits it | Copied into each worktree by `dev/new-session.*`; covered by `.gitignore` |

---

## How to sync

Worktrees share one repository, so every local branch (`main`, `session/latency`,
`session/explore`) is visible from every folder at once, with no fetch needed. `origin` only
changes when someone pushes, and only Vedant decides that.

Commit small and often on your own branch, staging by path:

```bash
git status                        # check that only your files changed
git add path/to/file another/file # never -A, never .
git commit -m "Short, focused message"
```

Before finishing (a rebase refuses to run with uncommitted changes, which is the point):

```bash
git fetch
git rebase origin/main            # what the task asks for; enough once main is pushed
git rebase main                   # also do this when local main has commits not yet pushed
```

See and take another session's work:

```bash
git log --oneline main..session/explore   # its commits not yet on main
git diff main...session/explore           # what it changed since it left main
git merge session/explore                 # take it all into your branch
git cherry-pick <sha>                     # or take one commit
```

From another machine or clone, fetch it first: `git fetch origin session/explore`, then use
`origin/session/explore` in the commands above.

Land a session's work on main (Vedant, from the main folder, after it rebased onto main):

```bash
git merge --ff-only session/latency
```

Never use `git stash` (one stash list is shared by every worktree, so a session can pop another's
changes), `git add -A`, `git commit -a`, `git reset --hard` or `git checkout -- <file>`. A branch
can be checked out in only one worktree; if git refuses that, another session holds it.
