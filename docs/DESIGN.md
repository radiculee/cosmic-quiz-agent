# Cosmic Quiz Agent - design plan

## Context
Vedant wants an autonomous AI agent themed on astronomy and space. v1 is a Learn/Quiz web game with an
analytics page of the agent's measured statistics by mode and difficulty ("Mission Control",
`docs/PLAN.md` Session 9); v2 adds an astronomy newsletter (email, then WhatsApp) produced by the same
agent. (Changed 2026-10-08 by Vedant: the analytics page, added to v2 on 2026-10-01, moved into v1.) It
started as a portfolio feature but is now a **standalone project**: its own repo (public with an MIT
licence from Session 10, after a security audit), served at `cosmic.vedantgaikwad.ie` and hosted on
Vercel. (Changed 2026-10-08 by Vedant: it was "own domain"; it is now a subdomain of his existing
vedantgaikwad.ie.) The portfolio repo is not changed (at most a Projects link later). Aim: a capped running cost (Anthropic API up to $10 a month, TypeSafe Jev on a prepaid balance, every other service free), a real agent (the model chooses tools in a loop and
runs on a schedule with no human trigger), and code that reads well to recruiters.

## Decisions (grill-me session, 2026-09-30)
1. **Audience:** Vedant first, public later. Build for one user; keep the data model public-ready (opt-in, unsubscribe, GDPR).
2. **Domain:** astronomy and space only.
3. **Models:** Claude Code builds it. At runtime, `claude-haiku-4-5` for every step via the `anthropic` SDK, behind the provider interface in `agent/llm.py` (the model is config). Changed 2026-10-01; it was OpenRouter free models. See `docs/PLAN.md`.
4. **UI:** separate pages with real URLs, styled with the portfolio tokens (surface panels, teal accent, Space Grotesk headings, Press Start 2P only for small labels) over scene backgrounds (2026-10-10; it was the void background). Changed 2026-10-08 by Vedant; it was one page modelled on the "Wikipedia Speedrun" screenshot, with `[EASY|MEDIUM|HARD]`, `[LEARN|QUIZ]`, a topic input, `[Random topic]` and `[GO]`. Details in `docs/PLAN.md` Session 8.
   - Home (`/`): a full-screen hero over a slideshow of scenes: the title, the tagline and a compact row of the three ways in (Learn, Quiz, and "Try a new topic" from the web with the visitor's searches left today), a "Your progress" link and the slideshow's pause control. Just below the fold, one solid card holds the rank, points, trophy shelf and the bank's size. (Changed 2026-10-10 by Vedant; it was Learn and Quiz as two large cards and a smaller web card, then the progress.)
   - Scenes (decided 2026-10-10, `docs/PLAN.md` "Scenes"): Vedant's AI-generated scenes replace the flat void background, as a fixed layer the content scrolls over. Home rotates three (the observatory, the piano, the glasshouse) every 10 s with a 1.5 s crossfade, never under reduced motion, while paused or in a hidden tab; every other page shows the observatory still. Cards and controls on a scene are solid; text straight on it is ink with a soft shadow, and small lines below a page's intro sit on solid chips. The art is not covered by the MIT licence.
   - Learn (`/learn`, `/learn/<topic-slug>`): a difficulty switch, a searchable grid of bank topics (read ones ticked) and Random. Each topic's explanation and sources has its own URL. The switch, the search box and Random sit in one solid bar that sticks to the top while the grid scrolls (decided 2026-10-10 by Vedant; a box that scrolls on its own was turned down because it traps the page's scroll on a phone).
   - Quiz (`/quiz`): a difficulty and a run of 10, 30 or 60 questions, each on a different random topic (unplayed first). A length is offered only when the bank has that many topics at that difficulty.
   - The web page (`/explore`): a typed topic researched live (decision 9). A search makes a question at each level and the explanation at the chosen level, all shown on the page and stored in the bank (changed later on 2026-10-08 by Vedant; it was one explanation or one question). The questions come first and the explanation last, behind a button that opens once every question is answered, so it cannot give an answer away; opening it counts towards Explorer (changed 2026-10-10 by Vedant; the explanation came first). "Mission Control" opens from it at `/explore/stats` (`docs/PLAN.md` Session 9): each of its two tabs opens on four key figures, with the rest in closed rows (decided by Vedant on 2026-10-08).
   - Trophies (`/trophies`): tiered bronze, silver and gold trophies, which replace the v1 badges and pop up when earned.
   - Privacy (`/privacy`, Session 10b, decided 2026-10-09): what is stored, why and for how long, in plain words, linked from a footer on every page.
   - A slim header on every page with a GitHub link. Routing is a hand-rolled History-API router, with no routing library.
