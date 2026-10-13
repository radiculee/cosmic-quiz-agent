# CLAUDE.md

Persistent context for Claude Code. Read this, then `docs/DESIGN.md` and `docs/PLAN.md`, at the start of every session.

---

## What this project is

**Cosmic Quiz Agent** (working name) by **Vedant Gaikwad**, a Dublin-based Data Analyst and Full-Stack
Developer. An autonomous astronomy and space AI agent, surfaced as a Learn / Quiz web game.

- **v1:** a Learn / Quiz web game on separate pages with real URLs. (Changed 2026-10-08 by Vedant; it was one Speedrun-style page.)
  - Home: a full-screen hero over a slideshow of Vedant's scenes, with the title, the tagline and a compact row of Learn, Quiz and "Try a new topic" (from the web); the rank, points and a trophy shelf in a card below the fold. (Changed 2026-10-10 by Vedant; inner pages show the observatory scene as a still.)
  - Learn: a searchable grid of bank topics. Each gives a plain-language explanation with cited sources, at its own URL.
  - Quiz: runs of 10, 30 or 60 four-option MCQs, each on a different topic, against the clock. After each answer, the game shows the explanation and cited sources.
  - The web page (`/explore`): a typed topic researched live by the agent, behind guardrails. It also opens "Mission Control", the agent's measured statistics by mode and difficulty (Session 9).
  - Tiered bronze, silver and gold trophies that pop up when earned.
- **v2:** an astronomy newsletter (email via Resend, then WhatsApp) produced by the same agent. (The analytics page moved from v2 into v1 on 2026-10-08.)

It is a standalone project with its own repo, hosted on Vercel and served at `cosmic.vedantgaikwad.ie`, a
subdomain of Vedant's existing domain. The repo goes public with an MIT licence in Session 10, after a
security audit. (Changed 2026-10-08 by Vedant; it was "its own repo and domain".) It is **not** part of the
portfolio repo (`Modernpersonalportfoliowebsite`, a separate folder), which is used only as a reference for
patterns and design tokens. Recruiters will read this code, so code quality is part of the deliverable.

The full decision record, repo layout, milestones and verification plan live in `docs/DESIGN.md`. Do not
reopen a locked decision without flagging it to Vedant first.

---

## Architecture in one paragraph

A daily **Curator** agent runs in GitHub Actions as a plain Python script (`python -m curator`). It scans
free astronomy sources, researches topics, writes MCQs at three difficulties, verifies each against the
sources it fetched, and publishes passing items to a Supabase Postgres question bank. The Vite + React UI on
Vercel serves from that bank. A typed custom topic runs the same Python agent core on demand through a
Vercel Python function (`api/research.py`), behind guardrails, with steps streamed to the UI.

---

## Stack

- **Agent core:** Python, a hand-rolled tool-calling loop (`run_agent` in `agent/loop.py`, about 120 lines) behind a small provider interface in `agent/llm.py`. The current implementation uses the `anthropic` SDK, with Pydantic for every model output. No agent frameworks (no LangChain, LangGraph or PydanticAI).
- **Models:** `claude-haiku-4-5` for every step (research, writing, verifying). The model is config, never hard-coded in logic. An OpenRouter implementation can be added later behind the same interface. (Changed 2026-10-01, see `docs/PLAN.md`.)
- **Second-opinion verifier:** TypeSafe Jev via `typesafe-sdk`. It answers typed questions with a confidence (supports / contradicts / says nothing) and never writes text. It cannot check numbers reliably, so numbers are checked in code. (Added 2026-10-01, see `docs/SPIKE.md`.)
- **Python tooling:** Python 3.12 virtualenv, pip with a pinned `requirements.txt`, and `ruff` plus `mypy --strict` as dev-only tools.
- **Frontend:** Vite + React + TypeScript (strict) + Tailwind CSS, with pnpm.
- **Serverless:** Vercel Hobby. Python functions for the agent, and TS or Python functions for reading the bank.
- **Database:** Supabase free-tier Postgres.
- **Scheduler:** a GitHub Actions cron plus `workflow_dispatch` (`.github/workflows/curator.yml`).
- **CI:** `.github/workflows/checks.yml` runs every check on each push and pull request, with no secrets and no paid calls (added 2026-10-13). pnpm is pinned by `packageManager` in `package.json`, which CI and Vercel both read.
- **No Docker.** Vedant explicitly ruled it out.

