# Handoff

> **Superseded on 2026-10-01.** This was the starting point for the first session in this repo. The plan
> has since changed (Claude Haiku 4.5 instead of OpenRouter, local first, TypeSafe Jev as a second-opinion
> verifier). The current plan is `docs/PLAN.md`; Session 1 results are in `docs/SPIKE.md`. Kept for the record.

Session moved here from the portfolio repo on 2026-10-01.

## Where things stand
- **Design is finished.** A brainstorming session with Claude Code on 2026-09-30 locked 14 decisions, recorded in `docs/DESIGN.md`.
- **No app code exists yet.** The folder contains only `CLAUDE.md`, `docs/` and `.gitignore`.
- **The git repo is initialised on `main`,** with nothing committed yet.
- **The portfolio repo was not changed.**

## Before Milestone 1, Vedant needs (all free)
- An OpenRouter account and API key.
- A Supabase project (free tier). Needed from Milestone 3, not for the spike.
- A NASA API key from api.nasa.gov.
- A Vercel account (existing) and a GitHub repo for this project.
- Optional: a free-tier web search API key (for example Tavily or Brave). Confirm current free-tier terms first.
- The domain can wait until Milestone 6.

## First prompt for the new session
Paste this into Claude Code in the new VS Code window:

> Read CLAUDE.md and docs/DESIGN.md. We are starting Milestone 1, the spike. Plan first, no code yet:
> (1) how we test whether a Vercel Python function on the Hobby plan can stream agent steps and what its
> max duration is, and (2) how we test which OpenRouter free models reliably do tool calling for our
> search -> fetch -> cite loop. Check current Vercel and OpenRouter docs rather than relying on memory.

## Open items to confirm during the spike
- Current Vercel Hobby limits for Python function max duration and streaming support.
- Current OpenRouter free-model rate limits and which models support tool calling.
- If Python streaming fails, use the fallback in `docs/DESIGN.md` (runs table plus polling).
