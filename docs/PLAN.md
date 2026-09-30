# Build plan

Working plan for building Cosmic Quiz Agent, split into sessions. Each session has a goal, what Vedant
prepares beforehand, what Claude Code does, the decisions Claude Code must ask about rather than make, and a
verification gate Vedant signs off before the next session starts.

Read at the start of every session together with `CLAUDE.md` and `docs/DESIGN.md`. At the end of every
session, tick the finished tasks and add a line to the session log at the bottom.

---

## Direction change (2026-10-01)

Vedant decided on 2026-10-01 to build with the Anthropic API first, for personal use, and to host in the
cloud afterwards. This changes locked decisions in `docs/DESIGN.md`:

| Topic | Was | Now |
|---|---|---|
| Runtime model (decision 3) | OpenRouter free open-weights models via the `openai` SDK | `claude-haiku-4-5` for every step (research, writing, verifying), via the `anthropic` SDK |
| Provider coupling | OpenAI-compatible client | A small LLM interface in `agent/llm.py` with one Anthropic implementation. An OpenRouter implementation can be added later without touching the loop |
| Cost rule (hard rule 1) | Zero running cost; domain is the only paid item | Anthropic API usage, capped at **$10 / month** by a Console spend limit. Every other service stays on a free tier |
| Build order | Vercel streaming spike first | Local first: the agent, Curator and UI run on Vedant's machine against the free Supabase project. Vercel, GitHub Actions and the domain come after |
| Verifier model | A different free model where possible | Also Haiku 4.5, run as a separate pass with its own prompt. The code-enforced citation check is unchanged and does not depend on the model |

Session 1 records this in `DESIGN.md` and `CLAUDE.md` once Vedant approves the wording.

### What Haiku 4.5 means for the code
- Price: $1 per million input tokens, $5 per million output tokens. 200K context, 64K max output.
- Supports tool use, strict tool schemas and structured outputs, so Pydantic models can be enforced at the API
  boundary as well as in our own validation.
- Prompt caching only applies to prefixes of at least 4,096 tokens on Haiku 4.5. Our system prompt plus tool
  definitions may be shorter than that, in which case caching silently does nothing. Session 1 measures this.
- It has no `effort` setting. Thinking, if used, is set with a fixed `budget_tokens`.

### Rough cost estimate (to be replaced by measured numbers in Session 1)
Assumes about 8 model calls per research run, fetched pages trimmed to about 3,000 tokens each, and context
growing across the loop.

| Unit | Estimated cost |
|---|---|
| One research run (LEARN, or one QUIZ item) | about $0.05 to $0.10 |
| One verifier pass | about $0.01 |
| One Curator topic (research once, 3 difficulties, 3 verifications) | about $0.10 to $0.15 |
| 20-topic eval run | about $2 to $3 |

At $10 a month this allows roughly one or two Curator topics a day plus development and a couple of eval runs.
The Curator's daily volume is therefore a decision for Vedant (Session 4).

---

## Standing rules for every session
- Plan and explain before any change that touches several modules. Ask before adding a dependency, a
  service or anything that costs money, and state its free tier or price.
- Ask, don't assume, on anything listed under "Decisions to ask". Give a recommendation with each question.
- Complete files only, no placeholders. Python fully type-hinted; TypeScript strict. No emojis.
- Never commit unless Vedant asks. Suggest a commit point at the end of each session.
- Log token usage and cost for every model run, so spending stays visible against the $10 cap.

---

## Session 0 - Plan (this session)
**Goal:** agree the plan and the direction change.

Claude Code:
- [x] Read `CLAUDE.md`, `docs/DESIGN.md`, `docs/HANDOFF.md`.
- [x] Check current Vercel and OpenRouter limits (findings kept for the cloud phase, Session 7).
- [x] Write this plan.

Vedant:
- [ ] Review this plan and correct anything that's wrong.
- [ ] Create an Anthropic Console account, create an API key, and set a **$10 monthly spend limit**.
- [ ] Decide whether to make the first commit (CLAUDE.md, docs, .gitignore) now.

---

## Session 1 - Skeleton and Claude tool-calling spike
**Goal:** prove the search -> fetch -> cite loop works on Haiku 4.5 and measure the real cost per run.