---

## Hard rules

1. **Capped running cost.** Anthropic API usage is capped at $10 a month by a Console spend limit. TypeSafe (Jev, the second-opinion verifier) runs on a prepaid balance (EUR 5 for evals at 2026-10-01) at $0.042 per million input tokens. Every other service stays on a free tier, and there is no other paid item: the site uses a subdomain of vedantgaikwad.ie, which Vedant already owns. Log tokens and cost for every model run. Before adding any service, dependency or API, state its free tier or price. (Changed 2026-10-01; changed 2026-10-08 by Vedant, when a new domain stopped being a cost. See `docs/PLAN.md`.)
2. **Citation rule.** A source may only be a URL actually fetched during that run. This is enforced in code (`agent/verify.py`), never trusted to the prompt. Drop any other URL.
3. **Publish gate.**
   - A separate verifier pass must quote a source passage that supports the correct answer and confirm each distractor is wrong.
   - Pass: `published`. Borderline: `review`. Fail: discard and log.
4. **Guardrails on on-demand runs:** an on-topic check, a per-IP limit (salted-hash IPs only, for GDPR), a daily global cap in runs and dollars that stays under the $10 limit, and fallback to the bank.
5. **Secrets** live only in env vars (Vercel, GitHub Actions secrets, a local `.env` that is never committed). The Supabase secret key (`SUPABASE_SECRET_KEY`, the new name for the service-role key) never reaches the browser; only the publishable key may.

---

## Working protocol

- **One session at a time** (see `docs/PLAN.md`). Build, let Vedant verify, then move on.
- **Build local first.** Session 1 is a spike that proves the search, fetch and cite loop on Haiku 4.5 and measures cost per run. Vercel and GitHub Actions come in Session 7.
- **Explain before large changes.** If a change touches several modules or shared state, describe what and why first.
- **Vedant often wants a plan-only session first.** Plan before big changes.

---

## Conventions (apply always)

- **No emojis** anywhere in code, comments, commit messages or console output.
- **Complete, production-ready files.** No placeholders or stripped-down versions.
- **TypeScript strict,** with no `any` unless unavoidable and commented. **Python fully type-hinted,** with Pydantic models at every boundary.
- **Commits:** small and focused with clear messages and honest `Co-Authored-By` trailers. Commit only when Vedant asks.
- **Package managers:** always pnpm for Node (never npm or yarn). A Python virtualenv, with dependencies pinned in `requirements.txt` and kept light, because of the Vercel Python bundle size limit.

---

## Design tokens (shared with the portfolio)

```
--bg-void        #05050A   the analytics panel, inputs and tiles (the page shows a scene)
--surface        #0D1117   cards, panels
--accent-teal    #4ECDC4   primary accent (replaces the lime in the Speedrun mock)
--accent-rust    #C1440E   secondary accent
--accent-gold    #F5E6C8   star highlights, sparing use
--muted-lavender #7B6B8A   midtones
--text-primary   #F0EDE8   near-white, warm
--text-secondary #8B9BAA   slate grey body (inside cards only, never on a scene)
--sky-top        #021A3D   the page top above a scene on tall screens
--sky-edge       #033770   the scenes' top edge, where the sky gradient meets the image
```

Scenes (2026-10-10, `docs/PLAN.md` "Scenes"): the page background is Vedant's AI-generated
scenes (`public/scenes/`, not covered by the MIT licence). Cards and controls on a scene are
solid `--surface`; text straight on a scene is ink with a soft shadow (`on-scene`,
`on-scene-muted`), and small lines below a page's intro sit on solid chips (`scene-note`).

Fonts (from Google Fonts, served from the site itself in `public/fonts/` under the SIL Open Font
License, so no visit reaches Google; changed 2026-10-10):
- Headings: **Space Grotesk** Bold.
- Body: **Inter** Regular / Medium.
- Pixel accents ONLY: **Press Start 2P** at 8-11px, for segmented-control labels, tags and small labels. Never for body text or headings.

Pixel accents are subtle texture: pixel-dashed borders (4px on / 4px off), 4x4px square bullets. No sprites or scanlines.

---

## Reference code (portfolio repo, copy patterns only)

- `Modernpersonalportfoliowebsite/api/contact.ts`: Vercel function style (web-standard Request/Response), env-secret handling, the Resend REST call and the branded dark HTML email template. Reuse it for v2.
