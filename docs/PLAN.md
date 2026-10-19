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
| Cost rule (hard rule 1) | Zero running cost; domain is the only paid item | Anthropic API usage, capped at **$10 / month** by a Console spend limit, plus a prepaid TypeSafe balance for Jev (added later the same day). Every other service stays on a free tier |
| Build order | Vercel streaming spike first | Local first: the agent, Curator and UI run on Vedant's machine against the free Supabase project. Vercel, GitHub Actions and the domain come after |
| Verifier model | A different free model where possible | Also Haiku 4.5, run as a separate pass with its own prompt. The code-enforced citation check is unchanged and does not depend on the model |
| Second opinion (added later on 2026-10-01) | None | TypeSafe Jev checks each claim against its quoted passage and returns supports / contradicts / says nothing with a confidence. Prepaid TypeSafe balance (EUR 5 for evals). Its confidence is stored and shown in the UI |

Session 1 recorded this in `DESIGN.md` and `CLAUDE.md`. The publish gate is now three layers (code checks,
Haiku verifier, Jev); see `DESIGN.md` decision 14.

### What Jev means for the code
- Jev answers typed questions only (`Choice`, `Score`, `Noul`) with probabilities and a confidence. It
  never writes text, so it cannot research, explain or write quiz questions; Haiku does all of that.
- Price: $0.042 per million input tokens, output free. A claim check is about 440 tokens, so about
  $0.00002. Measured latency 0.2 to 0.3 s. Limits: 64K tokens per request, 1,200 requests a minute.
- SDK: `typesafe-sdk` (pinned 0.7.2), built on the same `httpx2` as `anthropic`. Key: `TYPESAFE_API_KEY`.
- Pin `jev-1.13.0` rather than `jev-latest`, so thresholds and the confidence players see stay stable.
- Known weakness: it cannot check numbers reliably. In the Session 1 smoke test it accepted a wrong
  number at 0.86 confidence. Numbers are therefore checked in code (layer 1).

### What Haiku 4.5 means for the code
- Price: $1 per million input tokens, $5 per million output tokens. 200K context, 64K max output.
- Supports tool use, strict tool schemas and structured outputs, so Pydantic models can be enforced at the API
  boundary as well as in our own validation.
- Prompt caching only applies to prefixes of at least 4,096 tokens on Haiku 4.5. Our system prompt plus tool
  definitions may be shorter than that, in which case caching silently does nothing. Session 1 measures this.
- It has no `effort` setting. Thinking, if used, is set with a fixed `budget_tokens`.

### Cost per unit (measured in Session 1 where marked; the rest are estimates to confirm in Session 3)

| Unit | Anthropic (Haiku) | TypeSafe (Jev) |
|---|---|---|
| One LEARN research run | **$0.013 to $0.023, average $0.019 (measured)** | - |
| One Haiku verifier pass | about $0.005 to $0.01 | - |
| One Jev claim check | - | **about $0.00002 (measured, ~440 tokens)** |
| One Curator topic (research once, 3 difficulties, verify each) | about $0.05 to $0.08 | under $0.001 (about 30 claim and distractor checks) |
| 20-topic eval run, including the seeded-error set | about $1 to $2 | under $0.10 |

At $10 a month that is over 100 Curator topics plus development and several eval runs. The EUR 5 Jev
balance covers far more checks than the project will make in v1. The Curator's daily volume is still a
decision for Vedant (Session 4).

---

## Changes on 2026-10-08

Vedant played the deployed build and, in a grill-me session on 2026-10-08, changed these locked
decisions. Each is marked "Changed 2026-10-08 by Vedant" where it is recorded.

| Topic | Was | Now |
|---|---|---|
| UI (`DESIGN.md` decision 4) | One page: `[EASY\|MEDIUM\|HARD]`, `[LEARN\|QUIZ]`, a topic input, `[Random topic]`, `[GO]`; quiz runs of 10 with badges | Separate pages with real URLs: home, Learn (a topic grid), Quiz (runs of 10, 30 or 60), the web page for live research, and trophies. Tiered trophies replace the badges |
| Analytics page | v2, after launch | v1, Session 9 ("Analytics for nerds", opened from the web page) |
| Session order | Session 8 Launch, then v2 | Session 8 pages and trophies; Session 9 analytics; Session 10 security audit, public repo, domain and launch; then v2 (the newsletter) |
| Repo | Private | Public with an MIT licence in Session 10, after a security audit and a secret scan of the whole history |
| Domain (`CLAUDE.md` hard rule 1) | Its own domain, the one other paid item | `cosmic.vedantgaikwad.ie`, a subdomain of Vedant's existing domain, so there is nothing new to buy |
| Live research (`DESIGN.md` decision 9; second grill-me, later the same day) | One item per run; 3 runs a day per visitor, 10 a day for everyone | A search makes 4 items (the explanation and a question at each level); 2 searches a day per visitor, 4 a day for everyone; the dollar caps unchanged |

---

## Standing rules for every session
- Plan and explain before any change that touches several modules. Ask before adding a dependency, a
  service or anything that costs money, and state its free tier or price.
- Ask, don't assume, on anything listed under "Decisions to ask". Give a recommendation with each question.
- Complete files only, no placeholders. Python fully type-hinted; TypeScript strict. No emojis.
- Never commit unless Vedant asks. Suggest a commit point at the end of each session.
- Log token usage and cost for every model run, Haiku and Jev separately, so spending stays visible
  against the $10 Anthropic cap and the prepaid TypeSafe balance.

---

## Session 0 - Plan (this session)
**Goal:** agree the plan and the direction change.

Claude Code:
- [x] Read `CLAUDE.md`, `docs/DESIGN.md`, `docs/HANDOFF.md`.
- [x] Check current Vercel and OpenRouter limits (findings kept for the cloud phase, Session 7).
- [x] Write this plan.

Vedant:
- [ ] Review this plan and correct anything that's wrong.
- [x] Create an Anthropic Console account and an API key (in `.env`, working since Session 1).
- [x] Confirm the **$10 monthly spend limit** is set on the workspace. Done 2026-10-01: dedicated
      `cosmic-quiz-agent` workspace with a $10 limit and a new `local-dev` key; the old Default-workspace
      key was revoked. New key verified with one run ("The Moon", easy, passed, $0.0121).
- [x] Decide whether to make the first commit (CLAUDE.md, docs, .gitignore) now. Done: private repo
      `radiculee/cosmic-quiz-agent` created and `main` pushed on 2026-10-01.

---

## Session 1 - Skeleton and Claude tool-calling spike
**Goal:** prove the search -> fetch -> cite loop works on Haiku 4.5 and measure the real cost per run.

Vedant prepares:
- `ANTHROPIC_API_KEY` in a local `.env` (never committed). The empty `.env` was created in Session 1.

Decisions to ask:
- Python version: 3.12 (Vercel's default, so local matches the cloud) or 3.14 (currently installed).
- Dependency tooling: plain `venv` + `pip` with pinned `requirements.txt`, or `uv`.
- Lint and type checking: `ruff` + `mypy --strict`, or something else.
- Wording of the `DESIGN.md` / `CLAUDE.md` updates for the direction change.

Claude Code:
- [x] Update `DESIGN.md` and `CLAUDE.md` with the approved direction change. Decided: Python 3.12,
      venv + pip, ruff + mypy --strict, docs amended in place.
- [x] Python project skeleton: `agent/` package, pinned dependencies (`anthropic`, `pydantic`, `httpx2`,
      `python-dotenv`), lint and type config, `.env.example`. (`httpx2` instead of `httpx`: `anthropic` 1.x
      is built on it, so it is one dependency fewer.)
- [x] `agent/llm.py`: the provider interface and the Anthropic implementation. Model name from config.
- [x] Minimal loop with three tools: `search_wikipedia`, `fetch_page` (allow-listed domains), and
      `submit_answer` (Pydantic-validated explanation with citations).
- [x] Citation check in code: drop any cited URL that was not fetched in the run.
- [x] Step budget and wall-clock budget in the loop (plus an input-token budget).
- [x] Run 3 topics, record tokens, cost, steps, wall time and citation pass/fail in `docs/SPIKE.md`.
- [x] Measure whether prompt caching takes effect (the 4,096-token minimum).
- [x] Added after the spike: Jev smoke test on three spike claims (2 right, missed the numeric error);
      `typesafe-sdk` pinned; `TYPESAFE_API_KEY` in `.env`. Results in `docs/SPIKE.md`.

Gate (Vedant): runs the spike command himself, reads the three outputs, and checks that the Console spend
matches the numbers in `docs/SPIKE.md`.
- [x] Spike command run by Vedant: "Saturn's rings" (medium) passed, 3 model calls, $0.0125, 4 citations
      kept, 3 of 4 quotes verbatim.
- [ ] Console spend check: expected about $0.070 in total ($0.057 spike + $0.0125 gate run).

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
- [x] Tools: `wikipedia.py`, `arxiv.py` (astro-ph), `nasa.py` (APOD and image library), `feeds.py` (NASA, ESA,
      JWST, Hubble RSS), `fetch.py` (allow-listed, text-extracted, size-capped). Notes: the APOD API now
      returns placeholders, so APOD is read from its pages (today and older dates work; recent past dates
      cannot be looked up); webbtelescope.org and hubblesite.org no longer have feeds, so Webb and Hubble news
      comes from esawebb.org, esahubble.org and science.nasa.gov; science.nasa.gov's feed has an XML bug that
      is repaired before parsing; britannica.com returns 403 to the agent, so Vedant removed it from the allow-list. No NASA key is needed for now.
- [x] `schemas.py`: `Citation`, `Explanation`, `QuizItem`, plus `Step`, `RunResult` and `CitationCheck`
      (moved from `loop.py`). The stored `Run` row is designed with the Supabase schema in Session 4.
- [x] Loop hardening: tool errors returned to the model, retries on 429/5xx and network errors (shared
      `http_get`), token budget per run. Added: the word range is checked in code, with one correction.
- [x] CLI: `python -m agent learn "<topic>" --difficulty easy|medium|hard` (built in Session 1).
- [x] Unit tests for the citation check and the tools (network mocked): 77 tests with `pytest`, plus loop
      tests with a scripted fake model. No test touches the network or a paid API.

Decided 2026-10-01: allow-list = core agencies, research and observatories, and popular science sites
(lowest preference in the prompt); no web search fallback for now (revisit with Session 3 eval data);
LEARN length by difficulty (EASY 80-120, MEDIUM 120-180, HARD 160-220 words).

Gate (Vedant): runs LEARN on 3 topics of his choice and judges whether the explanations and sources are good.
- [x] Passed 2026-10-01. Vedant ran "Black holes" (hard: passed, 221 words, 5 of 5 quotes verbatim, used
      search_arxiv and fetch_feed, $0.0165) and "Quasar" (easy: passed, 116 words, 4 of 6 quotes verbatim,
      $0.0154) and approved the results. Britannica removed from the allow-list after it returned HTTP 403.
      Re-verified: ruff and mypy --strict clean, 77 tests pass, 14 of 15 live tool checks pass (the 15th is
      Britannica, now correctly rejected).

---

## Session 3 - Quiz items, three-layer verifier and evals
**Goal:** MCQs at three difficulties that pass the three-layer publish gate (code checks, Haiku verifier,
Jev second opinion), with each layer measured on a fixed eval set.

Vedant prepares:
- Confirm the TypeSafe balance (EUR 5) and the Anthropic spend limit before the first eval run.

Decisions to ask:
- Approve the 20 eval topics (a proposed list is shown; Vedant can swap any).
- Approve the seeded-error set: how many planted faults of each kind (wrong number, unsupported claim,
  quote not on the page, a distractor that is actually true). Recommendation: about 40 items, 10 of each.
- Hand-review about 10 generated questions; Vedant's judgement sets the quality bar. Jev's verdicts are
  shown alongside, so the hand review also checks whether Jev agrees with Vedant.
- How layers 2 and 3 combine. Options: both must pass to publish; Jev only escalates to `review`; or Jev
  alone decides claims and Haiku only checks distractors. Recommendation given after the eval results.
- Jev's confidence threshold for auto-accept (TypeSafe's cookbook starts at 0.8; the spike's wrong number
  scored 0.86, so the threshold alone is not enough).
- Approve the eval run cost before running it (estimate shown first, Haiku and Jev separately).

Decided 2026-10-01: the 20 proposed topics approved as listed (`evals/topics.py`); a full run is 20 topics
x 3 difficulties = 60 items, with a 5-topic `--quick` mode; the planted-error set is 40 items, 10 per
fault type, with code planting wrong numbers and broken quotes and Haiku planting unsupported claims and
true distractors (a fixed seed keeps it reproducible); a $0.30 development budget for real checks; the
full eval spend (about $1.75-$2.55) approved before running.

Claude Code:
- [x] Per-difficulty prompt templates in `agent/prompts/`, including a rule to keep numbers in the form the
      source uses.
- [x] `verify.py`, layer 1 code checks as hard gates: fetched URLs (exists), verbatim quotes (now a gate,
      not just a count), and every number in the answer appears in a fetched page.
- [x] `agent/verifiers/`: a `Verifier` interface with `haiku.py` (layer 2: confirms support and that each
      distractor is wrong) and `jev.py` (layer 3: one `Choice` per claim and per distractor, pinned to
      `jev-1.13.0`, returning verdict, probabilities, confidence, tokens and cost).
- [x] `schemas.py`: a `ClaimCheck` model holding every layer's result per claim, ready for Supabase.
      Built as `JevCheck` (per claim), `HaikuReport`, `CodeCheck` and `Verification`, plus `ItemRecord`.
- [x] `evals/`: the fixed topics, the seeded-error set, a scoring script, and results written to
      `evals/results/` (not committed). The report shows, per layer and combined: catch rate and
      false-reject rate on seeded errors, Haiku/Jev agreement, Jev calibration (verdicts grouped by
      confidence band against the expected answer), and cost and latency for Haiku and Jev separately.
- [x] CLI: `python -m agent quiz "<topic>" --difficulty ...` (prints each claim's Jev verdict and
      confidence) and `python -m evals`.

Gate (Vedant): the eval report meets the DESIGN.md targets (at least 90% citation pass, 0 unfetched URLs,
every item schema-valid, every planted wrong number and non-verbatim quote caught), the combination rule and
Jev threshold are agreed from the measured results, and the hand-reviewed questions are acceptable.
- [x] Passed 2026-10-01. Full run of 60 items: layer 1 85% (92% re-scored after fixing text-matching
      artifacts the eval exposed), 0 unfetched URLs, every item schema-valid; 38 of 40 planted faults
      handled (the 2 misses look like planting noise). Vedant hand-reviewed 10 items: nothing published
      was wrong, the discarded item had a real error, and 2 items Haiku sent to review were correct.
      Decision: keep all_must_pass with the Jev threshold at 0.8. Results in `docs/EVALS.md`.

---

## Session 4 - Supabase bank and Curator (run locally)
**Goal:** the Curator fills the bank when run by hand on Vedant's machine.