Vedant prepares:
- `ANTHROPIC_API_KEY` in a local `.env` (never committed).

Decisions to ask:
- Python version: 3.12 (Vercel's default, so local matches the cloud) or 3.14 (currently installed).
- Dependency tooling: plain `venv` + `pip` with pinned `requirements.txt`, or `uv`.
- Lint and type checking: `ruff` + `mypy --strict`, or something else.
- Wording of the `DESIGN.md` / `CLAUDE.md` updates for the direction change.

Claude Code:
- [ ] Update `DESIGN.md` and `CLAUDE.md` with the approved direction change.
- [ ] Python project skeleton: `agent/` package, pinned dependencies (`anthropic`, `pydantic`, `httpx`,
      `python-dotenv`), lint and type config, `.env.example`.
- [ ] `agent/llm.py`: the provider interface and the Anthropic implementation. Model name from config.
- [ ] Minimal loop with three tools: `search_wikipedia`, `fetch_page` (allow-listed domains), and
      `submit_answer` (Pydantic-validated explanation with citations).
- [ ] Citation check in code: drop any cited URL that was not fetched in the run.
- [ ] Step budget and wall-clock budget in the loop.
- [ ] Run 3 topics, record tokens, cost, steps, wall time and citation pass/fail in `docs/SPIKE.md`.
- [ ] Measure whether prompt caching takes effect (the 4,096-token minimum).

Gate (Vedant): runs the spike command himself, reads the three outputs, and checks that the Console spend
matches the numbers in `docs/SPIKE.md`.

---

## Session 2 - Agent core
**Goal:** the full toolset and a reliable loop, run from the command line.

Decisions to ask:
- The domain allow-list for `fetch_page` (a proposed list is shown for approval).
- Web search fallback: leave it out, use a free-tier search API (terms checked first), or Anthropic's server-side
  web search (paid per search). Recommendation given with prices.
- Tone and length of LEARN explanations (a sample is shown for approval).

Vedant prepares:
- A NASA API key from api.nasa.gov, added to `.env`.

Claude Code:
- [ ] Tools: `wikipedia.py`, `arxiv.py` (astro-ph), `nasa.py` (APOD and image library), `feeds.py` (NASA, ESA,
      JWST, Hubble RSS), `fetch.py` (allow-listed, text-extracted, size-capped).
- [ ] `schemas.py`: `Citation`, `Explanation`, `QuizItem`, `Run`.
- [ ] Loop hardening: tool errors returned to the model, retries on 429/5xx, token budget per run.
- [ ] CLI: `python -m agent learn "<topic>" --difficulty easy|medium|hard`.
- [ ] Unit tests for the citation check and the tools (network mocked).

Gate (Vedant): runs LEARN on 3 topics of his choice and judges whether the explanations and sources are good.

---

## Session 3 - Quiz items, verifier and evals
**Goal:** MCQs at three difficulties that pass a verifier, measured on a fixed eval set.

Decisions to ask:
- Approve the 20 eval topics (a proposed list is shown; Vedant can swap any).
- Hand-review about 10 generated questions; Vedant's judgement sets the quality bar.
- The pass / borderline / fail thresholds for the verifier.
- Approve the eval run cost before running it (estimate shown first).

Claude Code:
- [ ] Per-difficulty prompt templates in `agent/prompts/`.
- [ ] `verify.py`: the verifier pass (quotes a supporting passage, checks every distractor is wrong) plus the
      code-enforced citation check.
- [ ] `evals/`: the fixed topics, a scoring script, results written to `evals/results/` (not committed).
- [ ] CLI: `python -m agent quiz "<topic>" --difficulty ...` and `python -m evals`.

Gate (Vedant): the eval report meets the DESIGN.md targets (at least 90% citation pass, 0 unfetched URLs,
every item schema-valid), and the hand-reviewed questions are acceptable.

---

## Session 4 - Supabase bank and Curator (run locally)
**Goal:** the Curator fills the bank when run by hand on Vedant's machine.

Vedant prepares:
- A free Supabase project. Add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_ANON_KEY` to `.env`.

Decisions to ask:
- Daily Curator volume (topics per day), given the measured cost per topic and the $10 cap.
- Retirement rule for stale items (age, or a total item cap).
- Who runs `schema.sql`: Vedant pastes it into the Supabase SQL editor, or Claude Code runs it via the
  Supabase CLI (an extra dependency).

Claude Code:
- [ ] `supabase/schema.sql`: `items`, `sources`, `runs`, `reports`, `rate_limits`, with row-level security
      (the anon key can only read published items).
- [ ] `agent/store.py`: Supabase REST reads and writes.
- [ ] `curator/__main__.py`: discover -> research -> draft -> verify -> publish / review / discard -> retire,
      with a `runs` row and step log per run.

Gate (Vedant): runs `python -m curator`, sees `published` and `review` rows in the Supabase table editor,
approves one borderline item by changing its status.

---

## Session 5 - UI (local)
**Goal:** the Speedrun-style game, playable locally against the bank.

Vedant prepares:
- The "Wikipedia Speedrun" reference screenshot, shared in the session.

Decisions to ask:
- Local API shape: a small local Python server that mirrors the future Vercel functions, or TypeScript
  functions run through `vercel dev`. Recommendation given.
- Layout and copy review of a first screen before building the rest.
- How sources are shown after an answer (list, cards, inline footnotes).

Claude Code:
- [ ] Vite + React + TypeScript (strict) + Tailwind with pnpm, portfolio design tokens and fonts.
- [ ] Controls: `[EASY|MEDIUM|HARD]`, `[LEARN|QUIZ]`, topic input, `[Random topic]`, `[GO]`.
- [ ] QUIZ flow: answer, then explanation and sources. LEARN flow: explanation and sources.
- [ ] Report button (2 reports hide an item). Streak and score in `localStorage`.

Gate (Vedant): plays every mode and difficulty with `pnpm dev`, checks that sources open and belong to the item.

---

## Session 6 - Custom topics on demand (local)
**Goal:** a typed topic runs the agent live, with guardrails and streamed steps.

Decisions to ask:
- Per-IP daily limit and the global daily cap, in runs and in dollars.
- What the UI shows while steps stream, and what it shows when a run is rejected or capped.

Claude Code:
- [ ] On-topic check (a cheap Haiku call or a keyword filter, recommendation given).
- [ ] Per-IP limit with salted-hash IPs, global cap, fallback to the bank.
- [ ] Streamed agent steps to the UI; verified results cached into the bank.

Gate (Vedant): valid topic streams and caches; off-topic is rejected; the limit falls back to the bank.

---

## Session 7 - Move to the cloud
**Goal:** the app runs on Vercel, the Curator runs on GitHub Actions.

Vedant prepares:
- A GitHub repo for the project, a Vercel project linked to it, and the secrets entered in both.

Decisions to ask:
- Whether public on-demand runs stay on Claude (costs money per visitor) or switch to OpenRouter free models
  through the provider interface, or are disabled publicly.
- Curator schedule (time of day, frequency).

Claude Code:
- [ ] Run the Vercel streaming spike planned on 2026-10-01 (incremental delivery, 300 s cap, client
      disconnect, coexistence with Vite, cold start) and record results in `docs/SPIKE.md`.
- [ ] Deploy the UI and API; set `maxDuration`; the agent's own time budget stays under it.
- [ ] `.github/workflows/curator.yml`: daily cron plus `workflow_dispatch`.

Gate (Vedant): the production URL works; a manual workflow run adds rows to Supabase.

---

## Session 8 - Launch
Decisions to ask: the domain name, README tone, and what the OG image shows.

Claude Code:
- [ ] Domain setup, OG image, README with an architecture diagram for recruiters.

Gate (Vedant): the README reads well to someone who has never seen the project.

---

## Session 9 and later - v2 newsletter
Planned separately when v1 is live: Curator email output via Resend (portfolio `api/contact.ts` pattern),
subscribers with double opt-in and unsubscribe, then WhatsApp.

---

## Session log
- 2026-10-01 - Session 0: read the handoff, checked Vercel and OpenRouter docs, switched to Claude Haiku 4.5
  (swappable provider, $10/month cap, local-first with Supabase), wrote this plan.