5. **Modes:**
   - LEARN: a plain-language explanation plus cited sources.
   - QUIZ: one 4-option MCQ per GO. After answering (right or wrong), show the explanation plus cited sources.
   - After answering, a "source check" shows Jev's verdict and confidence for each answer option (supported, contradicted or not addressed by the cited sources); LEARN shows how many sentences the sources back. It is labelled as a source check, never as accuracy. (Changed 2026-10-03 from "per source": Jev checks each claim against all cited pages together, so there is no per-source verdict to show.)
6. **Citation rule:** a source may only be a URL fetched in that run, enforced in code. Any other URL is dropped.
7. **Architecture:**
   - The daily **Curator** scans sources, picks notable topics, researches them, writes MCQs at each difficulty, verifies them, publishes to the bank, and retires stale items.
   - The bank is filled up front, then grown daily (decided 2026-10-02). `python -m curator build` researches 30 approved evergreen topics (`curator/topics.py`), each in LEARN and QUIZ at all three difficulties, under a $6 cap; it can be re-run and skips jobs already done. `python -m curator daily` then adds 1 news topic a day from the NASA and ESA feeds under a $0.40 cap.
   - LEARN is also served from the bank: each topic has a verified explanation per difficulty, so players can browse topics to explore. A typed new topic still runs live (decision 9).
   - Retirement: items from news topics retire 90 days after the topic is added; evergreen topics never retire. Retired items keep their rows (status `retired`) so history and analytics survive.
   - The UI serves questions from the bank.
   - A typed custom topic runs the same agent core on demand.
   - v2 newsletter: the same Curator with an email output.
8. **Runtime:**
   - GitHub Actions cron runs the Curator as a plain Python script (no Docker).
   - Supabase free Postgres stores the bank. Daily writes stop the free tier from pausing.
   - Azure was considered and turned down on 2026-10-02. The only always-free Azure database (Azure SQL's free offer) has a monthly compute allowance that a public site could use up, after which it pauses until the next month; Azure PostgreSQL is free for 12 months only; and Azure SQL has no browser-safe read API. Azure could still host another part later (for example the Curator's schedule or v2 email).
   - Vercel Hobby hosts the UI and `/api`.
   - Local first: everything runs on Vedant's machine against Supabase, and moves to the cloud in Session 7 (changed 2026-10-01).
   - The only costs are the Anthropic API (capped at $10 a month) and TypeSafe Jev (prepaid balance, EUR 5 at 2026-10-01; $0.042 per million input tokens, output free). The site uses a subdomain of Vedant's existing domain, so there is nothing new to buy (changed 2026-10-08 by Vedant; a new domain was the one other cost).
9. **On-demand guardrails:**
   - A cheap on-topic check: two Jev yes/no questions in one request (is it astronomy or space; is it only a topic name, with no instructions or abuse), with the typed text passed as data. Measured 2026-10-04 on 44 labelled inputs: Jev 44/44, a keyword filter 18/44; about $0.00002 and 0.23 s a check (`python -m evals ontopic`).
   - Per-user limits, where a user is a salted hash of the IP address (never the raw IP, for GDPR). Decided 2026-10-01:
     - 2 searches a day per user, resetting at midnight UTC. A search is up to 4 agent runs, one at a time: a question at each level, the chosen level first, then the explanation at the chosen level (in that order since 2026-10-10, so when a cap cuts a search short it is the explanation that is left out), only for items the bank does not already have. Bank questions do not count. (Changed 2026-10-08 by Vedant; it was 3 custom-topic runs of one item each, lowered from 10 on 2026-10-05 after the Session 6 code review, since at 10 one visitor could use up the global daily cap.)
     - 300 API requests an hour per user, across all endpoints (bank questions, reports, stats), against scraping and runaway scripts. (Raised from 60 on 2026-10-04: a 10-question run is about 21 requests, so 60 stopped players during their third run in an hour.)
     - 10 reports a day per user (added 2026-10-09 by the security audit, `docs/SECURITY_AUDIT.md` S2): two reports hide an item, so without a limit two connections could hide the whole bank.
     - Visitor hashes are cleared on a timer by a daily purge (migration 008, added 2026-10-09): live runs' hashes and request windows after a day, report hashes after 30 days.
     - The API serves this site's own pages only: a request another site's page sends is refused, and a POST must carry JSON (added 2026-10-09, `docs/SECURITY_AUDIT.md` S1).
     - Over a limit, custom topics fall back to the bank and other requests get HTTP 429 with a retry time.
   - A global cap that stays under the $10 limit (set 2026-10-04): 4 searches and $0.50 a day, and $4 a month for live runs, leaving room for the daily Curator. Each run reserves the most it can cost ($0.17) until it ends; a search runs one at a time, so it never reserves more than that. When a cap is reached, serve from the bank. (Changed 2026-10-08 by Vedant: the daily count was 10 live runs; a search costs about $0.12.) Since a run starts only if today's spend plus its reservation fits $0.50, 4 searches is a ceiling: the day's 4th search usually makes 1 or 2 items, or cannot start. Kept as is (decided 2026-10-08).
   - No run of a search starts after 3 minutes, and a run that starts after about 2 minutes gets a shorter agent time budget (what is left before 280 s, minus 40 s for the verifiers and the save), so a search always ends inside Vercel's 300 s (decided 2026-10-08).
   - Live results are stored in the bank whatever the outcome. A published one is shown to everyone; one in review is shown only to the player who asked for it, labelled 'Not fully verified' with the checks' doubts, until Vedant approves it; a discarded one sends the player to the bank (decided 2026-10-04).
   - The UI streams live agent steps as a terminal-style agent log, including each Jev claim check. For a quiz, the option checks show only Jev's confidence until the player answers, so the log cannot give the answer away.
