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
| latency | `session/latency` (not made yet; works on `main`) | `../cqa-latency` (planned; now in the main folder, `cosmic-quiz-agent`) | The live-search backend, the bank schema and the shared docs: see "latency owns" | Active | 2026-10-28 |
| explore | `session/explore` (landed on `main`) | `../cqa-explore` | The Explore page's frontend: see "explore owns" | Done: universal topics and Surprise me are on `main`; follow-ups in `docs/handoff/explore.md` | 2026-10-28 |

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

### Open questions for Vedant

- **Runs per search.** The cost-guard decision below reserves 4 runs at $0.17 each ($0.68 a
  search). The uncommitted `agent/limits.py` sets `runs_per_search = 6` with "about $0.17 for all
  six". These cannot both hold; the cost guard needs one number.
- **Migration 009** cites `docs/PLAN.md` "Universal topics", and PLAN.md has no such section yet.
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

---

## Do-not-touch / shared files

Only the listed owner edits these. Any other session that needs a change writes the exact text
it wants in its own `docs/handoff/<session>.md` and asks Vedant.

| File | Owner | Why |
| --- | --- | --- |
| `supabase/schema.sql`, `supabase/migrations/**` | latency | Migrations are numbered and run once on the live bank; two sessions picking the same number breaks it |
| `docs/PLAN.md` | latency | Nearly 2,000 lines, edited in many places; parallel edits conflict |
| `CHANGELOG.md`, `README.md` | latency | One voice for what shipped |
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
