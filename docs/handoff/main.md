# Handoff: main (coordinator)

Notes for the main session (`docs/SESSIONS.md`), which plans, writes the other sessions' briefs
and reviews their branches. It edits no code: only `docs/SESSIONS.md`, `docs/handoff/*.md` and,
once Vedant approves the text below, `docs/DESIGN.md` and `CLAUDE.md`.

Last update: 2026-10-30

## Current goal

The pre-launch overhaul, settled in a grill-me session on 2026-10-30 (22 questions, recorded in
`docs/SESSIONS.md`, Decisions). Five sessions build it in parallel: latency, data, ui, seo and
media. Code freeze **Monday 2 November 18:00 Dublin**; deploy and live check that evening. If
work is late it is cut in this order: accounts, then prerendering, then image cards.

## Review protocol

1. A session tells Vedant a piece is ready: rebased onto `main`, every check green, its handoff
   updated.
2. Vedant asks main to review. Main reads `git diff main...session/<name>` and the handoff, and
   checks the piece against its brief, the hard rules in `CLAUDE.md` and the ownership table.
   Findings go back through Vedant as a numbered list; nothing merges with an open finding.
3. Vedant lands it from the main folder: `git merge --ff-only session/<name>`. Every other session
   then rebases onto `main`.

Merge order on Monday (earlier where a piece is ready): latency, seo, media, ui, data. seo's
`src/brand.ts` pass lands first of all, on Saturday morning.

## Edits to Vedant's files (approved by Vedant and applied, 2026-10-30)

### `docs/DESIGN.md`

Replace the "Player state" default with:

> - **Player state:** optional accounts (changed 2026-10-30 by Vedant, grill-me; it was "no
>   accounts", with accounts planned for v2). Guests play as before, with the profile in
>   `localStorage`. Signing in (Google, or an email link through Resend; no passwords) saves
>   progress to Supabase: one row per answer, plus what was read and seen, behind row-level
>   security, so a server-scored leaderboard can be added later. On sign-in, guest progress is
>   added to the account and points and trophies are recalculated from the history. Signed-in
>   users are limited per account, guests per salted IP hash; the global caps are unchanged. An
>   account can be exported and deleted from its page.

In the Context paragraph and the Repo layout, replace `cosmic.vedantgaikwad.ie` with
`curiosity.vedantgaikwad.ie` and add:

> (Changed 2026-10-30 by Vedant: the site is named **Curiosity**, after the Mars rover, and moves
> to `curiosity.vedantgaikwad.ie`; `cosmic.` and a few typo subdomains redirect there
> permanently. The repo keeps the name `cosmic-quiz-agent`.)

Add to the Decisions list:

> 10. **Pre-launch overhaul** (grill-me, 2026-10-30): parallel search plus a Curator fill of 30
>     likely topics; progress rows driven by the agent's real steps; real NASA or Wikimedia images
>     on topic cards (public domain or CC only, credited, served from the site's own origin), with
>     a fact card where none fits; a sticky header with navigation and each page's settings, while
>     each question's actions stay on its card; prerendered Learn pages with structured data; rover
>     ranks (Sojourner to Perseverance). Full list: `docs/SESSIONS.md`, Decisions, 2026-10-30.

### `CLAUDE.md`

- "What this project is": the first line becomes **Curiosity** (repo `cosmic-quiz-agent`, the
  name changed 2026-10-30 by Vedant, after the Mars rover), and `cosmic.vedantgaikwad.ie` becomes
  `curiosity.vedantgaikwad.ie` (cosmic. redirects).
- Under v1, add: "Optional sign-in (Google or an email link) saves progress to Supabase;
  guests play as before (changed 2026-10-30 by Vedant)."
- Hard rule 1, append: "Resend's free tier (3,000 emails a month, 100 a day) sends sign-in links;
  Supabase Auth's free tier covers 50,000 monthly users; Supabase Storage holds topic images on
  the free tier (1 GB stored, 5 GB transferred a month)."
- Hard rule 5, append: "The browser holds a signed-in user's session token, never another key;
  every user table is behind row-level security."
- Design tokens: no change.

## Done

- 2026-10-30: the grill-me session; the plan; the five briefs (`docs/handoff/{data,ui,seo,media}.md`
  and a new section at the end of `docs/handoff/latency.md`); the rows, ownership and decisions in
  `docs/SESSIONS.md`.

## Next

- Done 2026-10-30: Vedant approved the drafts above (applied to `docs/DESIGN.md` and `CLAUDE.md`);
  this coordination is committed on `main`, so every new worktree starts with the briefs.
- Vedant: start the sessions (below), then review each piece as it is ready.
- Monday before the freeze: Vedant picks the title tag (candidates in `docs/handoff/seo.md`).

### Starting the sessions

On this Mac, `dev/new-session.sh` prints `source .venv/Scripts/activate` (the Windows path); use
`source .venv/bin/activate`. Node 22 LTS is needed first: Vite 8 does not run on Node 16 or 20.17.

```zsh
cd ~/cosmic-quiz-agent
for name in latency data ui seo media; do dev/new-session.sh "$name"; done
```

The earlier latency session ran on Windows (`C:\Users\vedan\cqa-latency`) and pushed everything to
`main`; this Mac has no `session/latency` branch, so latency starts a fresh worktree here like the
others. If the Windows machine still has unpushed work on `session/latency`, push it first.

Then in each folder: `python3.12 -m venv .venv && source .venv/bin/activate && pip install -r
requirements-dev.txt && pnpm install`, then `claude`, with this first message (name filled in):

> Read CLAUDE.md, docs/SESSIONS.md and docs/handoff/<name>.md, then docs/DESIGN.md and
> docs/PLAN.md. You are the "<name>" session, in the worktree ../cqa-<name> on branch
> session/<name>. Your brief is in your handoff. Follow "Parallel sessions" in CLAUDE.md and edit
> only the files your session owns. Tell me your plan before changing code.

### Models (set with `/model` in each session)

| Session | Model | Why |
| --- | --- | --- |
| main (review) | Opus 5.5, high effort | Review needs the most judgement about how things break |
| latency | Opus 5.5, high effort | Threads, the cost guard and a live migration on the critical path |
| data | Opus 5.5, high effort | Auth, RLS and GDPR deletion: security mistakes are costly |
| seo | Sonnet 5.5 (Opus 5.5 for the prerender step if it struggles) | Mostly well-specified metadata and config |
| ui | Sonnet 5.5 | Well-specified frontend work in many files |
| media | Sonnet 5.5 | A bounded pipeline with clear rules and tests |

Opus uses up a plan's limits faster; if a limit is hit, latency and data keep Opus first.

## Blockers

- Node 22 LTS: installed 2026-10-30 in `~/.local/share/node22` (pnpm 11.5.0 through corepack);
  Vedant adds `export PATH="$HOME/.local/share/node22/bin:$PATH"` to the end of `~/.zshrc`.
- Python 3.12 is not on this Mac (only 3.10 and Anaconda's 3.10); the worktrees need it.
- Vedant's setup tasks for the agents (listed in each brief's "Needs from Vedant").

## Files touched

- `docs/handoff/main.md` (this file), `docs/handoff/data.md`, `docs/handoff/ui.md`,
  `docs/handoff/seo.md`, `docs/handoff/media.md`, the last section of `docs/handoff/latency.md`,
  `docs/SESSIONS.md`.