10. **Evidence tools** (built in Session 2):
    - `search_wikipedia`, `search_arxiv` (astro-ph), `search_nasa_images` (NASA Image Library), `nasa_apod` (read from the APOD pages, since the APOD API now returns placeholders), and `fetch_feed` (NASA news, NASA Science, ESA Space Science, ESA/Webb, ESA/Hubble). None needs a key.
    - `fetch_page`, limited to an allow-list: Wikipedia; NASA, ESA, STScI, Webb and Hubble sites; arXiv (abstract pages only), ESO, NOIRLab, the IAU; and popular science sites (Space.com, Sky & Telescope) at the lowest preference. Britannica was removed in Session 2 because it blocks the agent (HTTP 403).
    - No web search fallback for now (decided 2026-10-01). Revisit if the Session 3 evals show topics failing for lack of sources; Tavily's free tier (1,000 searches a month) is the first option then.
11. **Stack:**
    - A Python agent core package, shared by `curator` (run with `python -m curator` in Actions) and `api/research.py` (Vercel Python function).
    - Vite + React + TypeScript + Tailwind UI, with pnpm.
12. **Agent loop:**
    - Hand-rolled (`run_agent` in `agent/loop.py`, about 120 lines), using the `anthropic` SDK behind the provider interface (changed 2026-10-01).
    - Tools are plain functions with JSON schemas, and there's a hard step budget.
    - Pydantic models validate every output: `QuizItem`, `Explanation`, `Citation`.
13. **Difficulty (depth plus distractors):**
    - EASY: well-known facts, clearly wrong distractors, sources are Wikipedia and NASA.
    - MEDIUM: mechanisms and "why", plausible distractors.
    - HARD: numbers and recent findings, distractors built from common misconceptions, arXiv and JWST sources, one technical term defined.
