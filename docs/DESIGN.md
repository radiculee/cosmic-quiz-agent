# Cosmic Quiz Agent - design plan

## Context
Vedant wants an autonomous AI agent themed on astronomy and space. v1 is a Learn/Quiz web game; v2 adds an
astronomy newsletter (email, then WhatsApp) produced by the same agent. It started as a portfolio feature but
is now a **standalone project**: new repo, own domain, hosted on Vercel. The portfolio repo is not changed
(at most a Projects link later). Aim: zero running cost, a real agent (the model chooses tools in a loop and
runs on a schedule with no human trigger), and code that reads well to recruiters.

## Decisions (grill-me session, 2026-09-30)
1. **Audience:** Vedant first, public later. Build for one user; keep the data model public-ready (opt-in, unsubscribe, GDPR).
2. **Domain:** astronomy and space only.
3. **Models:** Claude Code builds it. At runtime, OpenRouter free-tier open-weights models (OpenAI-compatible; the model is config).
4. **UI:** modelled on the "Wikipedia Speedrun" screenshot, restyled with the portfolio tokens (void background, surface panels, teal accent, Space Grotesk headings, Press Start 2P only for small segmented-control labels). Controls: `[EASY|MEDIUM|HARD]`, `[LEARN|QUIZ]`, a topic input, `[Random topic]`, `[GO]`.
5. **Modes:**
   - LEARN: a plain-language explanation plus cited sources.
   - QUIZ: one 4-option MCQ per GO. After answering (right or wrong), show the explanation plus cited sources.
6. **Citation rule:** a source may only be a URL fetched in that run, enforced in code. Any other URL is dropped.
7. **Architecture:**
   - The daily **Curator** scans sources, picks notable topics, researches them, writes MCQs at each difficulty, verifies them, publishes to the bank, and retires stale items.
   - The UI serves questions from the bank.
   - A typed custom topic runs the same agent core on demand.
   - v2 newsletter: the same Curator with an email output.
8. **Runtime:**
   - GitHub Actions cron runs the Curator as a plain Python script (no Docker).
   - Supabase free Postgres stores the bank. Daily writes stop the free tier from pausing.
   - Vercel Hobby hosts the UI and `/api`.
   - The only cost is the domain.
9. **On-demand guardrails:**
   - A cheap on-topic check.
   - A per-IP limit of about 5 runs a day (IP stored as a salted hash, for GDPR).
   - A global cap equal to the free-model quota. When it's exhausted, serve from the bank.
   - Verified results are cached into the bank.
   - The UI streams live agent steps.
10. **Evidence tools:**
    - `search_wikipedia`, `search_arxiv` (astro-ph), `nasa_image_library` / APOD (free NASA key), and `fetch_feed` (NASA, ESA, JWST, Hubble RSS).
    - `fetch_page`, limited to an allow-list of domains.
    - A free-tier `web_search` fallback. The agent stops using it when the monthly cap is hit.
11. **Stack:**
    - A Python agent core package, shared by `curator` (run with `python -m curator` in Actions) and `api/research.py` (Vercel Python function).
    - Vite + React + TypeScript + Tailwind UI, with pnpm.
12. **Agent loop:**
    - Hand-rolled, about 150 lines, using the `openai` SDK pointed at OpenRouter.
    - Tools are plain functions with JSON schemas, and there's a hard step budget.
    - Pydantic models validate every output: `QuizItem`, `Explanation`, `Citation`.
13. **Difficulty (depth plus distractors):**
    - EASY: well-known facts, clearly wrong distractors, sources are Wikipedia and NASA.
    - MEDIUM: mechanisms and "why", plausible distractors.
    - HARD: numbers and recent findings, distractors built from common misconceptions, arXiv and JWST sources, one technical term defined.
14. **Publish gate:**
    - A separate verifier pass (a different free model where possible) must quote a source passage that supports the correct answer, confirm each distractor is wrong, and confirm the citations were fetched.
    - Pass: auto-publish. Borderline: `review` status. Fail: discard and log.
    - A Report button on each question; 2 reports hide it.

