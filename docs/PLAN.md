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
- [ ] Re-check items 100 (Jev: possibly contradicted), 136 (LIGO: announcement date and a
      verifier misquote) and 165 (Voyager: power-supply date) against their sources.

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

Claude Code:
- [ ] Keep `runs/curator/pending/` between scheduled runs (actions/cache or an artifact), so a run
      the bank could not store is re-sent by the next one, as it is locally.
- [ ] Run the Vercel streaming spike planned on 2026-10-01 (incremental delivery, 300 s cap, client
      disconnect, coexistence with Vite, cold start) and record results in `docs/SPIKE.md`. Check
      that WSGI `app` functions in `api/` stream line by line (the UI copes if they are buffered),
      and that Vercel replaces `X-Forwarded-For` with the client's address.
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

## Session 9 and later - v2
Two features, planned in detail once v1 is live. Their order is a decision for Vedant at that point.

### v2: Analytics page ("nerd stats")
**Goal:** a separate page (for example `/stats`) that shows everything the agent measures, filtered by
mode (LEARN, QUIZ) and difficulty (EASY, MEDIUM, HARD), with a 2 x 3 grid view that compares all six
combinations side by side.

What it shows, grouped (every group respects the mode and difficulty filters, a date range, and the run
source: Curator or on-demand):

| Group | Statistics |
|---|---|
| Volume and outcomes | Runs; outcome split (passed, failed citations, no answer, budget exceeded, model error); published / review / discarded rate |
| Cost | Cost per run and per published item, Haiku and Jev separately; month to date against the $10 Anthropic cap and the TypeSafe balance; savings from prompt caching (actual against uncached price) |
| Tokens | Average input, cache write, cache read and output tokens per run; cache hit ratio |
| Speed | Run time (median and 95th percentile); latency per model call, per tool and per Jev check |
| Agent behaviour | Model calls per run; tool calls by tool; how often the model calls tools in parallel; pages fetched per run and by domain (Wikipedia, NASA, ESA, arXiv); nudges; which budget ran out, when one did |
| Evidence | Citations per answer; kept against dropped; verbatim quote rate; number-check pass rate |
| Verifiers | Haiku verdict split; Jev verdict split; Jev confidence histogram; Haiku/Jev agreement; why items went to review |
| Evals | Each `python -m evals` run over time: citation pass rate, seeded-error catch rate per layer, Jev calibration, with model or version changes marked |
| Players (only if approved, see decisions) | Correct-answer rate per difficulty; reports per item |

Data and serving:
- Reads the tables v1 already writes (`runs`, `claim_checks`, `items`, `reports`) plus stored eval results.
- The browser only reads aggregated SQL views, never raw rows, so salted IP hashes and step logs stay
  server-side. Views are refreshed after each Curator run to keep queries light on the Supabase free tier.
- Built with the portfolio design tokens; Press Start 2P only for small stat labels.

v1 prerequisites (so the page has history from the first day):
- Session 3: eval results saved as JSON with the date, model and Jev versions, and per-layer scores.
- Session 4: each `runs` row stores mode, difficulty, source (Curator or on-demand), outcome, Haiku and Jev
  tokens and cost separately, cache tokens, wall time, per-step latencies, tool calls by name, pages
  fetched by domain, nudges and the budget reason.

Decisions to ask:
- Public page, or private to Vedant. Recommendation: public, aggregated only; it doubles as a portfolio
  piece for recruiters.
- Whether to store anonymous player answer events (no IP, no account) to get correct-answer rates. This
  touches GDPR, so it needs a privacy note and must stay aggregate-only.
- Charts: hand-written SVG or a free chart library (license and bundle size checked first).
- Which statistics appear on the first screen, and the refresh cadence.

Gate (Vedant): picks one mode and difficulty filter and checks the page's numbers against the Supabase
tables and the Anthropic and TypeSafe consoles.

### v2: Newsletter
Curator email output via Resend (portfolio `api/contact.ts` pattern), subscribers with double opt-in and
unsubscribe, then WhatsApp.

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