14. **Publish gate:** three layers, cheapest and most certain first (layers 2 and 3 updated 2026-10-01).
    - **Layer 1, code checks** (deterministic, free): every cited URL was fetched in the run; every quote appears word for word on its fetched page; every number in the answer appears in a fetched page. The Session 1 spike found 2 of 13 quotes were not verbatim and one wrong number, so all three are hard gates.
    - **Layer 2, Haiku verifier:** a separate Haiku 4.5 pass with its own prompt confirms the quoted passages support the correct answer and that each distractor is wrong.
    - **Layer 3, Jev second opinion:** for each claim and each distractor with its quoted passage, TypeSafe Jev answers supports / contradicts / says nothing, with probabilities and a confidence. Jev is pinned to a fixed version (`jev-1.13.0`) so thresholds and the scores players see stay stable. Jev cannot check numbers reliably (it accepted the spike's 10^-27 vs 10^-30 error at 0.86), which is why layer 1 checks numbers.
    - How layers 2 and 3 combine, and the thresholds, are set in Session 3 from the eval results. Pass: auto-publish. Borderline (the verifiers disagree, or Jev's confidence is below threshold): `review` status. Fail: discard and log.
    - Every layer's result is stored with the item, including Jev's confidence, which the UI shows (decision 5).
    - Jev's verdict definitions are astronomy-specific (`astro-1`, chosen 2026-10-02): the same quantity in an equivalent unit or notation counts as support; a different value, order of magnitude, object or classification counts as a contradiction. A Jev-only re-check of the Session 3 eval at the same threshold kept planted faults handled at 38/40, with two more flagged by Jev itself; generated items went from 22/20/9 to 23/19/9 published/review/discarded. The wording's version is stored with every Jev result.
    - Decided 2026-10-01 from the Session 3 eval and Vedant's hand review: **all_must_pass** with a Jev threshold of **0.8**. Any layer failing discards; any doubt goes to review. Measured: 38 of 40 planted faults handled, 43% of generated items published directly. See `docs/EVALS.md`.
    - Amended 2026-10-02: when the Haiku verifier's own supporting quote is not word for word on a cited page, the item goes to `review` instead of being discarded. That is the verifier's mistake, not evidence against the item: re-scored on the Session 3 eval it caught 0 of 40 planted faults and discarded 5 items, which now go to review; none is newly published and 38 of 40 planted faults are still handled.
    - A Report button on each question; 2 reports hide it. A visitor sends at most 10 a day, and `python -m curator review --reported` keeps or discards each hidden item (added 2026-10-09).

## Defaults chosen without asking (change if wanted)
- **Review queue:** Vedant decides borderline items with `python -m curator review`, which shows each item with its question, answer, explanation, why it is in review, every cited source with its quote, and Jev's source check (changed 2026-10-02: the table editor does not show an item's sources, and nothing is approved without seeing them). `items.reviewed_at` records when each item left review, so the verifiers' doubts can be compared with his decisions. No admin UI in v1.
- **Player state:** no accounts. Streak and score are kept in `localStorage`. Decided 2026-10-10 by Vedant: saving progress across devices waits for accounts in v2, decided together with the newsletter (which needs subscribers' emails anyway). Known limits until then: the profile does not move between devices, and Safari deletes script-written storage after 7 days of use without a visit; `navigator.storage.persist()` does not prevent that (it only guards against eviction when space runs low, and Safari usually refuses it in a tab).
- **Model selection:** a small eval set (about 20 fixed topics) scored on tool-call success, citation pass rate and verifier agreement. It scores the configured model and runs again whenever a model is swapped.
- **Verifier evaluation:** the eval also includes a seeded-error set: generated items with planted faults (a wrong number, an unsupported claim, a quote that is not on the page, a distractor that is actually true). Each layer's catch rate and false-reject rate is measured on it, together with Haiku/Jev agreement and whether Jev's confidence is calibrated (do 0.9-confidence verdicts turn out right about 90% of the time).
- **Secrets:** `ANTHROPIC_API_KEY`, `TYPESAFE_API_KEY`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (Actions and server only; Supabase's new name for the service-role key), `SUPABASE_PUBLISHABLE_KEY` (the new name for the anon key: read-only, row-level security), `IP_HASH_SALT`. `NASA_API_KEY` is kept in `.env` but unused while APOD is read from its pages; `SEARCH_API_KEY` only if a web search fallback is added.

## Repo layout
Changed 2026-10-08 by Vedant: the UI is split into pages with a router and trophies, `api/quota.py`
(Session 8) and `api/stats.py` (Session 9) are added, and the repo gets an MIT licence when it goes
public (Session 10). The repo is `radiculee/cosmic-quiz-agent`, served at `cosmic.vedantgaikwad.ie`.
```
agent/                 Python package (shared core)
  llm.py               provider interface + Anthropic implementation, model config
  loop.py              tool-calling loop with step budget
  tools/               wikipedia.py arxiv.py nasa.py feeds.py fetch.py base.py (shared HTTP + retries)
  schemas.py           Pydantic: QuizItem, Explanation, Citation, Run
  verify.py            layer 1 code checks: fetched URLs, verbatim quotes, numbers
  verifiers/           Verifier interface: haiku.py (layer 2), jev.py (layer 3)
  prompts/             per-difficulty prompt templates
  rest.py              small PostgREST client (retries, errors, paging) shared by store and bank
  store.py             Supabase writes/reads with the secret key (Curator, review, reports, limits)
  bank.py              public reads with the publishable key: topics, items, answers, source check
  limits.py            the on-demand guardrails' numbers, and the visitor's quota
  topic_check.py       the on-topic check for typed topics (Jev)
  ondemand.py          a guarded live search (up to 4 runs, one at a time), streamed as events
  run_stats.py         one live run's figures for the analytics panel (numbers only)
  stats.py             the analytics page's statistics: agent_stats() reply models and reader
  web.py               HTTP layer for api/: handle(ApiRequest) -> ApiResponse, WSGI app per function
curator/               build (initial bank) and daily (news) runs: discover -> research -> draft ->
                       verify -> publish / review / discard -> retire, under a dollar cap
api/research.py        Vercel Python fn: guarded on-demand run, streams steps (Session 6)
api/topics.py          bank topics and where they can be played
api/item.py            a random published item (a quiz item without its answer)
api/reveal.py          a quiz item's answer, explanation, sources and source check
api/report.py          report an item (salted IP hash; two reports hide it)
api/quota.py           the visitor's live runs left today and whether the global cap is open
api/stats.py           Mission Control: aggregates only, edge-cached (Session 9)
dev/api_server.py      local server for api/ (Vite proxies /api to it); never deployed
dev/check_stats.py     read-only check of the live agent_stats() against a Python version of it
evals/                 fixed topic set + scoring script; `export` writes the eval history for the UI
src/                   Vite + React UI: router.ts (History-API router), pages/ (home, Learn, Quiz,
                       the web page, trophies), game.ts (points, streaks, ranks, runs), trophies.ts
                       (tiers and what was just earned), profile.ts (progress in localStorage),
                       search.ts (a live search's items as the web page shows them), components/,
                       stats.ts and charts/ (Mission Control, hand-written SVG), data/evals.json
                       (the eval history, built in), slideshow.ts and components/Scene.tsx (the
                       scenes behind every page)
public/scenes/         the scene images at 1280, 1920 and 2560 px (WebP), versioned names; the
                       masters stay outside git (bg_images/)
supabase/schema.sql    topics, items, sources, claim_checks (per-claim results of all three layers,
                       incl. Jev verdict, confidence, probabilities and model version), runs,
                       curator_runs, cited_pages, reports, rate_limits, on_demand_runs
                       (+ subscribers in v2)
supabase/migrations/   numbered changes after schema.sql (006 the web page's searches, Session 8;
                       007 adds agent_stats() and drops the 004 begin_on_demand_run, Session 9;
                       008 clears visitor hashes on a timer, Session 10a)
.github/workflows/curator.yml   daily cron + manual dispatch
.github/workflows/checks.yml    every check on each push and pull request (no secrets, no paid calls)
public/fonts/          the three fonts, self-hosted (WOFF2 subsets, each with its OFL licence)
public/og-v1.jpg       the link preview: the observatory scene with the title and tagline
README.md              the case study: what it does, how, what it costs, security and privacy
docs/DEVELOPMENT.md    setup, every command and its cost, the checks, deploying, the repo map
docs/images/           the README's three screenshots (not under MIT; see NOTICE)
LICENSE                MIT, for the code (Session 10b)
NOTICE                 what MIT does not cover: the scene art, the link preview, the screenshots, the fonts
```

## Milestones (one at a time, verified before moving on)
Superseded on 2026-10-01 by the local-first session order in `docs/PLAN.md`. Kept for the record.

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
Done on 2026-10-01.

Create the project folder (`cosmic-quiz-agent`) with no app code:
- `CLAUDE.md`: project identity, stack, commands, conventions carried over from the portfolio (no emojis, complete files, strict typing, one milestone at a time, explain before large changes, small commits), design tokens and font rules, citation rule, zero-cost rule.
- `docs/DESIGN.md`: the full decision record, layout, milestones and verification (this plan).
- `docs/HANDOFF.md`: where things stand and the first prompt to paste into the new session (start Milestone 1 spike).
- `.gitignore` (Python + Node + .env), then `git init` on `main`. No commit unless Vedant asks.
Vedant then opens the folder in a new VS Code window and continues from `docs/HANDOFF.md`.

## Verification
- **Agent core:** `python -m evals` on the fixed topics. Targets: at least 90% of published items pass the citation check, 0 unfetched URLs, and every item validates against its schema.
- **Verifiers:** on the seeded-error set, report each layer's catch rate and false-reject rate, Haiku/Jev agreement and Jev's calibration. Targets are agreed with Vedant in Session 3; the combined gate must catch every planted wrong number and non-verbatim quote.
- **Curator:** trigger the workflow manually (`workflow_dispatch`), confirm new `published` rows in Supabase and a `runs` row with step logs, and confirm that failed or borderline items land in the right status.
- **UI:** run `pnpm dev` locally. Play each mode and difficulty, check that sources open and appear in that item's fetched set, and that Report hides an item after 2 reports.
- **On-demand:** run a valid topic (steps stream, result is cached, the second request is instant), an off-topic query (rejected), a 4th custom topic in a day from the same user (falls back to the bank), and a 301st request in an hour (HTTP 429).
- **Cost check:** confirm Anthropic Console spend stays under $10 a month, the TypeSafe balance matches the Jev usage logged per run, and every other service is on a free tier.