## Defaults chosen without asking (change if wanted)
- **Review queue:** Vedant approves borderline items by changing `status` in the Supabase table editor. No admin UI in v1.
- **Player state:** no accounts. Streak and score are kept in `localStorage`.
- **Model selection:** a small eval set (about 20 fixed topics) scored on tool-call success, citation pass rate and verifier agreement. It runs before picking the default free models and again whenever a model is swapped.
- **Secrets:** `OPENROUTER_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (Actions and server only), `SUPABASE_ANON_KEY` (read-only, row-level security), `NASA_API_KEY`, `SEARCH_API_KEY`, `IP_HASH_SALT`.

## Proposed repo layout (new repo; name and domain are Vedant's choice)
```
agent/                 Python package (shared core)
  llm.py               OpenRouter client, model config
  loop.py              tool-calling loop with step budget
  tools/               wikipedia.py arxiv.py nasa.py feeds.py fetch.py search.py
  schemas.py           Pydantic: QuizItem, Explanation, Citation, Run
  verify.py            citation check + verifier-model pass
  prompts/             per-difficulty prompt templates
  store.py             Supabase REST writes/reads
curator/__main__.py    daily job: discover -> research -> draft -> verify -> publish -> retire
api/research.py        Vercel Python fn: guarded on-demand run, streams steps
api/quiz.ts|py         serve random/filtered item from bank; report endpoint
evals/                 fixed topic set + scoring script
src/                   Vite + React UI (Speedrun-style layout)
supabase/schema.sql    items, sources, runs, reports, rate_limits (+ subscribers in v2)
.github/workflows/curator.yml   daily cron + manual dispatch
```

## Milestones (one at a time, verified before moving on)
1. **Spike (de-risk):** check that Vercel Python functions can stream and fit within the Hobby max duration. Check which OpenRouter free models do tool calling reliably. If Python streaming fails, the fallback is: POST creates a `run` row, the function writes steps to Supabase, and the UI polls.
2. **Agent core plus evals:** tools, loop, schemas and verifier, run locally from the CLI against the eval set.
3. **Curator plus bank:** `schema.sql`, the store, and the GitHub Actions cron. The bank fills daily.
4. **UI:** the Speedrun layout; LEARN and QUIZ from the bank; Random topic; difficulty; the Report button.
5. **On-demand custom topics:** guardrails, streaming steps, caching into the bank.
6. **Launch:** domain, OG image, README with an architecture diagram (a recruiter-facing deliverable).
7. **v2:** newsletter output from the Curator via Resend (reuse the portfolio's `api/contact.ts` email pattern), subscribers table with double opt-in and unsubscribe; WhatsApp after that.

## Reference code in the portfolio repo (copy patterns, don't share)
- `api/contact.ts`: Vercel function style, env-secret handling, Resend REST call, the branded HTML email template (reuse for v2).
- Design tokens and font rules: the portfolio's `CLAUDE.md`.

## Immediate step: handoff to a new VS Code window
Create `c:\Users\vedan\cosmic-quiz-agent\` with no app code:
- `CLAUDE.md`: project identity, stack, commands, conventions carried over from the portfolio (no emojis, complete files, strict typing, one milestone at a time, explain before large changes, small commits), design tokens and font rules, citation rule, zero-cost rule.
- `docs/DESIGN.md`: the full decision record, layout, milestones and verification (this plan).
- `docs/HANDOFF.md`: where things stand and the first prompt to paste into the new session (start Milestone 1 spike).
- `.gitignore` (Python + Node + .env), then `git init` on `main`. No commit unless Vedant asks.
Vedant then opens the folder in a new VS Code window and continues from `docs/HANDOFF.md`.

## Verification
- **Agent core:** `python -m evals` on the fixed topics. Targets: at least 90% of published items pass the citation check, 0 unfetched URLs, and every item validates against its schema.
- **Curator:** trigger the workflow manually (`workflow_dispatch`), confirm new `published` rows in Supabase and a `runs` row with step logs, and confirm that failed or borderline items land in the right status.
- **UI:** run `pnpm dev` locally. Play each mode and difficulty, check that sources open and appear in that item's fetched set, and that Report hides an item after 2 reports.
- **On-demand:** run a valid topic (steps stream, result is cached, the second request is instant), an off-topic query (rejected), and a 6th request from the same IP (falls back to the bank).
- **Cost check:** confirm the OpenRouter dashboard shows $0 and all services are on free tiers.
