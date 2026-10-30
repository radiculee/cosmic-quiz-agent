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
| latency | `session/latency` | `../cqa-latency` | The live-search backend, the bank schema and the shared docs: see "latency owns" | Paused: on `main` and pushed; parallel search and November's budget next (`docs/handoff/latency.md`) | 2026-10-28 |
| explore | `session/explore` (landed on `main`) | `../cqa-explore` | The Explore page's frontend: see "explore owns" | Done: universal topics and Surprise me are on `main`; follow-ups in `docs/handoff/explore.md`. Its files pass to ui and media (2026-10-30) | 2026-10-30 |
| main | `main` | the main folder | Coordination only, no code: this file, `docs/handoff/*.md` briefs, reviews | Active: the pre-launch overhaul (`docs/handoff/main.md`) | 2026-10-30 |
| data | `session/data` | `../cqa-data` | Accounts: see "data owns" | Briefed, not started (`docs/handoff/data.md`) | 2026-10-30 |
| ui | `session/ui` | `../cqa-ui` | Header, cards, progress rows, ranks: see "ui owns" | Briefed, not started (`docs/handoff/ui.md`) | 2026-10-30 |
| seo | `session/seo` | `../cqa-seo` | The rename, metadata, prerendering, redirects: see "seo owns" | Briefed, not started (`docs/handoff/seo.md`) | 2026-10-30 |
| media | `session/media` | `../cqa-media` | Topic images: see "media owns" | Briefed, not started (`docs/handoff/media.md`) | 2026-10-30 |

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
