# Handoff: main (coordinator)

Notes for the main session (`docs/SESSIONS.md`), which plans, writes the other sessions' briefs
and reviews their branches. It edits no code: only `docs/SESSIONS.md` and `docs/handoff/*.md`
(and `docs/DESIGN.md` and `CLAUDE.md` when Vedant approves the exact text).

Last update: 2026-10-30, 02:00 Dublin. The session ended on the Mac; Vedant continues on the
Windows machine, which has the API keys.

## Read first (a new main session)

1. `CLAUDE.md`, then this file.
2. `docs/SESSIONS.md`: the rows, "The pre-launch overhaul (2026-10-30)" ownership, and the
   2026-10-30 entry under Decisions (all 22 grill-me decisions).
3. The five briefs: `docs/handoff/latency.md` (its last section, "Pre-launch overhaul
   additions"), `data.md`, `ui.md`, `seo.md`, `media.md`.

First message for a new main session on Windows:

> Read CLAUDE.md and docs/handoff/main.md, then docs/SESSIONS.md and the five briefs it lists. You
> are the "main" session: the coordinator and reviewer for the pre-launch overhaul. You write
> prompts and review branches; you do not edit code. Tell me where things stand and what is next.

## How Vedant wants main to work

- Main is the prompt engineer and reviewer. It edits no code; specialist sessions write it.
- When Vedant is listing changes, wait for the whole list before asking anything. Then ask one
  question at a time, each with a recommendation first and honest pushback grounded in the code.
  He wants better suggestions, not agreement.
- Commit only when he asks; stage by path; never push without his word.
- The repo is public: commits are authored "vedant gaikwad <vedantgaikwad01@gmail.com>", matching
  the history.

## Current goal

The pre-launch overhaul, settled in a grill-me session on 2026-10-30. The site becomes
**Curiosity** at `curiosity.vedantgaikwad.ie`, with optional accounts, parallel search with
progress rows, image topic cards, a sticky header with card buttons, prerendered SEO pages,
typo redirects and rover ranks. Everything ships before the launch on Tuesday 3 November.

- **Code freeze: Monday 2 November 18:00 Dublin**, then the deploy and a live check that evening.
- **Cut order if late:** (1) accounts, (2) prerendering, (3) image cards.
- **Must ship:** November's budget, parallel search, the rename and metadata, the header and card
  buttons.
- **Open until Monday:** the title tag. Vedant's direction is "Curiosity: Quiz on the wonders of
  our world beyond earth", or something better; candidates are in `docs/handoff/seo.md`. It is one
  line in `src/brand.ts`.

## Where things stand (2026-10-30, 02:00)

- **On `main`, not pushed yet** (pushed only if Vedant says so before leaving the Mac):
  - `659ae30` Brief five parallel sessions for the pre-launch overhaul
  - `c69bac2` Record the rename to Curiosity and optional accounts (`CLAUDE.md`, `docs/DESIGN.md`,
    Vedant's approved text)
  - the commit with this file
- **No code has been written** for the overhaul. No session has started work.
- **The Mac** has worktrees `~/cqa-{latency,data,ui,seo,media}` on `session/<name>` at `c69bac2`,
  each with a Python 3.12 `.venv` and `node_modules`, and an empty `.env` (template only). They
  are Mac-only and hold no work; leave them, or remove them later with
  `git worktree remove ~/cqa-<name>` and `git branch -d session/<name>`. Any Claude sessions still
  running in the Mac's main folder should be quit.

## Continuing on Windows

1. **Get `main`.** In `C:\Users\vedan\cosmic-quiz-agent`: `git pull --ff-only`. If the Mac's
   commits were not pushed, push them from the Mac first; otherwise the briefs are not on Windows.
2. **latency already has a worktree** on Windows (`C:\Users\vedan\cqa-latency`, branch
   `session/latency`, from 2026-10-28, its work already on `main`). Do not run the script for it.
   In that folder: `git status` (it must be clean), then `git rebase main`. Its handoff then
   includes the new section.
3. **The other four**, from the main folder in PowerShell:
   ```powershell
   foreach ($n in "data","ui","seo","media") { dev\new-session.ps1 $n }
   ```
   The script copies the Windows `.env` (with the keys) into each worktree. Then in each folder:
   `python -m venv .venv`, `.venv\Scripts\activate`, `pip install -r requirements-dev.txt`,
   `pnpm install`. Node must be 20.19 or newer, or 22.12 or newer (Vite 8); `node --version` to check.
4. **Start the sessions**, each in its own terminal inside its worktree: `claude`, then `/model`
   (table below), then this first message with the name filled in:
   > Read CLAUDE.md, docs/SESSIONS.md and docs/handoff/<name>.md, then docs/DESIGN.md and
   > docs/PLAN.md. You are the "<name>" session, in the worktree ../cqa-<name> on branch
   > session/<name>. Your brief is in your handoff. Follow "Parallel sessions" in CLAUDE.md and
   > edit only the files your session owns. Tell me your plan before changing code.
5. **Start seo first.** Its `src/brand.ts` pass (the name in one place) merges before ui edits
   the same files. Until then, ui builds only its two throwaway card prototypes.

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

## Timeline

- **Fri 30 Oct:** sessions start (Windows). seo begins with `src/brand.ts`.
- **Sat 31 Oct:** seo's brand pass merges first; ui rebases onto it. latency ships November's
  budget (deployed by Saturday), then parallel search. data: migration 011 and auth. ui: header,
  card buttons, two card prototypes for Vedant to pick from. media: the image pipeline and 012.
  seo: metadata, robots.txt, redirects, the 404 close-match.
- **Sun 1 Nov:** parallel search go/no-go. The fills run on November's budget (30 likely topics,
  about $5; images, free). ui: progress rows, the chosen card, rover ranks. seo: prerendering.
  latency: per-account limits once data's auth is on `main`.
- **Mon 2 Nov:** Vedant picks the title tag. Merges in review order: latency, seo, media, ui,
  data. Freeze at 18:00. Deploy, DNS switch, live check.

## Review protocol

1. A session tells Vedant a piece is ready: rebased onto `main`, every check green, its handoff
   updated.
2. Vedant asks main to review. Main reads `git diff main...session/<name>` and the handoff, and
   checks the piece against its brief, the hard rules in `CLAUDE.md` and the ownership table.
   Findings go back through Vedant as a numbered list; nothing merges with an open finding.
3. Vedant lands it from the main folder: `git merge --ff-only session/<name>`. Every other session
   then rebases onto `main`.

## Vedant's setup tasks (all free; each brief's "Needs from Vedant" has the detail)

- [ ] Google Cloud OAuth client (web), with Supabase's callback as the redirect URL (data).
- [ ] Supabase: enable Google and email providers; custom SMTP with Resend; site URL
      `https://curiosity.vedantgaikwad.ie` and redirect URLs for localhost and previews (data).
- [ ] Resend account, with SPF and DKIM records on vedantgaikwad.ie (data).
- [ ] DNS CNAMEs for `curiosity.` and the aliases `quiz.`, `astro.`, `cosmik.`, `curiousity.`,
      `curiosty.`, `cosmicquiz.`, each added to the Vercel project; `cosmic.` stays and redirects (seo).
- [ ] A Vercel deploy hook, saved as the GitHub Actions secret `VERCEL_DEPLOY_HOOK_URL` (latency).
- [ ] `public/og-v2.jpg`, 1200 x 630, CURIOSITY over one of the scenes (seo).
- [ ] Approve new dependencies when asked: `@supabase/supabase-js` (data), Pillow for the Curator
      only (media), any prerender dev dependency (seo).
- [ ] Paste migrations 010, 011, 012 in that order when each is ready.
- [ ] Check the Anthropic rate-limit tier before the go/no-go; raise the Console limit to $27
      before 3 November and back to $10 on 1 December (already planned).
- [ ] The title tag, on Monday.
- [ ] After launch: Google Search Console and Bing Webmaster Tools; submit the sitemap.

## Verification for the whole overhaul

- Each branch: every check in `.github/workflows/checks.yml` (`pnpm lint typecheck test build`,
  `ruff`, `mypy --strict`, `pytest`) plus its brief's own tests.
- A headless drive against the stub API (one session at a time runs the dev servers on 5173
  and 8787).
- 2 real local searches (about $0.17 each, asked for one by one): 25 to 40 s for the whole
  search, the first question in about 17 s.
- Accounts: the two-browser merge, RLS refusing another user's rows, delete removing everything,
  and the site unchanged with the flag off.
- Live: `curl -I` on `cosmic.` and each alias returns 301 to `curiosity.`; `curl` on
  `/learn/antimatter` shows its text, title and JSON-LD; Rich Results Test passes; no CSP
  violations; a pasted link shows the right preview.

## Edits applied to Vedant's files (2026-10-30, `c69bac2`)

Approved by Vedant. `CLAUDE.md`: the name Curiosity, the new domain, optional sign-in under v1,
the free tiers for Resend, Supabase Auth and Storage under hard rule 1, and session tokens and
RLS under hard rule 5. `docs/DESIGN.md`: the rename and domain in Context and Repo layout,
decision 15 (the overhaul), and "Player state" changed to optional accounts.

## Done

- 2026-10-30: the grill-me session (22 decisions); the five briefs; `docs/SESSIONS.md` rows,
  ownership and decisions; the approved `CLAUDE.md` and `docs/DESIGN.md` edits. On the Mac only:
  Node 22.23.4 in `~/.local/share/node22`, Python 3.12 through uv, the five worktrees.

## Next

- Vedant: continue on Windows (above), start seo first, then the others.
- main: review each piece when Vedant says it is ready.

## Blockers

- None for starting. Setup tasks above gate data (OAuth, Resend), seo (DNS, og-v2.jpg) and
  latency's deploy hook.

## Files touched

- `docs/handoff/main.md` (this file), `docs/handoff/data.md`, `docs/handoff/ui.md`,
  `docs/handoff/seo.md`, `docs/handoff/media.md`, the last section of `docs/handoff/latency.md`,
  `docs/SESSIONS.md`, `CLAUDE.md`, `docs/DESIGN.md`.