Vedant prepares:
- [x] A free Supabase project. `SUPABASE_URL`, `SUPABASE_SECRET_KEY` and `SUPABASE_PUBLISHABLE_KEY`
      (Supabase's new names for the service-role and anon keys) are in `.env`.

Decisions to ask:
- Daily Curator volume (topics per day), given the measured cost per topic and the $10 cap.
- Retirement rule for stale items (age, or a total item cap).
- Who runs `schema.sql`: Vedant pastes it into the Supabase SQL editor, or Claude Code runs it via the
  Supabase CLI (an extra dependency).

Decided 2026-10-02:
- Build the bank up front instead of a slow daily trickle: 30 evergreen topics (approved list in
  `curator/topics.py`), each in LEARN and QUIZ at all three difficulties, about $5 under a $6 cap.
  Then 1 news topic a day (about $0.17 a day, about $5 a month) under a $0.40 cap per run. October
  already had about $2.30 of spend, so daily runs start in November or at Session 7.
- LEARN is served from the bank too (stored explanations per topic and difficulty).
- Keep the three-layer gate (all_must_pass, Jev at 0.8); Jev's confidence is shown to players.
  Jev's criteria made astronomy-specific (`astro-1`) after a Jev-only re-check of the Session 3
  eval: planted faults handled stayed 38/40, generated items 22/20/9 became 23/19/9, $0.022 on
  TypeSafe (`python -m evals rejev RUN_DIR --criteria astro-1`).
- Retirement: news topics' items retire after 90 days; evergreen items never retire.
- Vedant pastes `supabase/schema.sql` into the SQL editor; later changes go in numbered files
  under `supabase/migrations/`.
- Gate amended: a Haiku verifier quote that is not on a cited page sends the item to review instead
  of discarding it (same 38/40 planted faults handled; see `docs/EVALS.md`).
- No new dependency: the store calls Supabase's REST API through `httpx2`. The untracked npm
  `package.json` (`@supabase/server`) was removed; the Session 5 UI is set up with pnpm.

Claude Code:
- [x] `supabase/schema.sql`: `topics`, `items`, `sources`, `claim_checks` (every layer's result per
      claim: code-check outcomes, Haiku verdict, Jev verdict, confidence, probabilities and model
      version), `runs` (with Haiku and Jev tokens and cost kept separately), `curator_runs`,
      `cited_pages`, `reports`, `rate_limits`, with row-level security (the publishable key can only
      read published items with fewer than 2 reports, their sources and checks, and their topics).
      Each run is saved in one transaction by a `record_item()` function.
- [x] `agent/store.py`: Supabase REST reads and writes, with every reply validated by Pydantic.
- [x] `curator/`: `build` and `daily`; discover -> research -> draft -> verify -> publish / review /
      discard -> retire, with a `runs` row and step log per run and a `curator_runs` row per
      invocation. A hard dollar cap; unstored runs are kept on disk and sent by the next run.
- [x] `runs` rows store every metric the v2 analytics page needs (listed under Session 9), so history
      exists from the first Curator run.

Results 2026-10-02 (schema checked first with 18 free checks against the live project: RLS, grants,
triggers, retirement, all passing):
- 1-topic trial ("The Sun and solar flares"): $0.161 Anthropic, $0.0011 TypeSafe.
- Full build, 29 more topics (174 jobs, curator run 3): $4.82 Anthropic (estimate $4.70, cap $6),
  $0.040 TypeSafe, 0 crashes, 0 unstored runs. Median run 15-16 s, about $0.027 per job.
- Bank: 99 published, 66 review, 14 discarded (179 items from 180 runs; 1 run ended without an
  answer). LEARN 55 published / 34 review / 1 discarded; QUIZ 44 / 32 / 13.
- The review queue is mostly Haiku's doubts about explanations (82 of 99 review reasons), most of
  all in LEARN hard (19 of 30 in review). This is the "revisit if the review queue grows faster than
  it can be cleared" case from Session 3; to decide with Vedant after he looks at a sample.
- October Anthropic spend is now about $7.30 of the $10 cap (Sessions 1-3 about $2.30, today
  about $4.98), so no more paid runs this month beyond small checks.

Added after Vedant's first look at the review queue (2026-10-02): the table editor shows an item
without its sources, and he will not publish anything without seeing them. Every item does have
sources (545 of 545 on published and review items were fetched in their run), so the fix is the
review workflow:
- [x] `python -m curator review [--mode] [--difficulty]`: one item at a time with its reasons, marked
      answer, explanation, sources and quotes, and Jev's checks; p / d / s / q. Free.
- [x] `items.reviewed_at`, set by the status trigger when an item leaves review (by the command
      or the table editor). Shipped in migration `002_review_and_safe_resume.sql`.
- Decided: 1 fetched, verbatim-quoted source per item stays the minimum.

Code review before the first push (2026-10-02): 15 findings, all confirmed and fixed. The ones that
touched hard rules:
- The dollar cap is now hard. Each agent run stops before any model call whose cost bound (prompt
  bytes at the cache-write rate plus the full output allowance) could take it past $0.10, and the
  Haiku verifier is skipped (item to review) if its call could cost over $0.07. A job therefore
  never costs more than $0.17, and that is what it reserves against the cap. A replay of the 180
  build runs showed no run or verification would have been stopped by these limits.
- A re-sent payload is never stored twice (`runs.client_id`, checked in `record_item()`).
- A URL that was not read in its run is never stored where a player can see it (citation rule).
Also: Ctrl+C or a crash keeps paid results and still closes the `curator_runs` row; a verifier bug
sends the item to review instead of losing the run; jobs that hit a temporary API error are
retried by the next build; `daily` asks before any spend; stored eval results are re-scored under
the current rules. Migration `002_review_and_safe_resume.sql` carries the SQL side.

Second code review (2026-10-02, on the pushed commit): 15 more findings, all fixed.
- Cost is logged for every billed call, including ones that fail after billing (a reply cut off
  at the output limit) or crash in post-processing, so the cap and `runs` costs stay exact.
- The verifier's cost bound uses Anthropic's free token-counting endpoint for the exact prompt
  size (a sample prompt: 7,739 tokens, against a byte bound of 26,540), falling back to the byte
  bound if the counter cannot be reached.
- `daily` never reuses a feed article under a new name, and finishes a recent news topic left
  incomplete before choosing a new one.
- `topics.lead_url` is hidden from the browser (migration `003_hide_lead_url.sql`): the article
  may never have been read, so it may not be shown as a source.
- Payloads the bank refuses (4xx) go to `pending/rejected/` with the reason instead of repeating;
  NUL characters are stripped before storage; reads and `record_item()` retry with backoff.
- A result that cannot be handled is kept in `pending/unsaved/`; the job loop polls, so Ctrl+C
  works on Windows; `--workers`, `--topics` and `--cap` are validated.
- One shared step from a run to a publish decision (`agent/publish.py`) for the Curator, the
  evals and the CLI; `make_jev` lives in `agent/verifiers`.

Gate (Vedant): runs `python -m curator`, sees `published` and `review` rows, and decides review items
with `python -m curator review`, seeing their sources before publishing.
- [x] Passed 2026-10-02. Vedant decided 28 review items with their sources in view: 26 published,
      2 discarded. The bank stands at 125 published, 38 review, 16 discarded.

Review queue cleared 2026-10-03 on Vedant's instruction: the 35 items held only by Haiku's
explanation doubts were published, then the last 3 as well, to be cleaned up later. Bank: 163
published, 0 review, 16 discarded. The gate rule for new items is unchanged.
- [x] Re-check items 100 (Jev: possibly contradicted), 136 (LIGO: announcement date and a
      verifier misquote) and 165 (Voyager: power-supply date) against their sources. Approved by
      Vedant on 2026-10-05; they stay published. The same day he approved item 183 ("Black
      holes", the first live run, held for review), so the queue is empty: 166 published,
      0 review, 16 discarded.

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
- How the Jev "source check" meter looks and what it says (a sample is shown for approval). It is labelled
  as a source check, not accuracy, and appears per source after the player answers.

Claude Code:
- [x] Vite + React + TypeScript (strict) + Tailwind with pnpm, portfolio design tokens and fonts.
- [x] Controls: `[EASY|MEDIUM|HARD]`, `[LEARN|QUIZ]`, topic input, `[Random topic]`, `[GO]`.
- [x] QUIZ flow: answer, then explanation and sources. LEARN flow: explanation and sources.
- [x] Source-check meter per answer option, read from `claim_checks`: Jev's verdict and confidence.
- [x] Report button (2 reports hide an item). Streak and score in `localStorage`.

Decided 2026-10-03:
- API: Python functions in `api/` (stdlib only), each a `handle(ApiRequest) -> ApiResponse` wrapped
  for Vercel by `agent/web.py`; locally served by `python -m dev.api_server` (port 8787), which
  Vite proxies `/api` to. Reads use the publishable key, so they can only see published items.
- Topic box: suggests bank topics playable at the chosen mode and difficulty; an unknown topic
  shows "Custom topics are coming soon" (Session 6 turns it into a live run).
- Sources: a numbered list with site, link and the quoted passage.
- Source check: per answer option (Jev's verdict and confidence), not per source (see DESIGN.md
  decision 5); LEARN shows how many sentences the sources back.
- A quiz question reaches the browser without its answer; `/api/reveal` sends the answer,
  explanation, sources and source check after the player answers.
- First screen approved by Vedant ("The UI looks great"); placeholder example "Black holes"
  (not yet a bank topic, so it shows the custom-topic hint until it is added).
- New dependencies, all MIT: react, react-dom, vite, @vitejs/plugin-react, typescript,
  tailwindcss, @tailwindcss/vite, and vitest (dev only). Fonts from Google Fonts. New local
  secret `IP_HASH_SALT` for hashing visitors' IP addresses (reports, and Session 6 limits).

Gamified after Vedant's first play-through (2026-10-03):
- QUIZ is played in runs of up to 10 questions on 10 different topics (the chosen topic first),
  with a results screen: score, accuracy, best streak, time, points, rank progress, new badges.
- Points: EASY 100, MEDIUM 200, HARD 300 per correct answer; x1.5 from 3 in a row, x2 from 5;
  +25% for answering within 15 seconds.
- Speedrun clock: runs only while a question waits for an answer, so reading the explanation
  and sources never costs time.
- Ranks from all-time points: Stargazer, Cadet (1,000), Navigator (3,000), Astronomer (7,500),
  Astrophysicist (15,000), Cosmologist (30,000).
- Badges: First light, Hot streak, Perfect run, Hard mode, Speed runner (10 in under 2 min),
  Explorer (10 topics learned).
- No repeats: never within a run, and across visits this browser's unseen questions and
  unplayed topics come first (a note says when repeats are unavoidable). The profile lives in
  `localStorage` and works with storage blocked.
- Jev's confidence stays a number. Why it is so often 1.00 on EASY and HARD: Jev returns exactly
  1.0 when the cited page states the answer outright and plainly rules the other options out,
  which is how EASY questions are built (DESIGN.md decision 13) and how HARD ones about a stated
  number come out. Of the bank's option checks, 84 of 104 (EASY), 32 of 104 (MEDIUM) and 72 of
  88 (HARD) are 1.00; MEDIUM spreads lower because its wrong options are plausible.

Built:
- [x] Endpoints: `/api/topics`, `/api/item`, `/api/reveal`, `/api/report` (salted IP hash, one
      report per visitor per item; two hide an item).
- [x] UI: controls, topic box with suggestions, Random topic, GO; QUIZ card (answer, then result,
      explanation, source check and sources); LEARN card; Report; score and streak in
      `localStorage` (works with storage blocked); recently shown items skipped.
- [x] Game layer: `src/game.ts` (rules) and `src/profile.ts` (saved profile), run HUD, points
      pop-up, results screen, rank and badges strip.
- [x] Tests: 207 Python (endpoints, adapter, bank reads), 18 TypeScript (topics, game rules,
      profile storage).

Gate (Vedant): plays every mode and difficulty with `pnpm dev`, checks that sources open and belong to the item.
- [x] Passed 2026-10-04. Vedant played the gamified build: "looks well and works well".

---

## Session 6 - Custom topics on demand (local)
**Goal:** a typed topic runs the agent live, with guardrails and streamed steps.

Decisions to ask:
- The global daily cap, in runs and in dollars. (Per-user limits were decided on 2026-10-01: 10 custom-topic
  runs a day and 60 API requests an hour per salted-hash user; no global hourly cap.)
- What the UI shows while steps stream, and what it shows when a run is rejected or capped.

Claude Code:
- [x] On-topic check. Recommended: a Jev yes/no question ("is this topic about astronomy or space?"),
      about 0.2 s and $0.00002 per check, measured against a keyword filter on a small set of on- and
      off-topic inputs. The input is user-controlled, so it goes into Jev's state as data, never into the
      question's instructions.
- [x] Per-user limits (salted-hash IPs): 3 custom-topic runs a day and 300 requests an hour; global daily
      cap; over a limit, custom topics fall back to the bank and other requests get HTTP 429. Counters live
      in the Supabase `rate_limits` table so they hold across serverless instances.
- [x] Streamed agent steps to the UI, including each Jev claim check and its confidence as it completes;
      verified results cached into the bank.

Decided 2026-10-04:
- Global cap: 10 live runs and $0.50 a day, plus $4 a month for live runs (the daily Curator needs
  about $5 a month of the $10 limit). A run reserves its hard bound ($0.17) until it ends, then
  settles at its real cost (about $0.027).
- Requests per user raised from 60 to 300 an hour (flagged as a locked decision): a 10-question
  run is about 21 requests.
- While a run streams: a terminal-style agent log. Quiz option checks show only Jev's confidence
  until the player answers (a verdict per option would give the answer away).
- Live results the gate holds for review are shown to the player who asked, labelled 'Not fully
  verified' with the doubts (sent with the answer for a quiz); they join the bank once approved.
  Discarded results send the player to a bank question at the same settings.
- A live quiz question is question 1 of a run; the other 9 come from the bank. A topic the bank
  has but not at this mode and difficulty is researched live too.
- On-topic check: Jev, measured against a keyword filter (`python -m evals ontopic`, $0.0009):
  Jev 44/44, keywords 18/44; on-topic inputs scored 0.95 or more, off-topic ones 0.04 or less,
  and injection attempts 0.18 or less as 'a plain topic name'.
- API wrapper changed from `BaseHTTPRequestHandler` to a standard-library WSGI `app` (a form
  Vercel's Python runtime loads), because WSGI streams a response by returning an iterator. The
  visitor's IP is now the last `X-Forwarded-For` entry (the one a client cannot forge).

Built:
- [x] `agent/topic_check.py` (cleaning and the Jev check), `evals/ontopic.py`.
- [x] Migration `004_on_demand_runs.sql`: custom topic kind, `on_demand_runs` (every live run, the
      limits are counted from it), and `begin_on_demand_run`, `finish_on_demand_run`,
      `hit_request_limit` (secret key only). Visitor hashes are removed after two days.
- [x] `agent/limits.py`, `agent/ondemand.py` (the live run on its own thread, so a paid run is
      stored even if the page closes), `api/research.py` (streamed JSON lines), signed reveal
      tokens for live quiz items.
- [x] UI: agent log, live first question, 'Not fully verified' tag and doubts, fallbacks, 429.
- [x] Tests: 241 Python, 21 TypeScript.

Code review (2026-10-05, before committing), fixed:
- A reservation could leak if the player left right after it was made (three leaks would have
  blocked live runs for everyone until midnight): the run's thread now starts before anything
  more is streamed, so it always settles the slot.
- Closing the stream now waits for a started run to be stored (the close is passed through the
  WSGI layer), so a serverless instance stays alive for it. To confirm on Vercel in Session 7.
- The Haiku verifier's reasons are no longer streamed for a quiz (they can name the answer);
  they come with the answer as the doubts.
- Players' custom topics are left out of the Curator's news prompt.
- Each on-topic check is logged with its tokens and cost (CLAUDE.md rule 1).
- Topic lookup is one filtered read; the public reader repeats the published / fewer-than-2-
  reports rule in every query; the secret-key reader is a separate `LiveResults` class that reads
  one item by id. Live-run clients are made once per process, after checking every setting.
- The agent log's timer restarts for each run.
- Decided by Vedant: 3 live runs a day per visitor (was 10), so one visitor cannot use up the
  global cap of 10 runs a day. The gate's limit check above was run at 10; the rule is the same.

Gate (Vedant): valid topic streams and caches; off-topic is rejected; an 11th custom topic in a day falls
back to the bank; a 301st request in an hour gets HTTP 429.
- [x] Passed 2026-10-05. Vedant ran custom topics in the browser: "Drake Equation" and "Space
      Travel" streamed and were published to the bank, and off-topic input was rejected. Checked
      against the API: a 301st request in an hour got HTTP 429 (Retry-After set), and with 10 runs
      simulated for a test visitor the 11th fell back to the bank without reserving anything. A
      first live run ("Black holes") went to review and is in the queue. Live spend: $0.066.

---

## Session 7 - Move to the cloud
**Goal:** the app runs on Vercel, the Curator runs on GitHub Actions.

Vedant prepares:
- A Vercel project linked to the GitHub repo (`radiculee/cosmic-quiz-agent`, created in Session 0), and the
  secrets entered in both, including `TYPESAFE_API_KEY` (a separate TypeSafe key per environment if the
  console allows it, as with the Anthropic keys).

Decisions to ask:
- Whether public on-demand runs stay on Claude (costs money per visitor) or switch to OpenRouter free models
  through the provider interface, or are disabled publicly.
- Curator schedule (time of day, frequency).

Decided 2026-10-05:
- Live runs on the deployed site stay on Claude with the Session 6 caps (3 a day per visitor;
  10 and $0.50 a day, $4 a month overall).
- The Curator runs daily at 06:17 UTC. Paid `daily` runs start on 2026-11-01: about $7.35 of
  October's $10 is spent (about $2.30 before the bank build, $4.98 on it, $0.07 on live runs),
  and 26 daily runs at about $0.17 would pass the limit around 21 October, which would stop live
  runs too. Until then the schedule runs `python -m curator upkeep` (new, free: stores left-over
  runs, retires stale items, no model calls), which also keeps Supabase's free tier from pausing.
  One manual `daily` run (about $0.17) is made now for the gate.
- Workflow actions are pinned to release commits (checkout v7.0.1, setup-python v7.0.0, cache
  v6.1.0), since the job holds API keys. Secrets go in as Production-only Vercel variables and
  GitHub Actions secrets, with separate Anthropic keys per environment.

Claude Code:
- [x] Keep `runs/curator/pending/` between scheduled runs (actions/cache or an artifact), so a run
      the bank could not store is re-sent by the next one, as it is locally.
- [x] Run the Vercel streaming spike planned on 2026-10-01 (incremental delivery, 300 s cap, client
      disconnect, coexistence with Vite, cold start) and record results in `docs/SPIKE.md`. Check
      that WSGI `app` functions in `api/` stream line by line (the UI copes if they are buffered),
      and that Vercel replaces `X-Forwarded-For` with the client's address.
- [x] Deploy the UI and API; set `maxDuration`; the agent's own time budget stays under it.
      Live at https://cosmic-quiz-agent.vercel.app (2026-10-06). Spike results, the two
      deployment fixes (dependencies read from pyproject.toml; the Anthropic key's name) and the
      move to the `dub1` region are in `docs/SPIKE.md`.
- [x] `.github/workflows/curator.yml`: daily cron plus `workflow_dispatch` (a choice of `daily`,
      `upkeep` or `rejev`); `vercel.json` (Vite build, Python functions at 300 s, lean bundles).
      Checked 2026-10-08: all 4 runs succeeded (2 scheduled `upkeep`, the manual `daily` gate run
      and the manual `rejev`); the left-over-runs cache passes from run to run and is empty; all 4
      secrets are set; the date check switches `upkeep` to `daily` on 2026-11-01. GitHub started
      both scheduled runs about 7 hours late (13:16 and 13:19 UTC for 06:17), which its docs allow
      under high load ("some queued jobs may be dropped"). Harmless for free upkeep; watch it once
      paid daily runs start.

Gate (Vedant): the production URL works; a manual workflow run adds rows to Supabase.
- [x] Passed 2026-10-08: Vedant played the white-dwarf topic ("White dwarf planets in
      second-generation systems") on the live site and it works. Both conditions were met on
      2026-10-06: the production URL works (Vedant played a full run; live custom topics work,
      0.23 s median API time in dub1), and a manual `daily` run (curator run 4, $0.145) added a
      news topic with 6 items. Settled before the gate:
  - The GitHub secret `TYPESAFE_API_KEY` was rejected by TypeSafe (401), so every Jev check in
    that run failed and all 6 items (189 to 194, "White dwarf planets in second-generation
    systems") went to review with no Jev checks. Vedant re-entered the secret on 2026-10-06 and
    chose to re-check them: `python -m curator rejev` (new) re-runs Jev on items whose Jev check
    failed, from the page text stored with each run, re-applies the gate, and stores the result
    through `apply_jev_recheck` (migration 005), which keeps `reviewed_at` for human decisions.
    It is run once from GitHub Actions (`rejev` choice), which also proves the new key works.
    Done 2026-10-06 (Actions run 37484087533): Jev passed all 6; 5 published, 193 (QUIZ medium)
    stays in review on its Haiku doubt; $0.0011 on TypeSafe. The new GitHub key works. Bank:
    171 published, 4 review (186, 187, 188, 193), 16 discarded.
  - Also in review: live runs 186 (Olympus Mons: explanation calls it the largest volcano;
    the source says tied with Rheasilvia as the tallest mountain), 187 (Tidal locking) and 188
    (Space oceans).
  - The scheduled run at 06:17 UTC is the free `upkeep` until 2026-11-01 and does not use Jev.

---

## Session 8 - Pages, router and trophies
**Goal:** the single page becomes separate pages with real URLs (home, Learn, Quiz, the web page
and trophies), quiz runs of 10, 30 or 60 questions, and tiered trophies that pop up when earned.
Changed 2026-10-08 by Vedant: this replaces the old Session 8 (Launch), which moves to Session 10.

Decided 2026-10-08 (grill-me session):
- **Home:** Learn and Quiz as two large cards, with "Try a new topic from the web" as a smaller
  third card below, showing "N of 3 left today". Rank, points and a compact trophy shelf sit
  underneath.
- **Header:** a slim, non-sticky header on every page. Inner pages show "COSMIC QUIZ" on the left,
  linking home. The GitHub icon sits on the right, opens a new tab and has an aria-label.
- **Routing:** real URLs: `/`, `/learn`, `/learn/<topic-slug>`, `/quiz`, `/explore`,
  `/explore/stats` (Session 9) and `/trophies`. A hand-rolled History-API router (no new
  dependency, unit-tested), plus a Vercel SPA rewrite that leaves `/api/*` alone.
- **Learn page:** a difficulty switch, a search box that filters a grid of topic cards (read ones
  are ticked), and Random. A card opens the explanation and sources at `/learn/<slug>`. A topic
  that is not in the bank links to the web page.
- **Quiz page:** difficulty, length (10 / 30 / 60) and START, with no topic choice. Every question
  is a different random topic, unplayed ones first.
  - A length is enabled only when the bank has that many quiz topics at the chosen difficulty.
    Otherwise it is disabled with "HARD: 23 of 60 questions so far". No repeats, no cost.
  - An "End run" button shows results for the questions answered so far. Full-run trophies are
    not awarded. There is no resume after a reload, and points already earned stay.
- **Trophies:** tiered bronze / silver / gold trophies replace the badges, and the v1 badges carry
  over as bronze. Tier colours come from the tokens: bronze `--accent-rust`, silver
  `--text-secondary`, gold `--accent-gold`. The icons are pixel-style SVGs, with no emojis. The
  list and thresholds are approved at the start of the session.
- **Trophy pop-up:** a centred card over a dimmed page, shown right after the answer is revealed,
  while the clock is already paused. Several trophies at once share one card. A button or Esc
  closes it; focus is trapped and reduced motion is respected. Rank-ups pop up the same way. In
  LEARN and on the web page it pops up after the result.
- **Trophy case:** the home page has a shelf. `/trophies` lists every trophy and tier, with locked
  ones greyed and showing how to earn them.
- **Web page (`/explore`):** topic, difficulty and LEARN/QUIZ. The agent log streams, then the
  explanation, or one quiz question, is shown on the page with sources and the source check.
  - No 10-question run is attached.
  - A topic already in the bank at those settings links to Learn or Quiz instead of spending a run.
  - It keeps the limit of 3 a day per hashed IP. The page shows "2 of 3 left today, resets at
    01:00 Irish time", plus a notice when the global cap is reached.
  - Changed later on 2026-10-08 by Vedant: a search now makes a whole topic. See "The web page
    makes whole topics" below.

Decisions to ask:
- The trophy list with its bronze / silver / gold thresholds (a proposal is shown).
- A first-screen mock of the home page and the quiz page, before the rest is built.

Decided at the start of the session (2026-10-08), from a mock of the home, quiz and trophy pages:
- Trophies as proposed, except that Speed runner also needs at least 70% right (7 of 10, 21 of
  30, 42 of 60), so racing through on guesses does not earn it:

  | Trophy | Bronze | Silver | Gold |
  |---|---|---|---|
  | First light | 1 correct answer | 50 | 250 |
  | Hot streak | 5 correct in a row | 10 | 20 |
  | Finisher | Finish a 10 run | 30 | 60 |
  | Perfect run | 10 / 10 | 30 / 30 | 60 / 60 |
  | Speed runner | A 10 run at 12 s a question or less, 70% right | 30 | 60 |
  | Hard mode | Perfect HARD 10 | 30 | 60 |
  | Explorer | 10 LEARN topics read | 20 | 30 |
  | Web researcher | 1 live topic | 3 | 10 |

  With the bank at 30 / 26 / 23 quiz topics, every 60 tier and Hard mode silver cannot be earned
  yet; the trophy case says so on those tiers. Higher tiers of a carried-over badge come with the
  next matching event. Run trophies pop up when the last answer is revealed. Web researcher counts
  live runs that produced a result. A question on the web page scores like a quiz answer.
- The mock approved as shown; End run ends a run in one click.
- The GitHub icon links to Vedant's profile (github.com/radiculee) until the repo is public in
  Session 10, so visitors never meet a 404; then it links to the repo.
- A QUIZ topic already in the bank at the chosen difficulty is played on the web page itself,
  free and with no run attached, since Quiz has no topic choice (LEARN links to
  `/learn/<slug>`). The server's fallback messages no longer promise "a question from the bank";
  the page offers Learn and Quiz instead.
- The reset time is shown in Irish time from the server's reset instant (midnight UTC), so it
  reads 01:00 until the clocks go back on 25 October and 00:00 after.

Claude Code:
- [x] `src/router.ts` and tests: path matching, `navigate()`, `popstate`, `<Link>`
      (`components/Link.tsx`), and the topic slug both ways.
- [x] `src/pages/`: `HomePage`, `LearnPage`, `QuizPage`, `ExplorePage`, `TrophiesPage` and a
      not-found page, each owning its part of the old `App.tsx`. `App.tsx` is now a shell: the
      router, the profile hook, the trophy pop-up queue and the header.
- [x] `src/components/`: `SiteHeader`, `GitHubIcon`, `TopicGrid`, `TrophyIcon`, `TrophyPopup` (a
      native modal `<dialog>`, queued in the shell), `TrophyShelf` and `ModeCard`. `RunResults`
      gains partial-run results, `ProfileStrip` becomes the home summary and shelf, and
      `BadgeChip` is removed.
- [x] `src/trophies.ts` and tests: the trophy definitions and pure "what was just earned"
      functions, replacing `BADGES` and `runBadges`.
- [x] `src/game.ts`: run lengths 10, 30 and 60, `planRun(..., length)`, `availableLength()`, and
      runs that can end early.
- [x] `src/profile.ts`: profile v2 with trophy tiers, `liveRuns` and `finishedRuns`, migrating the
      `cosmic-quiz:profile:v1` badges to bronze and still working with storage blocked.
- [x] `api/quota.py`: `GET /api/quota` returns `{remaining, limit, resets_at, global_open}` for
      the visitor's salted hash, read server-side with the secret key (helpers in `agent/store.py`
      and `agent/limits.py`; no migration). It reads the visitor's rows today (at most 3) rather
      than a PostgREST count, which the REST client does not expose. `fetchQuota()` in
      `src/api.ts`; the route in `dev/api_server.py`.
- [x] `vercel.json`: an SPA rewrite of `/((?!api/).*)` to `/index.html`.
- [x] Checks: 58 TypeScript tests, 258 Python tests, typecheck, build, ruff and mypy --strict.
      Driven in headless Chrome against the local servers: a v1 profile carried over, a perfect
      EASY 10 with both pop-ups (focus on Continue, Esc closes), End run, Back and Forward, deep
      links, the Learn-to-web-page link, a bank question played free on the web page, and 404.
- [x] Committed (`366cddd`, docs `7b5cfd2`) and pushed on 2026-10-08. Production serves every
      deep link and `/api/quota`. Note for the gate: "Black holes" has questions but no LEARN
      explanation, so use `/learn/quasars` for the shared-link check.

### The web page makes whole topics (changed later on 2026-10-08 by Vedant)
Vedant asked that a search on the web page also produce quiz questions at every level. Decided in
a second grill-me session on 2026-10-08, folded into Session 8 before its gate:
1. **Scope:** a search makes 4 items: the LEARN explanation at the chosen level, plus a QUIZ
   question at EASY, MEDIUM and HARD. All four go to the bank.
2. **Controls:** the LEARN/QUIZ switch is removed. The difficulty switch sets the explanation's
   level and which question is shown first.
3. **Pipeline:** 4 separate agent runs, the Curator's evaluated pipeline unchanged, each finding
   sources suited to its level (DESIGN.md decision 13). About $0.12 a search. A shared research
   pass was turned down: a new agent path, the same sources for every level, and not covered by
   the Session 3 evals.
4. **Limits:** the money caps are unchanged ($0.50 a day and $4 a month for live research, so
   the $10 Anthropic limit holds). A search counts once: 2 a day per visitor (was 3 live runs),
   and 4 searches a day for everyone (was 10 live runs). The page shows "1 of 2 left today".
5. **Run order:** one run at a time, so only $0.17 is ever reserved for a search: the explanation
   first (shown at about 20 s), then the question at the chosen level (about 40 s), then the
   other two while the player reads (about 80 s in all). No run starts after about 3 minutes,
   so a slow search may skip a background question rather than pass Vercel's 300 s limit.
   Changed 2026-10-10 by Vedant: the questions first (the chosen level at about 20 s), the
   explanation last, so a search cut short loses the explanation rather than a question (see
   "Fixes and design questions" under Session 10).
6. **Display:** all 3 questions can be answered on the page, each labelled with its difficulty:
   the chosen level first, then "Next: MEDIUM question" and so on as the runs finish. Changed
   2026-10-10 by Vedant: the explanation comes after the questions, behind a button that opens
   once every question is answered.
7. **Failures:** every run goes ahead (the search is already counted). A discarded item is
   reported in the agent log and skipped; if the explanation fails, the page goes straight to
   the questions. Items in review are shown to the player with their doubts, as before.
8. **Topics already in the bank:** only the missing items are made (the explanation at the
   chosen level, and questions at levels without one). What the bank has is shown free
   alongside. If nothing is missing, the search is free and does not count.
9. **Scoring:** Web researcher counts searches that produced something, not items. The
   explanation counts towards Explorer. Each question scores like a quiz answer on its own, with
   no streak across the three.
10. **Plan:** part of Session 8, built in a new session, then one gate for everything.

Vedant prepares: paste `supabase/migrations/006_live_searches.sql` into the Supabase SQL editor
when it is ready (as for 004 and 005).

Decided while building it (2026-10-08, flagged by Claude Code and chosen by Vedant):
- **Late runs get a shorter agent budget.** The 3-minute start cutoff alone does not keep a search
  under Vercel's 300 s: the agent's budget is 120 s a run, plus the verifiers, so a run started
  at 180 s could still be going at 300 s and be lost with its $0.17 left reserved. A run now gets
  the full 120 s, or less if it starts late: what is left before 280 s, minus 40 s for the
  verifiers and the save. Runs that start in the first two minutes (every typical search, about
  80 s in all) keep the full evaluated budget; one that starts at the cutoff gets 60 s.
- **The caps stay as decided.** A run starts only if today's spend plus its $0.17 reservation
  fits $0.50, so at about $0.10 to $0.12 a search the day's 4th search usually makes only 1 or 2
  items, or cannot start (the page then says live research is paused for everyone). 4 is a
  ceiling; the money rules do not change.

Claude Code (next session):
- [x] Migration `006_live_searches.sql`: live runs carry a search id; `begin_on_demand_run`
      counts searches (2 a day per visitor, 4 a day for everyone) and keeps counting each run's
      reservation against the dollar caps; a later run of a search already counted is not
      counted again. `supabase/schema.sql` updated to match. (Session 9's `agent_stats`
      migration becomes 007.) Built as `on_demand_runs.search_id`, the id of the run that opened
      the search (null on that run, which is the one counted), and an 11-argument
      `begin_on_demand_run` that also checks a later run joins the same visitor's search, that
      its earlier runs have ended, and that it has fewer than 4 runs. The 9-argument version from
      004 stays until this is deployed, so the live site keeps working; 007 drops it.
- [x] `agent/limits.py`, `agent/store.py` and `api/quota.py`: the limits and the quota in
      searches, so the page shows "1 of 2 left today".
- [x] `agent/ondemand.py` and `api/research.py`: a request takes a topic and a difficulty (no
      mode). The search works out the missing items, runs the on-topic check once, then the runs
      one at a time on the worker thread, each reserving and settling its own cost, with no run
      started after about 3 minutes. Every event says which item it belongs to, a quiz question
      comes with its own reveal token, and closing the page still finishes and stores the search.
      The stream starts with a `plan` event (each item, live or from the bank); a `missed` event
      reports an item discarded, failed or not started; `BankReader.coverage` replaces `has_item`.
- [x] `src/pages/ExplorePage.tsx`, `src/api.ts` and `src/types.ts`: no LEARN/QUIZ switch; the
      explanation, then the questions labelled with their difficulty, with a next button as each
      background question arrives; bank items shown free alongside; scoring and trophies as
      decided above. Also `src/search.ts` (the search's slots, pure and tested), the agent log
      grouped by item, `searchStatus` in `src/topics.ts` (new, partly in the bank, or complete
      and free), and `explorePath` without a mode.
- [x] Docs: DESIGN.md decisions 4 and 9 (done 2026-10-08, with this record).
- [x] Tests with the scripted fake model (no paid calls), then typecheck, build, pytest, ruff and
      mypy --strict, and a drive of the page against the local servers. 268 Python tests (one
      search runs through the real loop and verifiers with the scripted model and fake Jev) and
      73 TypeScript tests. Driven in headless Chrome against Vite and a scratchpad copy of the
      API with the agent runs, the on-topic check and the limits store faked (nothing spent,
      nothing written to Supabase): 39 checks passed, among them a full search with an item left
      out and one in review, a bank topic with gaps, the limit after 2 searches, a free complete
      topic, a deep link, and a page closed mid-search whose 4 runs were still stored and
      settled. The real local server served a complete topic's search for free; `/api/quota`
      answers 503 until 006 is applied.

Vedant, optional, before the gate: run `python -m curator review` for items 186, 187, 188 and
193. Publishing 193 takes MEDIUM quiz questions from 26 to 27.

Gate (Vedant): run `pnpm dev` and `python -m dev.api_server` and check:
- every card, plus Back, Forward and deep links;
- the Learn grid, search and a shared `/learn/<slug>` link (for example `/learn/quasars`);
- Quiz 10 on each difficulty and 30 on EASY, the disabled 30/60 messages, and End run;
- trophy pop-ups, including carry-over of existing badges, and `/trophies`;
- the web page: one search shows the explanation and 3 questions labelled with their difficulty;
  the counter goes from 2 to 1 and the limit message appears after 2 searches; a bank topic
  with a gap (for example "Black holes", which has no explanation) fills only the gap. Two real
  searches cost about $0.24;
- the GitHub icon.

After commit and push, check the web page and deep links on production.

Gate progress (2026-10-08):
- [x] Vedant applied migration 006 in the SQL editor. Checked: the new `begin_on_demand_run`
      refused to join a search that does not exist and inserted nothing, and the quota read
      counts searches against the real table. The deployed site kept working through the 004
      function: two Antimatter runs on production after the migration were published.
- [x] The web page's live searches. Locally the on-topic check failed with HTTP 401 (the
      `TYPESAFE_API_KEY` in the local `.env` is rejected; production's works), which stopped the
      search before anything was reserved. Vedant chose to test the searches on production
      instead of replacing the local key. The production runs made earlier on 2026-10-08 count
      as searches, so the search check there starts after 01:00 Irish time. Deployed the same
      day (`4d5fd8f`; free checks on production passed); Vedant moved the check to the end of
      Session 9. Passed 2026-10-09 on Vedant's word, with what the database confirmed recorded
      there.

---

## Session 9 - Analytics for nerds
**Goal:** a public page of everything the agent measures, opened from the web page. Changed
2026-10-08 by Vedant: it was a v2 page (`/stats`, planned after launch) and is now part of v1.

Decided 2026-10-08:
- A button on `/explore` opens a full-screen panel at `/explore/stats`. Back closes it.
- Two tabs:
  - **This run:** model calls, tools, pages by domain, tokens, cost, step timings and Jev checks
    for the search just made (up to 4 runs since the later 2026-10-08 change; to settle in
    Session 9 whether the tab shows the search as a whole or run by run).
  - **The agent:** the groups below, filterable by mode, difficulty and Curator vs live.
- Charts are hand-written SVG (no chart library). The stats are public, including dollar spend.
  Only aggregates leave the database.

What "The agent" tab can show (the 2026-10-01 list, grouped under the 2026-10-08 headings):

| Group | Statistics |
|---|---|
| Volume, outcomes and cost | Runs; outcome split (passed, failed citations, no answer, budget exceeded, model error); published / review / discarded rate; cost per run and per published item, Haiku and Jev separately; month to date against the $10 Anthropic cap and the TypeSafe balance |
| Tokens, caching and speed | Average input, cache write, cache read and output tokens per run; cache hit ratio; savings from prompt caching (actual against uncached price); run time (median and 95th percentile); latency per model call, per tool and per Jev check |
| Agent behaviour and evidence | Model calls per run; tool calls by tool; how often the model calls tools in parallel; pages fetched per run and by domain (Wikipedia, NASA, ESA, arXiv); nudges; which budget ran out, when one did; citations per answer; kept against dropped; verbatim quote rate; number-check pass rate |
| Verifiers | Haiku verdict split; Jev verdict split; Jev confidence histogram; Haiku/Jev agreement; why items went to review |

Data and serving (changed 2026-10-08 by Vedant; it was aggregated SQL views refreshed after each
Curator run):
- Migration `007_agent_stats.sql` (006 is the web page's searches, Session 8): a
  `security definer` function (`set search_path = ''`),
  `agent_stats(p_mode, p_difficulty, p_source)`, that returns aggregates only, as jsonb. Only it
  is granted to anon; `runs` stays private, so salted IP hashes and step logs stay server-side.
  007 also drops the 9-argument `begin_on_demand_run` from 004, which 006 left in place for the
  site deployed before the searches change.
- `api/stats.py`, edge-cached for about 10 minutes.
- The live run's `result` event gains a `stats` object, built from `RunResult` and the
  verification in `agent/ondemand.py`.
- `src/pages/StatsPanel.tsx` with the tabs, and `src/charts/` (`StatTile`, `BarSplit`,
  `Histogram`) in SVG with the design tokens; Press Start 2P only for small stat labels.

v1 prerequisites (done, so the page has history from the first day):
- Session 3: eval results saved as JSON with the date, model and Jev versions, and per-layer scores.
- Session 4: each `runs` row stores mode, difficulty, source (Curator or on-demand), outcome, Haiku and Jev
  tokens and cost separately, cache tokens, wall time, per-step latencies, tool calls by name, pages
  fetched by domain, nudges and the budget reason.

Decisions to ask:
- The first-screen layout and the default date range.
- Three items from the 2026-10-01 list that the 2026-10-08 decision does not mention: the 2 x 3
  grid comparing every mode and difficulty side by side; eval history over time (citation pass
  rate, seeded-error catch rate per layer, Jev calibration); and player statistics, which need
  anonymous answer events (no IP, no account) and so a GDPR note.

Decided at the start of the session (2026-10-08), each as recommended:
- **First screen:** summary first. The filters (mode, level, source, range), four tiles (runs,
  published by the gate, cost per published item, median run), the month's spend against the
  caps, and the mode-and-difficulty grid; the four groups follow as numbered sections, one column.
  (Changed later the same day by Vedant: see "Four key elements" below.)
- **Date range:** all time by default, with 7- and 30-day switches. `agent_stats` gains a fourth
  argument, `p_days` (the API takes only 7 and 30, so each filter set is one cache entry).
- **"This run" is "This search":** the search as a whole, then one row per run that opens to its
  steps and timings. Jev's checks are counts only, so a question waiting for its answer is not
  given away.
- **The 2 x 3 grid:** included. It follows the source and range filters only.
- **Eval history:** the latest eval as a static section. `python -m evals export` (new, free)
  writes a summary of every stored eval run to `src/data/evals.json`, which is committed and
  built in; it grows into a history as evals are re-run.
- **Player statistics:** left out of v1 (a write path and a table just before the security
  audit, fake answers could skew it, and it needs a privacy note). Revisit after launch.

Decided while building it (2026-10-08):
- **A `stats` event per run, not a field on `result`.** A discarded run sends `missed`, so a
  field on `result` would leave its cost out of the search's totals. Explained to Vedant before
  building (he could not reply then); to confirm at the gate.
- Chosen without asking, to change if wanted: "gate" counts what the publish gate decided when
  the run was stored and "bank" where the items are now; the spend shown is what `runs` records
  (eval and development runs and the on-topic checks are not stored, so the consoles show a
  little more), and there is no TypeSafe balance in the database, so Jev's spend is shown this
  month and in all instead; the $10 Console limit is mirrored as `ANTHROPIC_MONTHLY_LIMIT_USD` in
  `agent/config.py`; `/api/stats` refuses unknown parameters, so they cannot make cache entries.
- For the Session 10 audit: anyone holding the publishable key can call `/rpc/agent_stats`
  directly, past the edge cache and the 300-an-hour limit. It returns aggregates only and runs
  one small query.

Four key elements (changed 2026-10-08 by Vedant, in a grill-me session after seeing the built
panel): the panel should show only four key elements at first, for the reader's attention, and
the rest only when asked for.
- **Scope:** both tabs, four each. The tab switch is navigation, not an element.
- **Filters:** one Filter button that names the current choice ("All runs, all time") and opens
  the four filter rows. The filters still scope the four elements and every group.
- **The agent opens on:** published by the gate (with "104 of 195 runs" in its note), cost per
  published item, median run, and this month's spend as a meter against the $10 limit.
- **The rest:** closed rows under the four, each with its name and a one-line hint, opened one
  at a time: By mode and level, Spend this month (live research and TypeSafe), Volume, outcomes
  and cost, Tokens, caching and speed, Agent behaviour and evidence, Verifiers, Evals. The
  dates and "figures as of" are a footnote.
- **This search opens on:** cost, items made out of those planned (with how many are in review
  or left out), time and pages read. Closed rows: Run by run, Tokens, Pages by site, Tool calls,
  Jev's checks.
- **Rows always start closed;** nothing is stored in the browser.
- **Built now, before the gate.**

Vedant prepares: paste `supabase/migrations/007_agent_stats.sql` into the Supabase SQL editor.

Claude Code:
- [x] Migration `007_agent_stats.sql` (shown before pasting): `agent_stats(p_mode, p_difficulty,
      p_source, p_days)`, `security definer`, `stable`, `search_path = ''`, every argument checked;
      aggregates only as jsonb (volume, bank, tokens, speed, behaviour, verifiers, grid, budget);
      execute revoked from everyone and granted to anon, authenticated and service_role; drops
      the 9-argument `begin_on_demand_run`. `supabase/schema.sql` updated to match.
- [x] `agent/run_stats.py` and the `stats` event in `agent/ondemand.py`: sent once per run that
      made a record, before it is stored, and guarded so a failure there never costs the run.
- [x] `agent/stats.py` (reply models checked field by field, the reader, caching savings priced
      from `agent/config.py`) and `api/stats.py` (edge-cached for ten minutes), routed in
      `dev/api_server.py`.
- [x] `evals/export.py` and `src/data/evals.json` (1 full eval: 51/60 pass the code checks, 38/40
      planted faults kept out; the on-topic check: Jev 44/44, keywords 18/44).
- [x] UI: `/explore/stats` over the web page (which stays mounted, so a search keeps going),
      `src/pages/StatsPanel.tsx` (a modal dialog; Esc, Close and Back close it), the tabs in
      `src/components/stats/`, `src/charts/` (StatTile, BarSplit, BarList, Histogram, Meter and
      Table, hand-written SVG in the tokens; colours checked with the data-visualisation
      validator), `src/stats.ts`, `src/shapes.ts` and `src/guards.ts`, `useStats`.
- [x] Four key elements (above): the Filter button, the four key figures per tab, and closed
      rows (`Group` in `src/components/stats/Section.tsx`) whose figures are drawn only once
      opened. 112 TypeScript tests (3 new); a second drive passed 39 checks, among them exactly
      four figures per tab, every row closed with no chart drawn but the spend meter, one row
      opening at a time, the filters scoping the four, and rows closed again on every visit.
- [x] Checks: 290 Python tests (22 new) and 109 TypeScript tests (36 new), all with the scripted
      fake model or none; typecheck, build, ruff and mypy --strict.
- [x] Driven in headless Chrome against Vite and a scratchpad copy of the API (fake search runs;
      `/api/stats` answered by a Python re-implementation of `agent_stats` over the real rows,
      read-only): 42 checks passed, among them the filters, Esc, Back and Forward, a deep link, a
      search filling the tab as its runs end (a discarded run counted), no answer text in the
      panel, and no sideways scroll at phone width. The drive found and fixed: chart marks drawn
      black (an SVG attribute does not resolve `var()`), focus taken from the button on close,
      clipped labels and the grid wrapping on a phone. The real `/api/stats` answers 503 (not
      cached) until 007 is applied.
- [x] After 007 is applied: compare the live function with the Python re-implementation on 7
      filter sets (read-only), then check `/api/stats` on the local server. Done 2026-10-09:
      all 7 the same field by field; the real handler answers 200 with the edge-cache header;
      only the 11-argument `begin_on_demand_run` is left.
- [x] Fix the code review's findings (2026-10-08): `docs/CODE_REVIEW_SESSION9.md`, 7 items,
      two of them confirmed bugs (a dead Back press after Back, Forward and Close; `days`
      accepted in many spellings). Done 2026-10-09, all 7 (item 4 as the comparison only, on
      Vedant's choice: `python -m dev.check_stats`, 7 of 7 the same). The drive found one more:
      handling the dialog's `close` event (item 5) made Esc go Back twice when Chrome does not
      let the cancel be prevented; the panel now leaves `/explore/stats` once per close. 302
      Python and 114 TypeScript tests; a drive of 24 checks passed. Details in the review file.

Gate (Vedant): picks a filter and checks the numbers against the Supabase tables and the
Anthropic and TypeSafe consoles.
- [x] Paste 007; the comparison above agrees (2026-10-09).
- [x] Open the panel from `/explore` (and at `/explore/stats` directly): four elements per tab,
      the rest in closed rows; try the Filter button, each filter and the 7-day range; the
      numbers against the Supabase tables and the consoles (expect the consoles to be a little
      higher: evals and development runs are not in `runs`). Passed 2026-10-09 on Vedant's
      word. The figures against the tables are checked by `python -m dev.check_stats` (7 of 7
      filter sets the same); a check against the consoles was not reported.
- [x] Confirm the `stats` event (above), or say what to change. Confirmed 2026-10-09: for the
      Antimatter search below, the "This search" tab showed what the stored runs give ($0.067
      Anthropic and $0.0006 TypeSafe, 2 items made with 1 in review, 80 s, 4 pages read).

At the end of the session, after its gate (carried over from Session 8 on 2026-10-08):
- [x] Vedant runs two live searches on https://cosmic-quiz-agent.vercel.app/explore, on a day
      his network has not used live research yet (the count resets at 01:00 Irish time): a new
      topic at MEDIUM (about $0.12: the explanation, then three questions labelled by
      difficulty, the next button waiting for each), then "Black holes" at MEDIUM (about $0.09:
      3 items made, the EASY question marked "From the bank, free"). The counter goes 2, 1, then
      the limit message. Done on 2026-10-09: Antimatter (a topic the bank had in part) at 15:29
      Irish time, then "Red light shift index" (new) at EASY: the explanation, then three
      questions labelled by difficulty; the counter went from 1 to the limit message ("You have
      used today's 2 live searches").
- [x] Claude Code checks `on_demand_runs` read-only: each search's later runs carry the id of
      the run that opened it, and every run's `spent_usd` is set. Then the Session 8 gate is
      recorded as passed. Done 2026-10-09: one search since 01:00 Irish time, opened by live
      run 20 (QUIZ MEDIUM, item 198, in review) with live run 21 (QUIZ HARD, item 199,
      published) carrying `search_id` 20. Both have `spent_usd` set ($0.041657 and $0.025224),
      each equal to its run's stored Anthropic cost, and both come from the same visitor (hashes
      compared, not printed). It made only what the bank lacked (Antimatter already had the
      EASY explanation and question from 2026-10-08), which matches a search at EASY. Session 8
      and Session 9 gates recorded as passed on Vedant's choice.
      The second search, checked the same way: opened by live run 22 (LEARN EASY, item 200,
      published), with live runs 23 (QUIZ EASY, item 201, published), 24 (QUIZ MEDIUM, item 202,
      review) and 25 (QUIZ HARD, item 203, review) each carrying `search_id` 22; `spent_usd`
      set on all 4 and equal to each run's stored Anthropic cost; the same visitor throughout.
      Vedant's screenshots of "This search" match the stored runs: $0.152 with $0.0010 on Jev,
      4 of 4 made with 2 in review, 122 s, 10 pages from 2 sites, 23 model calls, and Jev's 32
      claims (22 supported, 9 contradicted, 1 not addressed); run by run the same calls, pages
      and costs, and times within 0.1 s (the event carries unrounded times; `runs` stores each
      to 2 decimals). The screenshots also showed "1 pages" in a run row, fixed the same day
      with the file's `plural()`. The local `TYPESAFE_API_KEY` is rejected (HTTP 401), so live
      runs work only on production until Vedant replaces it.

---

## Session 10 - Security, public repo, domain and launch
**Goal:** a hardened app, a public repo and the site on Vedant's domain. Changed 2026-10-08 by
Vedant: it replaces the old Session 8 (Launch) and adds the security audit and the public repo.

Decided 2026-10-08:
- **Security:** a full audit of the code and database, and every finding fixed. That includes
  headers, dependencies, and repo and platform guards if the audit flags them. Anything that needs
  a new tool or a paid feature is asked about first.
- **GitHub:** the repo goes public with an **MIT** licence, after the audit and a secret scan of
  the whole history.
- **Domain:** `cosmic.vedantgaikwad.ie`, as a CNAME at Web Hosting Ireland, where the domain's DNS
  is. The `.vercel.app` address redirects to it. Nothing new to buy.

Decided 2026-10-09 (planning, each as recommended):
- **Two sessions.** 10a is the audit and its fixes, with its own gate. 10b is everything that
  publishes: the history scan, the docs read-through, LICENSE, the public repo, the domain, the
  README, the OG image, the privacy page and the launch. The repo goes public only after 10a's
  gate.
- **History scan:** gitleaks (free, MIT), one binary downloaded outside the repo and run once,
  not a project dependency, plus a grep of every commit for this project's key prefixes and
  `.env` names. Once public, GitHub's secret scanning and push protection (free on public
  repos) take over.
- **A key found in the history:** rotate it at its provider and keep the history as it is (a
  revoked key is harmless, and the commits are part of what recruiters read).
- **`/rpc/agent_stats` (audit note 1):** kept as it is and documented: the figures are public by
  design and aggregates only, neither the Supabase URL nor a key is in the browser bundle
  (checked 2026-10-09), and the anon role's statement timeout bounds each call (3 s by default
  on Supabase; confirmed live in 10a). The reasoning goes in the audit record and the README's
  security notes.
- **Docs:** `docs/` and `CLAUDE.md` go public as they are, after Vedant reads them for anything
  private.
- **README:** an engineering case study: a short pitch and the live link, a Mermaid architecture
  diagram (GitHub draws it from text), the agent loop, the three-layer publish gate with its
  measured catch rates, the cost controls with real numbers, security notes, and how to run it.
- **OG image:** a title card ("COSMIC QUIZ" in Space Grotesk on the void background, the teal
  accent, a one-line tagline, a few pixel stars), 1200x630, rendered from an SVG in the repo
  with the headless Chrome already on the machine (no new dependency). Changed 2026-10-10 by
  Vedant: the card is the observatory scene with "COSMIC QUIZ" and the tagline in its sky, still
  1200x630 and rendered with headless Chrome (see the scenes step below).
- **Privacy:** a `/privacy` page with a footer link, in plain words: what is stored, why, for how
  long, and a contact; the same text in the README. Each retention it states is checked in 10a.

Before 10a: nothing. The Session 8 and 9 gates passed and both live searches are checked
(2026-10-09). Items 198, 202 and 203 from those searches are in the review queue.

### Session 10a - Security audit and fixes

Decisions to ask at the start:
- Python dependency audit: `pip-audit` (free, Apache-2.0, a new dev-only tool in
  `requirements-dev.txt`), or rely on Dependabot alerts once public. `pnpm audit` is built in.
- Report hashes: `reports.user_hash` is kept with no end date (it stops one visitor reporting an
  item twice), while `on_demand_runs` and `rate_limits` remove theirs after two days. Keep it and
  say so on the privacy page, or remove it after a set time.
- Any finding whose fix needs a new tool, a paid feature or a change to a locked decision.

Decided at the start of 10a (2026-10-09), each as recommended:
- **Python dependency audit:** `pip-audit` 2.10.1, pinned in `requirements-dev.txt` (dev only).
- **Report hashes:** cleared after 30 days by the daily upkeep; the report and its count stay.
- **Header check:** locally first (the built `dist/` with the `vercel.json` headers, in headless
  Chrome), then a scan of production after the push.

Decided on the audit's 19 findings (2026-10-09; details in `docs/SECURITY_AUDIT.md`):
- Fix the five Medium findings (S1 to S5): cross-site requests, report flooding, the paid
  on-topic check before the limits, redirects before the allow-list, and security headers.
- Also S13 (the daily purge of visitor hashes, migration 008), which carries the 30-day decision,
  and S17 (IPv6 visitors counted by their /64).
- The other Lows (S6 to S12, S14) are accepted for now, each with a reason, to revisit after
  launch. S15 (instructions in fetched pages) is accepted and documented, with the defences in
  code. 10 reports a day per visitor (S2).

Claude Code (each finding recorded in `docs/SECURITY_AUDIT.md` with its fix and test):
- [x] Every API input: each endpoint's method, parameters and body checked, unknown fields
      refused, sizes bounded (topic length, ids, the stream's lifetime), and no error reply that
      carries a stack trace, a database message or a key. Found S1 (fixed: a POST must be JSON,
      and a cross-site request is refused), S8 and S9 (accepted for now). No reply carries a
      stack trace, a database message or a key.
- [x] Rate limits on every endpoint, including `/api/quota` and `/api/stats`; that a 429 carries
      Retry-After; and that the global live-research caps hold when searches start at the same
      moment (`begin_on_demand_run` under concurrency). All hold (an advisory lock serialises
      starts). Found S2 (fixed: 10 reports a day, and `curator review --reported`) and S3 (fixed:
      the limits are read before the paid on-topic check).
- [x] Reveal tokens: the signing key, a constant-time compare, purpose binding and expiry. All
      fine except expiry: S10, accepted for now.
- [x] SSRF in `fetch_page`: host matching (exact or dot-suffix), IP literals and private ranges,
      user info and ports in URLs, redirects to hosts off the allow-list, schemes, and size caps.
      Found S4 (fixed: redirects followed in code with each hop checked; the default port only;
      dot segments resolved), S6 and S7 (accepted for now).
- [x] Prompt-injection paths: the typed topic (the on-topic check takes it as data), fetched page
      text reaching the agent, tool arguments, and the citation rule enforced in code. S15
      accepted (the defences stay in code); S12 accepted for now.
- [x] RLS and grants checked live, read-only. The probe with the publishable key passed (every
      private table refused, no write allowed). The SQL editor query below ran on 2026-10-13
      (as one combined query, pasted by Vedant): the anon role's timeout is 3 s (S18), and
      `rls_auto_enable` is Supabase's RLS event-trigger function, accepted together with two of
      this project's trigger functions that keep the default execute grant (S19).
      RLS on every table, and every function in `public`
      with its owner, `security definer` and who may execute it, and the browser roles'
      statement timeouts. Vedant runs this in the SQL editor (it lists, and changes nothing):

      ```sql
      select p.oid::regprocedure as function, r.rolname as owner,
             p.prosecdef as security_definer,
             has_function_privilege('anon', p.oid, 'execute') as anon,
             has_function_privilege('authenticated', p.oid, 'execute') as authenticated
      from pg_proc p join pg_roles r on r.oid = p.proowner
      where p.pronamespace = 'public'::regnamespace
      order by 1;
      select evtname, evtevent, evtfoid::regproc from pg_event_trigger;
      select rolname, rolconfig from pg_roles where rolname in ('anon', 'authenticated');
      ```

      This answers audit note 2: what created `public.rls_auto_enable`, and whether the browser
      roles can run it.
- [x] `agent_stats`: record the decision above (audit note 1) and its reasoning (S18). The anon
      statement timeout, confirmed from the query above on 2026-10-13, is 3 s.
- [x] Secrets: none in the built `dist/` bundle, in a reply, or in a log line; `IP_HASH_SALT`
      long and random; the visitor's IP read only from the last `X-Forwarded-For` entry. All
      hold; the local salt is 256 bits. The production salt cannot be read from here (S14:
      Vedant confirms it is 64 random hex characters).
- [x] Security headers in `vercel.json`: Content-Security-Policy (self, plus Google Fonts),
      frame-ancestors, X-Content-Type-Options, Referrer-Policy and Permissions-Policy; HSTS as
      Vercel serves it (S5, fixed). Checked locally as decided: every page in headless Chrome
      with no CSP violation, and framing refused. The production scan comes after the push.
- [x] Dependencies: `pnpm audit`, and the Python audit as decided; pins up to date where a fix
      exists. Both clean; no pin needed a change.
- [x] GitHub Actions: least-privilege `permissions`, no `pull_request_target`, pinned actions
      (done in Session 7), secrets only in the steps that need them, and the past run logs read
      for anything private, since they become public with the repo. All 6 runs' logs read:
      secrets masked, nothing private.
- [x] Data retention as the privacy page will state it, checked against the schema and the
      live tables. Holding today only because of traffic (S13, fixed with migration 008: live
      runs' hashes and request windows cleared after a day, report hashes after 30 days).
- [x] Tests for every fix, with the scripted fake model only; typecheck, build, pytest, ruff,
      mypy --strict; `python -m dev.check_stats` if `agent_stats()` changes (it did not). 330
      Python tests (28 new) and 116 TypeScript tests (2 new).

Vedant, to finish 10a:
- Run the SQL editor query above and paste the result (S18's timeout, S19). Pasted on
  2026-10-13, as one combined query (the editor shows only the last statement's result); S18
  and S19 closed.
- Paste `supabase/migrations/008_purge_visitor_hashes.sql` into the SQL editor before the push;
  until it is in, the scheduled `upkeep` fails. Applied 2026-10-10.
- Check the production `IP_HASH_SALT` (S14). Vercel does not show the stored value, so it cannot
  be read back; replacing it with a new 64-character random hex value would settle it.
- Optional: install the latest Python 3.12 and recreate `.venv` (S16).

Committed on Vedant's word as ten commits, one per finding (`f6811e8` to `9a97174`), each
passing pytest, ruff and mypy on its own, and pushed on 2026-10-10. Production header scan the
same day, read-only: all six `vercel.json` headers on the home page, two deep routes, a built
asset and two API replies. S1 checked live: a cross-site request that reaches a function gets
403 (sent `no-store`, so it is never cached) and a plain-text POST gets 415. A cross-site GET
that the edge cache answers never reaches the function and gets the cached public reply; that
is harmless (public bank data, nothing counted or written, and unreadable to the other site
without a CORS header).

Gate (Vedant): reads `docs/SECURITY_AUDIT.md` and confirms every finding is closed or accepted
with a reason; a header scan of the deployed site; the checks above pass.

### Scenes: the home slideshow and scene backgrounds (between 10a and 10b)

Planned in a grill-me session on 2026-10-10 and built the same day as its own step. The flat
void page background becomes Vedant's AI-generated scenes: a white object and a small white
animal in a wind-swept salmon field under a navy sky, with the top of the sky empty for text.
The masters (2720 x 1536 PNG) stay in `bg_images/`, which is in `.gitignore`.

Decided 2026-10-10 (Vedant, each as recommended):
- **Where:** the scenes take turns as a slideshow on the home page. Learn, Quiz, the web page and
  Trophies show the observatory as a still, so nothing changes behind a timed quiz and an inner
  page loads one image.
- **Home:** a full-screen hero. The title, the tagline and a compact row of the three ways in
  (Learn, Quiz, a new topic from the web with the searches left today) sit in the scene's empty
  sky; the progress sits just below the fold. This changes the Session 8 home layout.
- **The layer:** a fixed element behind the app (not `background-attachment: fixed`, which iOS
  ignores), so the content scrolls over it. From 4:3 up the scene fills the screen, anchored at
  the bottom; narrower, the whole scene sits at full width, pinned to the bottom, under a sky
  gradient sampled from the scenes, its top edge faded into it.
- **Cards stay solid.** Text straight on a scene is ink with a soft dark shadow, secondary lines
  at 80%; never slate. The analytics panel stays solid void; the trophy pop-up dims the scene.
- **No motion** beyond the crossfade: the wind is in the images.
- **Web sizes** made with headless Chrome (a canvas encoded to WebP), no new tool or dependency.
  Only the web sizes are committed.
- **Licence:** the code stays MIT; the art is kept out of it (generated by Vedant with
  one_prompt_design, all rights reserved). The note goes in LICENSE and the README in 10b; the
  tool's spelling is confirmed then.
- **Timing:** 10 s a scene and a 1.5 s crossfade, the observatory first.
- **Pausing (WCAG 2.2.2):** a pause/play control on the hero; no rotation under
  `prefers-reduced-motion` (the observatory stays, with no control); no rotation while the tab
  is hidden.
- **Loading:** only the observatory is preloaded. The other scenes are fetched at idle time once
  it is decoded, and each takes its turn only once it is decoded itself, so a crossfade never
  shows half an image.
- **OG card (10b):** the observatory.

Decided after the mock and the first drive (2026-10-10, each as recommended):
- **The portal scene is left out.** Its arch rises to about 12% of the height, behind the title
  and tagline on every wide screen. It can come back as a version with the arch lower: its files
  and one line in `src/slideshow.ts`. Three scenes, a 30 s loop.
- **The progress below the fold is one solid card** (rank, points, trophy shelf and the bank's
  size), not text on the scene, which landed on the grass. The Quiz page's progress strip gets
  the same card. A "Your progress" chip at the foot of the hero jumps to it, opposite Pause.
- **Small lines below a page's intro sit on solid chips** (`scene-note`): counts, notes, the
  hint, the quota and points lines, loading and error lines. On inner pages the observatory's
  white dome sits behind the centre column, and two such lines crossed it at 1.0 to 2.3 : 1;
  dimming the still enough to fix that (to 50%) made the inner pages muddy. Titles, intros, the
  labels beside controls and short labels at the top of a view stay on the sky.
- **Controls on the scene are solid in every state:** a disabled button no longer fades to 40%
  (the dome showed through GO), and hover brightens instead of fading.

Built:
- [x] `public/scenes/`: the observatory, piano and glasshouse at 1280, 1920 and 2560 px (76 to
      283 KB each), and `observatory-v1-1920.jpg` (269 KB) for a browser without WebP. The
      names carry a version; `vercel.json` caches `/scenes/*` for a year, immutable.
- [x] `src/slideshow.ts`: the pure rules (the order, each turn, which scenes are decoded, the
      crossfade's layers, when to rotate and when to fetch). `src/components/Scene.tsx` runs
      them as the fixed layer, mounted once in `src/App.tsx`; `src/useBrowserState.ts` follows
      reduced motion and the hidden tab.
- [x] `src/index.css`: the sky tokens, the scene layer and its 4:3 switch, the crossfade (off
      under reduced motion), and `on-scene`, `on-scene-muted` and `scene-note`.
- [x] The hero in `src/pages/HomePage.tsx` with the compact `ModeCard`; text on the scene swept
      across every page; the translucent page cards (`CardFrame`, `RunResults`, `AgentLog`, the
      web page's notes, the trophy list) made solid.
- [x] `index.html`: the observatory preloaded at the width the screen needs, and `theme-color`.
- [x] Tests: 18 Vitest tests for the slideshow (order, wrap-around, skipping an undecoded scene,
      turns, pause and resume, the crossfade's layers, when to rotate and fetch, the preload
      matching the first scene) and 4 packaging tests (each scene a real WebP at the width its
      name says and under 350 KB, every named file present and none unused, the cache rule,
      the CSS fade and 4:3 switch matching `src/slideshow.ts`).

Checked locally (headless Chrome over the built `dist/`, served with every `vercel.json`
header, `/api` passed to `python -m dev.api_server`):
- 1920x1080, 1440x900, 1024x768, 768x1024 and 390x844: the hero's subjects clear of the content,
  the phone's sky seamless, no sideways scroll, no CSP violation and no console error.
- The slideshow in order, a turn every 10 s (observatory, piano at 9.9 s, glasshouse at 19.9 s,
  observatory at 29.9 s); Pause holds it for 13 s and Play gives a full turn; a hidden tab
  (simulated) holds it. Reduced motion: one image, no control, no fade.
- Network with the cache off: an inner page fetches one scene file; home fetches the
  observatory first and the other two about 170 ms later; a phone at 3x gets the 1280 files only.
- The analytics panel solid (`rgb(5, 5, 10)`); the trophy pop-up dims the scene.
- Contrast from screenshot pixels behind every on-scene text block (text hidden): 74 blocks on
  five pages at 1920x1080, 1440x900 and 390x844, the worst 5% of each block's background at
  5.47 : 1 or better before the shadow is counted; none under 4.5. Before the chips, the Quiz
  points line and the Explore quota line measured 1.0 to 2.3 : 1 over the dome.

Gate (Vedant): the screenshots and the diff approved, then the commit and push; after the
deploy, `/scenes/*` is served with the long cache header and the scenes load under production's
CSP.

Committed on Vedant's word (`eb03598` the images and rules, `e5461c8` the layer, hero and sweep,
each passing every check on its own) and pushed on 2026-10-10. Deploy checks the same day,
read-only: every scene file 200 with its type and committed size, `Cache-Control: public,
max-age=31536000, immutable` and the security headers; the preload and `theme-color` in the
page. In headless Chrome on production: no CSP violation or console error; an inner page
fetches one scene file; home fetches the observatory first and the other two about 150 to
190 ms later; a phone at 3x gets the 1280 files only; turns at 0, 10.0, 20.2 and 30.0 s, held
by Pause and by a hidden tab. Vedant looks at it on production next.

### Session 10b - Public repo, domain and launch

Decisions to ask: the one-line tagline (OG card and README), the privacy page's wording and
contact address, and anything gitleaks finds.

Decided 2026-10-10 (Vedant, each as recommended):
- **Tagline:** "An astronomy quiz written by an AI agent that checks every answer against the
  pages it read." (the page's meta description already), on the OG card and in the README.
- **Privacy contact:** the contact form on the portfolio
  (`https://www.vedantgaikwad.ie/#contact`); no address is published.
- **The art credit:** "generated by Vedant Gaikwad with One Prompt Design", all rights reserved.
- **Local paths:** the three passages showing a Windows path (CLAUDE.md, DESIGN.md and
  CODE_REVIEW_SESSION9.md) now name the folders instead.
- **Fonts self-hosted:** Google Fonts sent every visitor's IP address to Google (a 2022 Munich
  ruling found that breaches the GDPR without consent). The three fonts are now served from
  `public/fonts/` (latin, latin-ext and greek WOFF2 subsets, the files Google serves, with
  each family's OFL licence); the CSP's `style-src` and `font-src` are `'self'` only.
- **LICENSE is the plain MIT text**, so GitHub shows MIT; `NOTICE` and the README say what
  it does not cover (the scene art and the link preview, all rights reserved; the fonts,
  under the OFL). This replaces the note inside LICENSE planned above.

Claude Code:
- [x] Docs read-through: Claude Code lists passages for Vedant to look at (names, emails, IDs,
      anything not meant for the public); Vedant reads `docs/` and `CLAUDE.md` and approves.
      Listed 2026-10-10: no email, key, project host, provider id or IP address; three local
      paths (replaced); spend figures and the TypeSafe balance (kept: they are the cost story).
      Vedant's own read is part of the review before the repo goes public.
- [x] History scan: gitleaks over every commit, plus the grep for key prefixes and `.env` names.
      Any real key found is rotated at its provider; the history is kept. gitleaks 8.30.1
      (checksum checked, run from the scratchpad): no leaks in 55 commits. No `.env` value
      appears anywhere in the history; the Supabase key prefixes appear only in test fixtures
      (`sb_secret_test...`); `.env.example` is the only env file ever committed. Nothing to
      rotate.
- [x] `LICENSE` (MIT, Vedant Gaikwad, 2026), and `NOTICE` for the scene art, the link preview
      and the fonts (decided above); the same note in the README.
- [x] README as decided, with the Mermaid diagram and the `agent_stats` note.
- [x] `/privacy` (a route in `src/router.ts`, a page, and a footer link on every page), with
      tests: the route, and a packaging test that holds the page's retention times to
      `purge_visitor_hashes()`.
- [x] OG image: the observatory scene with "COSMIC QUIZ" and the tagline in its sky, rendered
      to 1200x630 with headless Chrome (`public/og-v1.jpg`, a 138 KB JPEG rather than a PNG,
      for a photograph), and `og:` and `twitter:` tags in `index.html` with absolute URLs on
      the new domain. A packaging test checks the image's size and the tags.
Paused by Vedant on 2026-10-10: the repo **stays private** until a round of fixes (planned in
`docs/NEXT_SESSION.md`) and a session of its own for the README (the committed README is a
draft). He adds the `cosmic` CNAME later. Kept from the review: the "How it was built" line
(it was built with Claude Code) and the spend figures (cost matters to the story).

- [x] Vedant confirms, then the repo is made public (Vedant in GitHub's settings, or `gh repo
      edit --visibility public` on his word). Turn on secret scanning with push protection and
      Dependabot alerts (free on public repos). The header's GitHub icon links to the repo.
      Done on 2026-10-19 on Vedant's word ("go public"), in this order:
      - gitleaks 8.30.1 once more over every commit on every branch: no leaks in the 75 that
        carry text (the 76th changes only a screenshot); no key prefix in any patch;
        `.env.example` still the only env file ever committed.
      - `gh repo edit --visibility public`: the repo is public, and GitHub reads the licence as
        MIT.
      - Secret scanning and push protection enabled, and Dependabot alerts (the API answers
        204). Dependabot's automatic fix pull requests are left off; they were not asked for.
      - Description (the tagline) and homepage (`https://cosmic.vedantgaikwad.ie`).
      - The held header commit brought onto `main` (`3389a49`, cherry-picked from
        `held/header-link`, which is deleted) and pushed: production served the new build about
        60 s later, with the icon linking to the repo; the checks run on it passed.
      - Signed out (plain requests, no GitHub login): the repo page, the checks workflow's page,
        `docs/DEVELOPMENT.md` and a README screenshot answer 200, and the badge reads "Checks -
        passing".
- [x] Domain: add `cosmic.vedantgaikwad.ie` to the Vercel project; Vedant adds the CNAME
      `cosmic` at Web Hosting Ireland with the value Vercel shows; then redirect
      `cosmic-quiz-agent.vercel.app` to it. Check deep links, the API and the live search on the
      new domain.
      Decided 2026-10-13 (Vedant, each as recommended): the domain comes first, then the README
      session, then going public; the old address redirects in `vercel.json` (a permanent 308
      that matches only the host `cosmic-quiz-agent.vercel.app` and keeps the path and query,
      held by a packaging test), deployed only once the new domain answers over HTTPS.
      Done on 2026-10-13:
      - **DNS:** the domain was added to the project at 14:12 UTC (Vercel CLI), and Vedant added
        `cosmic` CNAME `cname.vercel-dns.com` (TTL 14400). Google's and Cloudflare's resolvers
        returned it by 14:21 UTC. (That session's check of the four nameservers went through
        this PC's VPN, which answers every DNS query itself; Google, Cloudflare and Let's
        Encrypt confirm the record independently.)
      - **The certificate waited on Vercel's own DNS check,** which still found no CNAME at
        14:40 (`cnames: []`, `misconfigured: true`). HTTPS failed with no certificate (Chrome:
        ERR_CONNECTION_CLOSED) while plain HTTP already served the site. Ruled out: a CAA
        record (none; the CNAME target allows Let's Encrypt) and DNSSEC (off). Most likely
        Vercel's first lookup, made before the record existed, was cached: the zone lets a "no
        such name" answer be cached for up to a day. Vedant pressed Refresh on the Domains
        page, then `vercel certs issue` followed (the CLI answered "Response Error"); Let's
        Encrypt issued the certificate at about 14:54 UTC (90 days, renewed by Vercel), and
        the config check then read `misconfigured: false`.
      - **Checked on the new domain,** read-only: `/`, `/learn/quasars`, `/explore/stats` and
        `/privacy` answer 200 with the six `vercel.json` headers; `/api/topics` and
        `/api/quota` 200; `/og-v1.jpg` is the 1200x630 JPEG; S1 holds (a cross-site GET 403,
        a `text/plain` POST 415). Headless Chrome on eight pages and the home page at phone
        size: no CSP violation, console error or blocked load; the fonts, the scenes and every
        API call from the new domain, and no other host.
      - **The redirect,** committed on Vedant's word (`bfff85e`, with the docs in `b60c97c`)
        and pushed at 14:57 UTC. Production then redirected every path except the home page:
        Vercel matches a source strictly, so `/:path*` misses `/` (and any path ending in a
        slash). The old home page was still served, and its API calls were redirected to the
        new domain and refused there as cross-site. Traced with the matcher Vercel's build
        uses (path-to-regexp in strict mode, in the CLI's own folder) and fixed with
        `/:path(.*)` on Vedant's word (`9366531`, pushed at 15:12 UTC).
      - **The redirect on production:** `/`, `/?ref=x`, `/learn/`, `/learn/quasars?x=1`,
        `/api/topics`, `/privacy` and `/og-v1.jpg` on the old address each answer 308 to the
        same path and query on the new domain; the new domain is not redirected (no loop); a
        browser lands there in one hop, with no CSP violation or error. Deployment URLs keep
        Vercel's login wall (a 302 to its SSO), untouched by the rule.
      - **Vedant on his iPhone** (Safari, the new domain): it works, a live search included
        ("Wormhole", 15:30 UTC). Its 4 runs, checked read-only: the easy, medium and hard
        questions first, then the explanation; item 208 published, 209 discarded, 210 in
        review, 211 (the explanation) published; $0.103 on Anthropic and $0.0008 on TypeSafe,
        197 s and 10 pages; `spent_usd` equal to each run's cost.
- [x] The link shared in WhatsApp shows the preview (the image, the title and the tagline).
      Checked by Vedant on 2026-10-13 (15:54 UTC): the card shows the observatory image with
      "COSMIC QUIZ" and the tagline, the title "Cosmic Quiz", the tagline as its description,
      and `cosmic.vedantgaikwad.ie`.
- [x] The README session (a session of its own, next). Decided 2026-10-13 (Vedant, each as
      recommended, asked one at a time):
      - **Reader:** recruiters first, then engineers. The first screen stands on its own for a
        30 to 60 second skim; everything below it is for the engineer who opens the code.
      - **Length:** about the draft's depth, with a sharper first screen: the tagline, the live
        link, the link-preview image, three highlights with numbers, and the stack.
      - **The three highlights:** it checks itself (citations only from fetched pages, enforced
        in code; three checks; 38 of 40 planted faults kept from players); it runs on its own
        (the model chooses its tools in a hand-rolled loop, and a scheduled job grows the bank
        every day); it is live at a capped cost (a visitor watches a search, about $0.12, under
        the $10 a month cap, with every call's cost logged).
      - **Kept from the draft:** the gate table and the costs, the Mermaid diagram, and security
        and privacy.
      - **Moved:** the run-locally steps and the repo map, to a new `docs/DEVELOPMENT.md` that
        the README links to.
      - **Visuals:** the link-preview image at the top, and three screenshots beside the
        sections they show (a quiz answer with its source check, the agent log streaming a live
        search, Analytics for nerds), made with headless Chrome as small WebP or JPEG files
        under `docs/images/`. `NOTICE` names them, since they show the scene art.
      - **Voice:** neutral, with one first-person line near the top on why Vedant built it.
        "How it was built" stays (decided 2026-10-10).
      - **CI** (asked after the session's other questions, as recommended): a second workflow,
        `.github/workflows/checks.yml`, runs every check on each push and pull request
        (pytest, ruff, ruff format, mypy --strict, typecheck, Vitest and the build), with no
        secrets and no paid calls, actions pinned to commits and read-only permissions as in
        the Curator; the README shows its badge. Free: Actions minutes are free on a public
        repo, and a run is a few minutes of the 2,000 a month on a private one. Until now
        every check ran only on Vedant's PC.

      Decided at the start of the README session (2026-10-13, Vedant, asked one at a time, each
      as recommended except where marked):
      - **The "I" line:** in his own words, tightened. His reason is his love of astronomy; the
        line is drafted from that for him to edit.
      - **The agent-log screenshot:** a live search on production, on a topic the bank did not
        have: "James Webb Space Telescope" (EASY).
      - **Security and privacy:** a few lines each, with links to `docs/SECURITY_AUDIT.md` and
        `/privacy` (not the recommendation, which kept the security bullets in full).
      - **pnpm on CI:** `"packageManager": "pnpm@11.5.0"` in `package.json`, read by
        `pnpm/action-setup` (v6.1.0, pinned to its commit) after `actions/setup-node` (v7.1.0).
        Corepack was turned down: Node 25 and later no longer bundle it.
      - **The rendering check:** GitHub's markdown API turns the README into GitHub's own
        HTML, shown in a scratchpad page with GitHub's stylesheet and mermaid.js from cdnjs
        (free; neither enters the repo). The final check is on github.com after the push.

      Built in the README session (2026-10-13):
      - [x] `README.md` rewritten as decided: the badge, tagline, live link and link-preview
            image; the three highlights and the stack; the "I" line; what you can do; the
            diagram (now top to bottom: the left-to-right draft drew at 800 x 127 px, too
            small to read); the agent, the gate table and live numbers, the guardrails, the
            costs, security and privacy in a few lines each, and links to the docs.
      - [x] `docs/DEVELOPMENT.md`: what you need, setup with every environment variable, the
            database, each command and its cost, the checks, deploying, and the repo map.
      - [x] `docs/images/`: three WebP screenshots of production at device scale 2, made with
            headless Chrome: `quiz-answer.webp` (The Big Bang, EASY, with Jev's source check),
            `agent-log.webp` (the live search 19 s in) and `analytics.webp` (Analytics for
            nerds, The agent tab, cropped to the four key figures). 193, 72 and 64 KB.
      - [x] `NOTICE` names `docs/images/` (all rights reserved), and the README's licence note
            says so.
      - [x] `.github/workflows/checks.yml`: a Python job (pytest, ruff check, ruff format
            --check, mypy --strict) and a site job (pnpm install --frozen-lockfile, typecheck,
            Vitest, build); `permissions: contents: read`, `persist-credentials: false`, every
            action pinned to its release commit, no secrets.
      - [x] `package.json`: the `packageManager` field.

      The live search, read from its "This search" tab: 4 of 4 items published, $0.097 ($0.00093
      of it on Jev), 85.6 s of runs and 11 pages from 3 sites; 93 s in the browser. This PC had
      one of its 2 searches left (Vedant's iPhone "Wormhole" search shared its address). A fresh
      Chrome profile earned the "Web researcher" trophy with the first result, and its pop-up
      covered the log from 21 s on, so the screenshot is the snapshot at 18.9 s, before it. The
      finished log, scrolled to the first question's checks, is kept in the scratchpad as the
      alternative.

      Checked:
      - Every number in the README against its source: `docs/EVALS.md` (the gate table, 38 of
        40), `docs/DESIGN.md` and `agent/limits.py` (the guardrails; the $0.17 reservation is
        `max_job_cost_usd`, the agent's $0.10 plus the verifier's cap), `agent/gate.py` (the
        publish rule), the security audit (19 findings: 5 Medium fixed), and the live
        `/api/stats` at 16:29 UTC (213 runs, 115 published directly, 80 review, 17 discarded;
        $5.89 in all; median 19.2 s, p95 36.2 s; caching saved $1.63 of $6.42), which the
        analytics screenshot shows.
      - Three claims in the draft README were wrong and are corrected: the loop is not "about
        150 lines" (`run_agent` is 120 lines; `agent/loop.py` about 300 lines of code); Jev
        checks each claim against the full text of the cited pages, not "its quoted passage";
        and an item does not need Jev "at 0.8 or above" on everything: the right answer needs
        support at 0.8, a wrong option must not be supported and no sentence contradicted,
        while sentences Jev says nothing about are allowed. The draft's "43% publish
        directly" was 22 of the 51 eval items that passed layer 1; the README now gives the
        live figure, 54%. `CLAUDE.md` and `DESIGN.md` decision 12 said "about 150 lines" too;
        fixed on 2026-10-13 (below).
      - The README and `docs/DEVELOPMENT.md` as GitHub renders them ("markdown" mode, as for
        files), at 1280 px and 390 px, light and dark: the diagram drawn (521 x 775 px), every
        image loaded, no sideways scroll on a phone. Every relative link resolves; the badge
        and the workflow link answer 404 until the push (the repo is private).
      - Every relative import and asset path resolves with its exact case (the runner's file
        system is case-sensitive; this PC's is not). The tests read no secrets and make no
        network calls.
      - 341 Python and 148 TypeScript tests, ruff, ruff format, mypy --strict, typecheck and
        the build; `pnpm install --frozen-lockfile` leaves the lockfile unchanged with the new
        field.
      - Vercel's build log (16:01 UTC) says it used pnpm 10.28.0 "based on project creation
        date" and that `packageManager` sets the version, so the next build should use 11.5.0.

      Vedant read the README and kept the "I" line as drafted. Committed on his word as three
      commits (`4883f3c` the checks workflow and the `packageManager` field, `52b98d2` the
      README, `docs/DEVELOPMENT.md`, the screenshots and `NOTICE`, then these records) and
      pushed the first two at 17:38 UTC. After the push:
      - **The first run of the checks workflow passed** (run 38440315065, on `52b98d2`): both
        jobs green on Ubuntu, in 28 s (the site) and 42 s (Python); 341 Python tests, 13
        Vitest files, ruff, ruff format, mypy --strict and the build, with pnpm 11.5.0 on Node
        24.21.0. Two notices only: `ubuntu-latest` moves to Ubuntu 26 from 19 October 2026
        (both workflows). The site job logs a pnpm warning about a v10 layout in `PNPM_HOME`;
        it refreshes the shims itself and installs with 11.5.0, so it is harmless.
      - **Vercel built with pnpm 11.5.0** ("from package.json#packageManager"), and production
        serves the same asset files as the local build, with the six headers; `/api/topics`,
        `/api/quota` and `/og-v1.jpg` answer 200, and the old address still answers 308.
      - Still Vedant's: the README on github.com (the diagram, the images and the badge, on a
        computer and his phone). The badge and the workflow link answer 404 to anyone signed
        out until the repo is public.

      After the README (2026-10-13, Vedant's requests):
      - **README edits:** his job title removed from the "Built by" line, and a Contact section
        sends any request for more details to the contact form on vedantgaikwad.ie.
      - **Renamed "Analytics for nerds" to "Mission Control"** (he asked for suggestions and
        chose it; the others were Under the Hood, Flight Recorder and Observatory Logbook):
        the button on the web page, the panel's title and heading, the privacy page, the code
        comments, `CLAUDE.md`, `DESIGN.md` and the README. This record, the migrations and the
        Session 9 code review keep the old name, as history. Committed as `024f0fe`, and the
        README's screenshot was retaken on the deployed build (`1339fe1`; the figures were
        unchanged).
      - **A prompt for his portfolio's own Claude Code session** to add this project there,
        written in the why, what, how, when and where form with the stack and the headline
        numbers; it asks that session to match the site's theme and to ask before publishing a
        code link that would 404 while the repo is private.
      - **Docs completed:** the loop's length corrected to "about 120 lines" in `CLAUDE.md`
        and `DESIGN.md` decision 12; `CLAUDE.md` names the checks workflow and the pnpm pin;
        the `DESIGN.md` repo layout lists `checks.yml`, `docs/DEVELOPMENT.md` and
        `docs/images/`, and its `NOTICE` line the screenshots.
      - **History scan before going public** (gitleaks 8.30.1, the same binary and checksum
        as on 2026-10-10): no leaks in the 71 commits that carry text (the 72nd changed only a
        screenshot); no key prefix, `.env` value or salt in any patch; `.env.example` is still
        the only env file ever committed. A scan of `docs/`, `CLAUDE.md` and the README found
        no email address, IP address, Windows path, project id or key.
      - **The header's GitHub icon** now points at the repo (`GITHUB_URL` and its label in
        `src/components/SiteHeader.tsx`); the other commit is held, not pushed, so visitors
        are not sent to a 404 while the repo is private. 341 Python and 148 TypeScript tests,
        and every other check, pass with it.

Gate (Vedant): the repo public and clean (gitleaks clean, or every key it found rotated), the
site at the new domain with the old address redirecting, the OG preview right where he shares
it, the privacy page, and the README readable to someone who has never seen the project.

Gate passed on 2026-10-19: the repo public with gitleaks clean, the site at
`cosmic.vedantgaikwad.ie` with the old address redirecting, the preview checked in WhatsApp,
the privacy page, and the README, which Vedant read before giving the word. That closes
Session 10b and version 1.

### Fixes and design questions (2026-10-10, after 10b's pause)

Planned in `docs/NEXT_SESSION.md` at the end of 10b. Vedant described the scroll bugs first, on
an iPhone with Safari: on the web page the page pulls him back up while he answers a question,
and on the home page scrolling stutters, the content shifts and the slideshow's fade stutters.
Back and Forward work, and the analytics panel is fine (his note about it was the web page).

Decided (Vedant, each as recommended, asked one at a time):
- **The web page's order:** the questions first and the explanation last, on the server too
  (`plan_search`): the first question comes at about 20 s instead of about 40 s. The reason is
  that the explanation can give answers away. The trade-off, accepted: when the $0.50 daily cap
  or the 3-minute cutoff cuts a search short, the explanation is what is left out. Each answer
  still shows its own explanation and sources.
- **When the explanation opens:** once every question the search shows is answered or left
  out, and the explanation is ready; a search that made no question opens it as soon as it is
  ready. Opening it counts towards Explorer (not its arrival).
- **Learn:** the difficulty switch, search and Random in one solid bar that sticks to the top
  while the grid scrolls. A box that scrolls on its own and a sideways carousel were turned
  down: the box traps the page's scroll on a phone, and the carousel hides most topics.
- **Saving progress:** accounts in v2, decided with the newsletter; nothing built now. A save
  link (no server) and an anonymous cloud save were the other options. Checked:
  `navigator.storage.persist()` does not stop Safari's 7-day deletion (it only guards against
  eviction when space runs low, and Safari usually refuses it in a tab).
- **The iPhone check:** Vedant tests the fixes on his phone over his Wi-Fi before the commit.

Reproduced first (headless Chrome over the built `dist/` with every `vercel.json` header, and a
scratchpad stub of the API: fake agent runs with a dozen log lines each, nothing spent):
- **The web page:** once the reader scrolled to the question, the next log line pulled the
  window back to the log: from 1780 to 1134 px at 1440x900 (the question's top at 863 of 900)
  and from 2408 to 1210 px at 390x844 (the question off screen), and it stayed pinned to the log
  with every line until the search ended, about 22 s. Cause: `AgentLog` called `scrollIntoView`
  on its last line, which scrolls the window as well as the log's box.
- **Home at phone size,** Safari's toolbar simulated by changing the viewport from 664 to 745 px:
  the hero grew 81 px, the progress card moved down 81 px, and the scene layer resized, so the
  scene dropped 81 px; all of it came back with the toolbar. Causes: the hero's `100dvh` and the
  scene layer's `inset: 0`.
- **The fade:** Chrome cannot show it. Traced around one turn alone, Chrome paints the same
  before and after the fix (2 paints). The likely cause on an iPhone is WebKit making a layer,
  and on phones a mask, for an image when its fade starts; only the phone can confirm the fix.

Built:
- [x] `agent/ondemand.py`: `plan_search` puts the questions first and the explanation last;
      `tests/test_ondemand.py` follows the new order (a search cut short now loses the
      explanation first).
- [x] `src/search.ts`: `explanationLock()` (locked with the questions left, coming, open, or
      left out), 6 tests. `src/scroll.ts`: `atEnd`, `stillFollowing` and `startsOffScreen`, 8
      tests.
- [x] `src/components/AgentLog.tsx`: new lines scroll the log's own box, only while the reader
      is at its end; the window is never moved.
- [x] `src/pages/ExplorePage.tsx`: the questions, then the explanation behind "Read the
      explanation" (the reason it is locked, or why it was left out); after the last answer,
      Next reads "Read the explanation"; Next brings the next question into view when it starts
      off screen, and the opened explanation is brought into view; Explorer counts on opening;
      the intro and hints say the new order. A topic the bank has in full uses the same order.
- [x] iPhone: the hero's minimum height in `svh` and the shell's in `min-h-svh`; the scene
      layer `top: 0; height: 100lvh`, so it never resizes; every scene image on its own layer
      (`will-change: opacity`); on phones one gradient band over the images instead of a mask on
      each (the same look). `tests/test_packaging.py` holds all of it (2 new tests).
- [x] `src/pages/LearnPage.tsx`: the sticky bar (one row from 768 px, two on a phone); the
      topic cards keep clear of it when keyboard focus scrolls to them.
- [x] Docs: DESIGN.md decisions 4 and 9 and the player-state default; this record.

Checked: 340 Python tests (2 new) and 148 TypeScript tests (14 new); typecheck, build, ruff and
mypy --strict. Driven in headless Chrome over the built site with the `vercel.json` headers:
- A live search at 1440x900 and 390x844 (28 checks): the first question at 12 s with the stub;
  the explanation locked below the questions; the window never moved while 8 or 9 log lines
  arrived; the log's box followed its newest line, and stayed where the reader scrolled it;
  questions 2 and 3 brought into view by Next; no Explorer credit until the explanation was
  opened, which brought it into view.
- Every page at 1920x1080, 1440x900, 1024x768, 768x1024 and 390x844 (37 checks): no sideways
  scroll; the Learn bar stuck at the top (74 px tall, 130 px on a phone); a topic the bank has
  in full shown free in the same order; no CSP violation or console error. Shift+Tab back up the
  grid kept each focused card at least 30 px below the stuck bar.
- The scene at 390x844: the CSS as intended; a scroll repaints nothing; the band against the old
  mask on production, the content hidden: at most 5 levels apart (mean 0.47) across the band.

Gate (Vedant): the fixes on his iPhone over his Wi-Fi (the web page while a search streams, the
home page's scroll and fade, the Learn bar), the screenshots and the diff; then the commit and
push on his word, and the same checks on production.
- [x] iPhone check passed on 2026-10-12, on Vedant's word ("it works"): the built site served on
      his PC's home-network address with the free stub API.
- [x] Committed on his word as three commits (`5ce29d6` the scroll fixes, `ebf68d8` the
      questions first, `71a5712` the Learn bar and these docs), each passing every check on its
      own.
- [x] Pushed on his word on 2026-10-12. Vercel deployed it to production at 15:33 UTC, about
      15 minutes after the push. Production serves the exact build tested locally (the same
      asset files), checked read-only in headless Chrome: the new scene CSS (`100lvh`, no
      mask), the explanation button, the Learn bar, and no CSP violation or console error.
- Seen on 2026-10-12: for a while Vercel's Security Checkpoint answered every non-browser
  request with HTTP 403 (`x-vercel-mitigated: challenge`); browsers passed it. By 2026-10-13 it
  was off again (the home page, the link preview's image and `/api/topics` answer 200, also to
  a Facebook crawler's user agent), so it was Vercel's automatic protection, not a setting.
- [x] Vedant's iPhone check on production: moved to the domain step, as one check on the new
  domain. Passed on 2026-10-13, on Vedant's word, with a live search (see 10b's domain item).


### The difficulty dropdown (2026-10-17)

Vedant, from his iPhone on the Learn page: the difficulty should be a dropdown. Asked which change
he meant (with mockups), he chose the recommendation: the EASY / MEDIUM / HARD switch becomes one
dropdown on every page that has it (Learn, each topic, Quiz and Explore). The other options were
every switch a dropdown (Quiz's 10 / 30 / 60 and Mission Control's filters too) and Learn grouped
in Easy, Medium and Hard sections.

Built:
- [x] `src/components/Dropdown.tsx`: a native `select` (no dependency), so a phone shows its own
      picker and the keyboard and screen readers work as everywhere. It lies invisibly over a face
      in the site's style (the choice as a teal pixel label and a pixel chevron, a solid card) with
      16px text, so iOS never zooms; the face takes the teal focus ring for the keyboard. Levels a
      topic lacks are disabled options.
- [x] Learn: the bar is one row at every width (the dropdown, the search box and Random); on a
      phone Random shows only its die and keeps its name for screen readers, and the placeholder
      is "Search topics". Each topic page, Quiz (beside its "Difficulty" label) and Explore (with
      a "Difficulty" label) use the same dropdown. Quiz's run length and Mission Control's filters
      stay as switches.
- [x] `tests/test_packaging.py`: no input, select or text area may have text under 16px (iOS
      zooms into it and does not zoom back). It found one: the Report box was 14px; now 16px.

Checked: 342 Python and 148 TypeScript tests, ruff, ruff format, mypy --strict, typecheck and the
build. A drive of the built site with every `vercel.json` header (the real bank through the local
API, nothing spent), 36 checks at 1280 x 900 and 390 x 844: the Learn bar one row (74 px tall on a
phone, against 130 px before), the search box at least 120 px wide, 16px select text, Random's
name, choosing a level updating the face and the list, the focus ring, a topic's missing levels
disabled (Antimatter: EASY only), Quiz and Explore taking the choice, no sideways scroll, and no
CSP violation or console error.

Pushed on Vedant's word ("push this edit"), as the code with its test and then these records.
The header-link commit, still held until the repo is public, would have gone out with any push
from `main`, so it was moved to the local branch `held/header-link` (it had never been pushed)
and `main` reset to `origin/main` before these commits.

---

## Later - v2: Newsletter
Planned in detail once v1 is live. Curator email output via Resend (portfolio `api/contact.ts`
pattern), subscribers with double opt-in and unsubscribe, then WhatsApp. (Changed 2026-10-08 by
Vedant: the analytics page, the other v2 feature, moved into v1 as Session 9.) Also accounts,
so players keep their progress across devices (Supabase Auth, passkeys or email links, free
tier), decided together with the newsletter's subscribers (Vedant, 2026-10-10).

---

## Session log
- 2026-10-01 - Session 0: read the handoff, checked Vercel and OpenRouter docs, switched to Claude Haiku 4.5
  (swappable provider, $10/month cap, local-first with Supabase), wrote this plan, created the private
  GitHub repo and pushed the first commit. Next: Vedant creates the Anthropic API key and $10 spend limit,
  then Session 1.
- 2026-10-01 - Session 1: amended DESIGN.md and CLAUDE.md for the switch to Haiku 4.5; built the
  skeleton (Python 3.12 venv, pinned deps, ruff + mypy --strict clean), the provider interface, the loop,
  three tools and the citation check. Spike: 3/3 passed, $0.057 total ($0.019 per run), caching saves
  25-35% on runs of 4+ calls; 2 of 13 quotes were not verbatim and one explanation had a numeric error
  (see docs/SPIKE.md). Next: Vedant's gate (run the spike command, check Console spend), then Session 2.
- 2026-10-01 - Session 1 (continued): adopted TypeSafe Jev as a second-opinion verifier (EUR 5 balance).
  Smoke test: right on a supported and an unrelated claim, missed the numeric error at 0.86. Plan updated:
  the publish gate is three layers (code checks, Haiku, Jev); Jev's confidence is stored per claim and
  shown in the UI; the Session 3 evals measure each layer on a seeded-error set; Jev is the candidate for
  the Session 6 on-topic check.
- 2026-10-01 - Session 2: decisions recorded (allow-list, no web search, length by difficulty). Added
  search_arxiv, fetch_feed, nasa_apod and search_nasa_images; a shared HTTP helper with retries; QuizItem
  and the run models in schemas.py; a code-enforced word range; 77 unit tests (pytest, no network). Three
  verification runs passed using the new tools (arXiv abstract, ESA/Webb and NASA feeds, NASA images),
  11 of 12 quotes verbatim, $0.070 including one re-run. Next: Vedant's gate (LEARN on 3 topics of his
  choice), then Session 3.
- 2026-10-01 - Session 3: QUIZ mode, the three-layer publish gate (code checks as hard rules with one
  correction round; Haiku verifier with its own quote re-checked in code; Jev claim checks pinned to
  jev-1.13.0) and pure publish rules re-scorable from stored results; evals with a 60-item run, a
  40-item planted-error set and a report. The eval exposed text-matching artifacts (empty Wikipedia
  brackets, zero-width characters, dash variants, arXiv LaTeX), now fixed. Vedant chose all_must_pass
  at threshold 0.8 after his hand review. 136 tests. Spend about $2.11 Anthropic, $0.02 TypeSafe.
  Next: Session 4 (Supabase bank and Curator).
- 2026-10-02 - Session 4: Jev criteria made astronomy-specific (astro-1, Jev-only re-check $0.022);
  a verifier misquote now goes to review instead of discard (same 38/40 planted faults handled);
  supabase/schema.sql (RLS: the publishable key reads only published items), agent/store.py over
  REST with no new dependency, and the Curator (build and daily, dollar cap, unstored runs kept on
  disk). Bank built: 30 topics, 99 published, 66 review, 14 discarded, $4.98 Anthropic and $0.041
  TypeSafe including the trial. Then a review command so items are approved with their sources
  in view (the table editor does not show them), and two code reviews (30 findings, all fixed:
  a hard dollar cap, idempotent storage, the citation rule in stored rows, exact cost logging).
  Migrations 002 and 003. Gate passed: Vedant decided 28 items (26 published). 194 tests.
  Next: the review-queue decision (Haiku's explanation doubts block most of the 38 left), then
  Session 5.
- 2026-10-08 - Session 7: moved to the cloud. The Vercel streaming spike passed (WSGI functions
  stream line by line, a run whose player left is still stored and settled, forged
  X-Forwarded-For is ignored; see docs/SPIKE.md), and the app is live at
  https://cosmic-quiz-agent.vercel.app in the dub1 region, next to Supabase. The Curator runs
  daily on GitHub Actions with left-over runs kept in the Actions cache: free `upkeep` until
  2026-11-01, then paid `daily`. A rejected TypeSafe secret sent the gate run's 6 items to
  review without Jev checks; the new `python -m curator rejev` (migration 005) re-checked them
  from the stored page text, and 5 were published ($0.0011 on TypeSafe). Gate passed: Vedant
  played the white-dwarf topic on the live site. Bank: 171 published, 4 review (186, 187, 188,
  193), 16 discarded. 250 tests. Next: Session 8 (pages, router and trophies).
- 2026-10-08 - Session 8 (in progress): closed Session 7; recorded the grill-me decisions
  (Sessions 8 to 10, the analytics page into v1, the public repo with MIT, the subdomain) in
  PLAN.md, DESIGN.md and CLAUDE.md. Built pages and a History-API router, tiered trophies with a
  pop-up, quiz runs of 10/30/60 with End run, profile v2 (v1 badges become bronze) and
  `/api/quota`, after Vedant approved the trophy list (Speed runner needs 70% right) and a mock.
  58 TypeScript and 258 Python tests. Committed and pushed; production serves the deep links.
  A second grill-me then changed the web page: a search makes the explanation and a question at
  each level, 2 searches a day per visitor and 4 for everyone, one run at a time (see "The web
  page makes whole topics" under Session 8). Next: a new session builds that change (migration
  006 first), then the Session 8 gate.
- 2026-10-08 - Session 8 (continued): built the searches change. Migration 006 (a search id on
  live runs; the daily limits count searches, the dollar caps every run), the limits and quota
  in searches, `agent/ondemand.py` as a search of up to 4 runs one at a time with a plan event
  and per-item events, and the web page without the LEARN/QUIZ switch. Two conflicts flagged and
  decided by Vedant: late runs get a shorter agent budget so a search ends under 300 s, and the
  caps stay (the day's 4th search may end early). 268 Python and 73 TypeScript tests; a no-cost
  drive of the page passed 39 checks. No paid calls. Next: Vedant pastes 006, then the Session 8
  gate.
- 2026-10-08 - Session 8 (continued): Vedant applied 006; a probe of the new function and the
  quota read passed against the real database, and production kept working through the 004
  function. The local TypeSafe key is rejected (HTTP 401), so Vedant chose to check the live
  searches on production. Committed (`823c2ea`, docs `4d5fd8f`) and deployed; free checks on
  production passed. The live-search check moves to the end of Session 9. Next: Session 9.
- 2026-10-08 - Session 9 (in progress): Vedant took the recommended option on all six decisions
  (summary first, all time with 7/30 days, This search as a whole then run by run, the 2 x 3
  grid, the latest eval as a static section, no player statistics in v1). Built migration 007
  (`agent_stats`, aggregates only; drops the 004 function), a `stats` event per live run,
  `/api/stats`, `python -m evals export`, and the panel at `/explore/stats` with hand-written SVG
  charts. 290 Python and 109 TypeScript tests; a no-cost drive passed 42 checks. No paid calls.
  Then, after a grill-me session, the panel opens on four key elements per tab (quality, cost,
  speed and budget; cost, made, time and pages) with everything else in closed rows and the
  filters behind one button. 112 TypeScript tests; a second drive passed 39 checks. Next:
  Vedant pastes 007, then the comparison, the Session 9 gate and the live searches.
- 2026-10-09 - Session 9 (continued): a code review found 7 items, none critical; they are
  filed in `docs/CODE_REVIEW_SESSION9.md` for the next session. Vedant applied 007; the live
  `agent_stats()` matches the Python re-implementation on 7 filter sets and `/api/stats`
  answers 200. Committed on Vedant's word (`90ff820` migration 007, `6376826` the server side,
  `619c5e9` the panel, then the docs) and pushed to deploy. What is left, and the prompt for the
  next session, are in `docs/NEXT_SESSION.md`. Next: Vedant checks the panel on production and
  runs the two live searches; then the review fixes and both gates.
- 2026-10-09 - Session 9 (continued): fixed all 7 code review items (item 4 as the comparison
  only, on Vedant's choice: `python -m dev.check_stats`, read-only, 7 of 7 filter sets the
  same). The drive caught one regression in the item 5 fix (Esc could go Back twice), fixed
  before the end. 302 Python and 114 TypeScript tests, all checks clean, a drive of 24 checks
  against the local servers; no paid calls. The live searches are not run yet, so the Session 8
  and 9 gates stay open. Planned Session 10 as two sessions (10a audit and fixes; 10b history
  scan, public repo, domain, README, OG image, privacy page), with Vedant's eight decisions
  recorded under Session 10. Not committed yet. Next: Vedant runs the live searches, then 10a.
- 2026-10-09 - Session 9 (closed): committed the review fixes and the Session 10 plan on
  Vedant's word (`87d1b0e`, `8daf4d5`, `14a07b2`, `d1e5b18`, `f413fb5`; not pushed). Vedant ran
  a live search on production (Antimatter: 2 runs, one item in review, $0.067) and reports the
  searches work; `on_demand_runs` checked read-only (the search id link, `spent_usd` set and
  equal to each run's cost), and the "This search" tab matched the stored runs. Session 8 and 9
  gates recorded as passed. Next: Vedant runs the second search (a new topic), then 10a.
- 2026-10-09 - Session 9 (after close): pushed and deployed. Vedant ran the second search ("Red
  light shift index", 4 runs, $0.152, 2 items in review, then the limit message); its runs check
  out read-only and match his screenshots of "This search". Fixed "1 pages" in a run row. Next:
  Session 10a.
- 2026-10-09 - Session 10a (in progress): Vedant took the recommended option on the three
  starting decisions (pip-audit dev-only, report hashes cleared after 30 days, headers checked
  locally first). The audit recorded 19 findings in `docs/SECURITY_AUDIT.md`: none High, 5
  Medium, 10 Low and 4 Info. Fixed on Vedant's choice: S1 to S5, S13 (migration 008) and S17;
  the other Lows are accepted for now, and S15 is accepted. `pnpm audit` and pip-audit are
  clean, the Actions logs hold nothing private, and the live RLS probe passed. 330 Python and
  116 TypeScript tests. No paid calls. Not committed. Next: Vedant runs the SQL editor query and
  pastes 008, then the commit, the push and a header scan of production (the 10a gate).
- 2026-10-10 - Session 10a (pushed): Vedant applied migration 008 and ran the SQL editor
  query (its results still to paste); 10a committed on his word as ten commits, one per finding,
  and pushed. The production header scan passed (details under 10a). Next: the scenes step.
- 2026-10-10 - Scenes step: Vedant took the recommended option on the six open questions and
  approved a mock of the hero; the mock and a first drive led to four more decisions (the portal
  left out, the progress in one card, a "Your progress" chip, small lines on solid chips). Built
  as planned; 334 Python and 134 TypeScript tests. Vedant approved the screenshots; committed
  and pushed on his word. Next: the deploy checks and Vedant's look at production; then 10b.
- 2026-10-10 - Session 10b (in part, same session): Vedant took the recommended option on each
  decision (the tagline, the portfolio's contact form, "One Prompt Design", replacing three
  local paths, self-hosting the fonts, LICENSE plain with a NOTICE). The history scan was clean.
  Built `/privacy` with a footer link, the self-hosted fonts (CSP `'self'` only), the link
  preview, LICENSE, NOTICE and a draft README; 338 Python and 134 TypeScript tests. The 10a
  production scan and retention counts are recorded. Committed and pushed on his word; the
  repo stays private. Next: the fixes and design questions in `docs/NEXT_SESSION.md`.
- 2026-10-10 - Fixes and design questions: Vedant described the scroll bugs (iPhone Safari) and
  took the recommended option on each decision (questions first on the server too, the
  explanation opening after every answer, a sticky bar on Learn, accounts in v2). Both bugs
  reproduced in headless Chrome first (the web page's jump of 646 px and 1198 px; the home page
  shifting 81 px with the toolbar). Built the fixes, the new order and the bar; 340 Python and
  148 TypeScript tests; drives of 28, 37 and 8 checks (one scene check, paints during a turn, is
  not something Chrome can show). No paid calls. On 2026-10-12 Vedant checked the fixes on his
  iPhone over Wi-Fi ("it works"); committed on his word as three commits and pushed the same
  day (deployed at 15:33 UTC; production checked read-only). Next: the domain, then the README
  session, then going public.
- 2026-10-13 - Session 10b, the domain: `cosmic.vedantgaikwad.ie` had no certificate because
  Vercel's own DNS check still saw no CNAME (most likely a lookup cached from before the record
  existed); after Vedant's Refresh and `vercel certs issue`, Let's Encrypt issued it at about
  14:54 UTC. Every read-only check passed on the new domain (pages, headers, API, link preview,
  S1, headless Chrome). The redirect from the old address was committed and pushed on Vedant's
  word (`bfff85e`, docs `b60c97c`); production showed `/:path*` misses the home page in
  Vercel's strict matching, fixed with `/:path(.*)` (`9366531`) and checked on 9 paths. Vedant
  checked the site on his iPhone, a live search on "Wormhole" included (4 runs, $0.103, item
  210 to review). He pasted the SQL editor tables: S18's timeout is 3 s and S19 is accepted
  (Supabase's RLS event-trigger function; two trigger functions keep the default grant, also
  harmless). S13's counts after the purges recorded. Planned the README session in seven
  questions (each as recommended), and Vedant added a CI workflow for every check to it. 341 Python and 148 TypeScript tests. About $0.10 spent (the
  search). Vedant shared the link in WhatsApp: the preview shows the image, the title and the
  tagline. Next: the README session, then going public.
- 2026-10-13 - Session 10b, the README session: Vedant decided the five open questions (his own
  reason for the "I" line, a live search on production for the log screenshot, security and
  privacy in a few lines each, `packageManager` with `pnpm/action-setup`, the rendering check
  in a scratch page). Built the new README, `docs/DEVELOPMENT.md`, three screenshots of
  production, the NOTICE line, the checks workflow and the `packageManager` field. Checking the
  numbers corrected three claims carried over from the draft (the loop's length, what Jev reads,
  the Jev rule). The diagram is now top to bottom. 341 Python and 148 TypeScript tests. $0.097
  spent (the live search). Vedant read it; committed on his word (`4883f3c`, `52b98d2`, then
  the records) and pushed. The checks workflow's first run passed on Ubuntu, and Vercel built
  with pnpm 11.5.0. Then, at his request: the job title out of the README, a Contact note,
  "Analytics for nerds" renamed Mission Control, a prompt for his portfolio's terminal, the
  docs completed, gitleaks run again over the history (clean) and the header icon pointed at
  the repo, held until the repo is public. Next: Vedant looks at the README on github.com and
  reads `docs/` and `CLAUDE.md`, then going public.
- 2026-10-17 - The difficulty dropdown: Vedant chose a dropdown for the difficulty on every page
  that has one (asked with mockups). Built `src/components/Dropdown.tsx` on a native select, the
  one-row Learn bar, and a packaging test against iOS zoom, which also caught the 14px Report box.
  342 Python and 148 TypeScript tests; a drive of 36 checks at desktop and phone size. Nothing
  spent. Pushed on his word; the held header commit moved to the local branch
  `held/header-link` so it did not go out with it.
- 2026-10-19 - Session 10b closed, and version 1 with it: on Vedant's word, gitleaks once more
  (clean), the repo made public (MIT), secret scanning with push protection and Dependabot
  alerts on, the description and homepage set, and the header's GitHub icon pointed at the repo
  (`3389a49`, from the held branch, now deleted). Signed out, the repo, its docs, the
  screenshots and the badge ("passing") all load. Nothing spent. Next: Vedant's own items, then
  planning v2.
