# Handoff: latency

Notes for the latency session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for
this session. Update them before finishing, and commit them on `session/latency`.

Last update: 2026-11-04. On `main` at `57771af`. Parallel search is
live since 2026-11-01 21:32 UTC. The reports below replace "Where things stand", "Next" and
"Blockers" further down, which are kept as the record of 2026-10-30.

## A leading "The" made a second, paid topic (2026-11-04)

**Done**

- `topic_key` in `agent/bank.py` and `topicKey` in `src/topics.ts` compare names ignoring case,
  extra spaces and one leading "The". Stored and shown names do not change.
- `topic_named` reads the name as typed. If that finds nothing, it reads the other spelling. The
  name as typed wins if the bank has both. It compares each row by `topic_key`, so `%`, `_` and `*`
  match nothing. An empty name sends no read.
- I used two plain `ilike` reads, not one `or=(...)` filter. The form is the one that runs today, so
  no new PostgREST syntax goes live untested. A new topic now costs two free reads, not one.
- `findTopic` has the same order, so the free or paid hint on Explore and Learn agrees with the
  server. `randomTopic` uses `topicKey` for the current and played topics.
- Suggestions and the Learn filter (`matching`) find a name with or without "The". They do not use
  `topicKey` alone: then "the m" would list every name with an "m", and "the" would lose "The Moon".
- "The" alone stays "the". It matches only a topic named "The" or "The The". It never matches an
  empty name or every topic.
- Both test files hold the same 12 cases for the rule.

**In progress**

Nothing.

**Left, each on main's word**

1. Fix `curator/discover.py` lines 145 and 158. **This one makes the same duplicate**: a news pick
   "The X" passes when the bank has "X", and the Curator pays for it. The file is not on my list, so
   I did not edit it. The fix: compare with `topic_key` from `agent/bank.py` in both lines.
2. Decide on the rest of the list under "Other places that compare names".
3. Retire topic 397, after the fix is deployed. See the plan below.

**Blocked on**

Main's word on item 1, since `curator/discover.py` is not on my list. Nothing else.

**Needs from Vedant**

His word to retire topic 397, after main runs step 1 of the plan and shows him which topic has more
items. The instruction assumes 397 is the one to drop. I could not confirm that without a bank read.

**Files changed**

`agent/bank.py`, `src/topics.ts`, `src/topics.test.ts`, `tests/test_api.py`,
`docs/handoff/latency.md`.

**Checks run**

All on the worktree with the code commits, with no `SUPABASE_*` variable set, so the build made no
bank read. All exit 0: `pnpm install --frozen-lockfile`, `pnpm typecheck`, `pnpm test` (306 tests in
28 files), `pnpm build` (4 pages, no topic pages), `pytest -q`, `ruff check .`,
`ruff format --check .`, `mypy --strict` (89 files).

**Not checked**

- The lookup has not run against real PostgREST. The tests use a stand-in for `ilike`. After the
  deploy, type "Cosmic Microwave Background" on Explore: the plan must name the other spelling.
- I did not measure the extra read's time.
- I made no bank read, and I did not use a key from `.env`. The only live reads were
  `/api/topics` and `/sitemap.xml` on the public site.
- I did not drive the pages in a browser.

### Other places that compare names

Fix needed, same duplicate:

- `curator/discover.py:145,158`: see "Left", item 1.
- A topic with no visible item, only `review` or `discarded` ones. Row-level security hides it from
  `topic_named`, so the other spelling makes a second row. The same spelling reuses the row, by
  `lower(name)`. The fix needs the secret key or the database: `agent/ondemand.py` or a migration.
- `supabase/schema.sql:30`: the unique index is on `lower(name)`, so the database allows both
  spellings. An index on the new rule would make a duplicate impossible, but it cannot be built
  while topics 377 and 397 both exist, because the retired row stays.
- `agent/store.py:401` `job_key` and the fill list: a listed name that differs from a bank name by
  "The" makes a second topic. Today none does: I compared `BUILD_TOPICS` and `FILL_TOPICS` with the
  39 topics in `/api/topics`. Topics that are not complete are not in that list, so run the same
  comparison with the secret key before the paid fill.

No duplicate, left as they are:

- `agent/topic_pick.py:116,124`: a Surprise me pick that differs by "The" now goes through
  `topic_named`, so it finds the bank's topic. It costs the pick (about $0.003) and shows an existing
  topic, with no second topic. Using `topic_key` here would stop that waste.
- `curator/__main__.py:132` removes repeats inside one run's jobs. `curator/images.py:945` is an
  operator's `--only` filter.
- `agent/bank.py` `coverage` and `random_item` compare by `eq`, but they get the bank's own spelling.
- `src/slug.ts`: "The X" and "X" have different addresses. This is correct while names are kept.
- `agent/topic_check.py`, `scripts/prerender/bank.ts` and `src/closeMatch.ts` do not decide whether a
  topic exists in the bank.

Also found, no duplicate in the bank that I could check: the eval list breaks its held-out rule by
"The". `evals/topics.py` has "The Andromeda Galaxy" and "The James Webb Space Telescope".
`FILL_TOPICS` has "Andromeda Galaxy", and the live bank has "James Webb Space Telescope".
`tests/test_curator.py:135,141` compares by casefold only, so it passes. I did not check whether the
eval topics are in the bank.

A small difference stays between the rules: Python uses `casefold`, TypeScript uses `toLowerCase`, so
they differ on letters like "ß". This is older than this change. It has little effect, because `ilike`
finds the candidates first.

### Plan: retire topic 397 (not run)

**Order.** Deploy this fix first. If 397 retires first, typing its name finds nothing, and the search
is paid again. The store reuses row 397 by `lower(name)`, so the new items go on the retired row.

**Step 1, read only.** Save the output in this file: it is the record for undoing the change.

```sql
select id, name, kind, retire_after, created_at from public.topics where id in (377, 397);
select topic_id, id, mode, difficulty, status, report_count from public.items
  where topic_id in (377, 397) order by topic_id, mode, difficulty, id;
select topic_id, kind, card_path, preview_path, locked from public.topic_images
  where topic_id in (377, 397);
```

Stop and ask Vedant if one of these is true:

- The names are not the two spellings. I expect 397 to be "Cosmic Microwave Background", because it
  is the later search, but that is inferred.
- 377 has no published item with `report_count` under 2. Then row-level security hides 377 too, and
  a typed search is paid again.
- 397 has more published levels than 377. Neither name is in `/api/topics` or `/sitemap.xml` today,
  so neither topic is complete. After the retirement, 377's gaps are filled by paid runs: a typed
  search or the daily Curator (`missing_slots`, at most 6 jobs a day).

**Step 2, write.** One transaction. Use the name from step 1.

```sql
begin;
update public.topics set retire_after = now()
  where id = 397 and lower(name) = lower('Cosmic Microwave Background');
update public.items set status = 'retired'
  where topic_id = 397 and status in ('published', 'review');
commit;
```

Check that the first update changes 1 row. If not, roll back.

| Rows | What happens | Why |
| --- | --- | --- |
| `topics` 397 | Stays, with `retire_after` set | `runs` and `items` point to it with no cascade, and it holds the cost record. `retire_stale()` then also retires an item that a run still in progress stores later. The Curator's name check still sees the name. |
| `items`, `published` and `review` | `status = 'retired'`; the trigger sets `retired_at` | Row-level security hides them. Do not delete them: `player_answers.item_id` points to them. |
| `items`, `discarded` | No change | They are never shown. |
| `sources`, `claim_checks`, `reports`, `runs`, `cited_pages` | No change | Row-level security hides sources and checks with their item. |
| `topic_images` 397 | No change | Row-level security hides it when the topic has no visible item. `curator/images.py` reads only topics with published items, so the fill skips it. |
| Files in the `topic-images` bucket | No change | Names hold a content hash, so 377 can share a file. The extra cost is at most two files of 512 KB. |

**The address.** `topicSlug` gives `/learn/cosmic-microwave-background` for 397 and
`/learn/the-cosmic-microwave-background` for 377. On 2026-11-04 neither name was in `/api/topics` or
`/sitemap.xml`, so neither address has a page, and nothing needs a redirect today. If 397 was listed
when a build ran, its static page stays until the next deploy, and no deploy hook is set. If main
finds the address shared or indexed, add a redirect in `vercel.json`, which is not on my list.

**After it.** `/api/topics` is cached for up to 300 s. Then check with free reads:
`BankReader.topic_named` returns 377's name for both spellings, and `missing_slots()` lists no slot
for 397. Mission Control's published count falls and its retired count rises by the same number. A
player who holds a question from 397 at that moment gets no answer from `/api/reveal`.

**To undo.** Set `retire_after` back to null on 397, and set each item in the step 1 record back to
its old status. `retired_at` stays set unless it is cleared by hand.

**CHANGELOG line for main:** Typing a topic with or without a leading "The" now finds the same bank
topic, so it no longer pays for a second one.

## Where this session stopped (2026-11-02)

Vedant ended the session. No server of this session is running. No paid call was made.

**State.** The EASY-first run order is live: main landed `7b00bf3` unchanged, and `origin/main` is at
`fa23eda`. `session/latency` was rebased onto it, and nothing is left unmerged except this note.

**Next, each on main's word:**

1. **Measure the EASY-first order.** The next main gives the real search's numbers. Use only searches
   with a run that did not fail, started after the deploy of `fa23eda`, with six runs. Compare the
   total (last `finished_at` less first `started_at`) and the first question with 61.3 s and 49 s, both
   n=1. Then update `CHANGELOG.md`, where "up to about 90 s" is still an estimate, and send main a
   report with the seven headings. Check whether it is a cold search: the first model calls in `steps`
   take about 20 s when cold, and quiz and learn compile apart, so a cold search should pay this twice.
2. **Check the daily Curator run.** Did it run both modes, and were later first calls fast? This tests
   whether the daily run keeps the schemas warm. The cause of the first-call cost stays "inferred".
3. **The fill.** `python -m curator fill`, paid. It waits for main's word, after the cheap key test. The
   worktree's `.env` still holds the old Anthropic key, so it needs the new one first.
4. **Per-account limits (step 4).** Not started. It waits for main to say accounts are set up.

**Decided, do not reopen.** No warm-up now, `strict: true` stays, no `max_tokens` test now. Left-out
items are reported after the first run starts, and `SEARCH_SECONDS` stays 280. The `timeLeft` note needs
no action: ui's branch no longer uses it in its progress code.

**Tools.** The scripts in the session's scratchpad do not carry over: `search_times.py`, `why_slow.py`,
`why_steps.py`, `why_first.py`, `why_cold.py`. Each is a read-only PostgREST query on `on_demand_runs`
and `runs`, loading `.env` with python-dotenv; `steps` holds each call's seconds. Vercel's request logs
for `/api/research` were still readable 15 minutes after the search; read them soon after a search if
429s matter, as they may not stay long.

## Report, 2026-11-02, the EASY question first

### Done

- `_run_search` in `agent/ondemand.py`: the EASY question goes first and alone when live, and the rest
  start together when it ends. See "The EASY question first" in `docs/PLAN.md` for each case.
- `CHANGELOG.md`: this order, and lines for free failed searches and the red daily run.
- Main's decisions recorded in `docs/SESSIONS.md`. The cause of the first-call cost stays "inferred".

### In progress

- Nothing.

### Left

- After a real search: measure this order, the time and the first question, and update the changelog.
- Today's daily Curator run: both modes? Are later first calls fast? It has not run yet (the 06:17 UTC
  cron has been running at 12:23 to 13:18).
- The fill, on main's word. Per-account limits, when accounts are set up.

### Blocked on

- Nothing.

### Needs from Vedant

- One real search, through main.

### Files changed

- `agent/ondemand.py`, `tests/test_ondemand.py`, `CHANGELOG.md`, `docs/DEVELOPMENT.md`, `docs/PLAN.md`,
  `docs/SESSIONS.md`, `docs/handoff/latency.md`.

### Checks run

All pass before commit: pytest, ruff check, ruff format, mypy --strict, pnpm typecheck, pnpm test, pnpm
build. No paid call and no dev server.

### For main

- **The flaky test.** `test_runs_finishing_out_of_order_each_send_their_own_item`, which ui also saw
  fail, relied on 50 ms gaps between threads. It was timing, not the search. The slow run now waits
  until the other five have settled, so no gap is involved.
- **Time limit.** `vercel.json` gives `api/*.py` 300 s; about 90 s fits. `SEARCH_SECONDS` stays 280:
  two batches at the agent's 120 s budget are about 240 s plus the verifiers. One gap stays: the budget
  is checked before each model call, and a call can run to its 60 s timeout. A search in which both
  batches hit that could pass 300 s, so Vercel ends it and those runs stay unsettled, and they count
  as stale reservations do today. The longest run stored so far took 61.8 s, so this is not changed.
- **A player leaving.** The second batch still starts if the player left during the EASY question. A
  reserved run is paid for and stored, so the cost is the same as before.
- **Progress rows, for ui.** `timeLeft` shows a waiting run's whole estimate. The five later rows say
  "About N s left" while they wait for the EASY question, and their own clock starts at their first
  progress.
- **Stub.** No edit needed. Main's newest stub, as read on 2026-11-02, replaces `run_learn`, `run_quiz`
  and `verify_and_decide` and goes through the real `research`, so the new order comes with the code.
  It has not been run with this change, as no dev server may start.

## Report, 2026-11-02, the after time

### Done

- After time, in `CHANGELOG.md`: **61.3 s, n=1** (search 86, "Light speed", six runs, 2026-11-02
  03:10:25 UTC, $0.2005). Before: median 145.2 s, n=4. Searches 74 and 80 (all failed) and 92 and 95
  (Pulsars, three runs, all failed, $0) are left out.
- Why each run took 35 to 61 s: see "Why search 86 took 61 s" below. No code changed.

### In progress

- Nothing.

### Left

- Main's decision on the page text and on the keep-warm options, below.
- A warm six-run search, to measure the time without the first-call cost. Not paid for by this
  session; the next real search within 24 hours of a run of both modes gives it.
- The fill: after the cheap key test and main's word. Per-account limits: when accounts are set up.
- `CHANGELOG.md` has no line yet for free failed searches or the red-run change. Main decides.

### Blocked on

- Nothing. The items above wait for main.

### Needs from Vedant

- The page text below (ui makes the change).
- Any recurring paid warm-up needs his approval (hard rule 1). This report does not recommend one yet.

### Files changed

- `CHANGELOG.md`, `docs/handoff/latency.md`.

### Checks run

All pass: pytest, ruff check, ruff format, mypy --strict, pnpm typecheck, pnpm test, pnpm build. Read-only
queries on `on_demand_runs`, `runs`, `curator_runs`; Vercel request logs; GitHub run logs. No paid call
and no dev server.

## Why search 86 took 61 s (2026-11-02)

**Cause: most likely the one-time compile of the strict tool schemas.** It is the first model call of
each run, not the parallel runs. This is inferred from timing: the API does not report compile time,
and no controlled test has run (it is paid).

| | Search 86 | Sequential runs (63) |
|---|---|---|
| First model call, each run | 19.4 to 22.6 s, 68 to 120 output tokens | warm: median 2.7 s (n=48); slow: median 21.9 s (n=15) |
| Later model calls per run | 4.33 calls, 19.2 s, 1,276 tokens | 2.94 calls, 12.7 s, 942 tokens |
| Seconds per 100 output tokens, later calls | 1.50 | 1.35 |
| Tool time per run | 2.3 s | 4.1 s |
| Run time not in the model, tools or verifiers | 0.1 to 0.3 s | median 0.3 s |

Evidence:

- All six runs paid it, and the times group by tool set: quiz 22.5, 22.5, 22.6 s; learn 19.4, 19.5,
  19.8 s. Later calls in the same runs took their usual time.
- The same 18 to 26 s is in the data since 2026-10-02, on sequential searches and the Curator, so
  parallel runs did not cause it. A sequential search paid it once for each mode; now all six runs wait
  together, which costs the search about 20 s, not 120 s.
- First call against the hours since a run of the same mode ended, all 340 runs with a model call:

| Hours since | Slow (over 10 s) | Fast |
|---|---|---|
| over 24 | 15 | 0 |
| 1 to 24 | 3 | 8 |
| under 1 | 7 | 305 |
| no earlier run | 1 | 1 |

- All 7 slow calls under 1 hour began together with a cold call of the same mode. Of the 3 slow calls
  at 1 to 24 hours, one is at 23.89 hours, the edge of the window. **The other two are not explained:**
  search 68 on 2026-10-30, at 5.15 hours, with no change to the tool or schema files since 2026-10-10.
- Anthropic's structured outputs page: "The first time you use a specific schema, there is additional
  latency while the grammar compiles", "cached for 24 hours from last use", and strict tool use "uses
  the same grammar pipeline". The cache is invalidated by a change to "the set of tools"; a change
  only to a name or description is not. The page lists Haiku 4.5, and does not state the cache's scope.
  `agent/llm.py:299` sets `strict: true` on every tool, and the first calls ran 74.8 hours after the
  last run with a model call: `DAILY_FROM` kept the Curator on upkeep until 2026-11-01, and that day's
  run failed on the old key.

Ruled out:

- **429 retries.** The request's log has 110 lines and no 429. It has 44 Anthropic lines, all 200: 32
  agent calls, 6 verifier calls and 6 token counts. That is the exact count with no retry at all.
- **CPU or thread contention.** Time outside the model is flat, tools were faster, and a later call was
  11% slower per token (n=1, within the spread between topics). Refused-key searches 74 and 80 ran six
  threads in 0.4 s on the same function.

The rest of the gap is this topic: it made more calls and wrote more. Its slowest run made 8 calls, so
without the first-call cost it would still have taken about 41 s, not 30 s. One verifier was slow too
(quiz-easy, 8.0 s against a usual 4.2 s), which may be its own schema compiling.

**Main's decision (2026-11-02).** No warm-up now, `strict: true` stays, no `max_tokens` test now. The
daily run is checked for both modes and fast first calls. The run order changed for other reasons, on
Vedant's word (see the report above). The recommendation as sent:

**Recommendation.** Change no code in the search: not the threads, the retries or the client.

1. Let the daily Curator keep the schemas warm. It costs nothing more, and it only began real runs on
   2026-11-01. Today's run is its first with a working key. Check that it runs both modes, and that the
   next real search within 24 hours has fast first calls. Limits: the cron at 06:17 UTC ran at 13:18,
   12:23 and 12:50, so a day's gap can pass 24 hours by minutes; a day with jobs in one mode only leaves
   the other cold.
2. Add a warm-up only if the launch week's logs show cold searches. It would be one small call per tool
   set and verifier schema, twice a day: about $0.70 a month. It first needs a test that a call with
   `max_tokens` 1 does compile the grammar, using a changed schema, under $0.01, on main's word.
3. Keep `strict: true`. Taking it off would remove the compile, but it needs a paid eval, and it comes
   just before the code freeze.

## The page text (for ui, Vedant chooses)

The two lines in `src/pages/ExplorePage.tsx:860` and `:867` are fixed text; no estimate feeds them.
They are right only when warm, and they also say the explanations come after the questions. In search
86 the explanations were done first (35 s against 49 s).

| | Warm | Cold |
|---|---|---|
| First question | 16.4, 16.8, 18.5 s (searches 50, 56, 62, rebuilt from sequential run times) | 49.0 s (search 86) |
| Whole search | 26.0, 29.0, 58.5 s (the same searches, rebuilt) | 61.3 s (search 86) |

Proposed:

- Empty: "Any astronomy or space topic. The agent writes a question and an explanation at each level.
  The first question takes 15 to 50 seconds, and the whole topic usually 30 to 60."
- New: "Not in the bank yet. GO uses one search: a question and an explanation at each level, usually 30
  to 60 seconds in all."

**The estimates.** `live_run_estimates` feeds only the progress rows, through `estimate_seconds` and
`timeLeft` in `src/progress.ts`. Keep it. Its sum matches a run's real time within 0.3 s, and its medians
(19.3 to 27.2 s) are right for a warm run. A cold run passes its estimate, and the row then says "Taking
longer than usual", which is true. Do not feed the fixed text from it: a median leaves out the cold case.

## Report, 2026-11-01

### Done

- Rebase on `origin/main` (`c9894d6`).
- Step 2, before time: **median 145.2 s (range 118.9 to 171.6 s, n=4)**. These are all the six-run
  searches before the cutoff, 2026-10-28 to 2026-10-30, measured as the last `finished_at` less the
  first `started_at`. Four-run searches: median 127.7 s (n=7). The plan's "about 100 s" was low.
- Step 3, the fill list and the estimate, below. Not run.
- The fill's code: `python -m curator fill`, with `FILL_TOPICS` in `curator/topics.py` and
  `--cap` at $5.00 by default. It is stored as a `build`, so it needs no migration. The workflow
  never runs it. Vedant's three decisions are in `docs/SESSIONS.md`.
- Found: the Anthropic key in GitHub Actions is refused (see Blocked on). Main confirmed it in
  Actions run 41310615378 and tells Vedant.
- A daily run whose model calls never worked now fails the workflow (`_model_calls_failed` in
  `curator/__main__.py`). Red: every job ended without an item and spent nothing; or there were no
  jobs and the topic choice failed and spent nothing. Green: a job reached the model; a billed
  topic choice that failed; a failed topic choice beside jobs that made items, because a red step
  would skip the site's rebuild. The purge still runs on a red run. The steps that save pending
  runs use `always()`, so they run too; the image and rebuild steps are skipped.
- A search that failed whole with no spend no longer counts (see "Free failed searches" below).
  Migration: `supabase/migrations/013_free_failed_searches.sql`. Check script:
  `supabase/checks/013_free_failed_searches_check.sql`. Stream event: `{"type": "end",
  "unavailable": boolean}`.

### In progress

- Step 2, after time: no search has succeeded since the deploy, so it cannot be measured yet. The
  query must use only searches with a run that did not fail. The `CHANGELOG.md` entry follows it.

### Left

- The after time and the `CHANGELOG.md` entry (step 2).
- Running the fill, on main's word only: `python -m curator fill`, from a machine with a working
  key. Learn and Quiz read `/api/topics` live, so a topic shows as soon as its sixth item is
  published, with no deploy. After the fill's review, if the prerender is live, call the deploy
  hook once. One deploy covers every topic published before it.
- Step 4, per-account limits: not started; waits for main.

### Blocked on

- The after time: a search that succeeds, which needs a working key in Vercel.
- `end` on the page: ui, after main sends the field name.
- The fill: Vedant fixes the GitHub `ANTHROPIC_API_KEY`, one cheap key test, the Console at $32,
  and main's word.

### Needs from Vedant

- Fix the `ANTHROPIC_API_KEY` in GitHub and Vercel, and put the Console at $32.
- Paste 013 and run its check script, before main deploys this code.
- Review the queue before 3 November, after the fill (decided).

### Files changed

- `docs/handoff/latency.md`, `docs/SESSIONS.md` (this session's row and the decisions).
- `curator/topics.py`, `curator/__main__.py`, `curator/discover.py`, `tests/test_curator.py`,
  `docs/DEVELOPMENT.md` (one row for the new command).
- `agent/store.py`, `agent/limits.py`, `agent/ondemand.py`, `supabase/schema.sql`,
  `supabase/migrations/013_free_failed_searches.sql`,
  `supabase/checks/013_free_failed_searches_check.sql`, `src/types.ts`, `src/api.ts`,
  `src/api.test.ts`, `tests/test_quota.py`, `tests/test_ondemand.py`, `docs/PLAN.md`.

### Checks run

All pass with free failed searches: pytest (521), ruff check, ruff format, mypy --strict, pnpm
typecheck, pnpm test (221), pnpm build. No paid call and no dev server. Read-only queries on
`on_demand_runs`, `topics`, `items`, `runs` and `curator_runs`. The SQL also ran on PGlite (see
below); it has not run on the live bank.

## Free failed searches (2026-11-01, Vedant's decision)

**The rule.** A search counts unless every run of it has ended as `failed` with `spent_usd` 0. A
run still going has no outcome, so a running search counts, and so does a stale one. The dollar
caps are unchanged.

**Order of work.** Main approved 013. Vedant pastes it and runs the check, which must say "CHECK
PASSED"; then main deploys the code. Before the paste, the deployed code would offer a search that
the database refuses. The other order is safe: with 013 and the old code, the old code only refuses
sooner. Once both are live, searches 74 and 80 stop counting, so Vedant has his 2 back.

**Verified.**

- PGlite (in-memory Postgres, in the scratchpad, not in the repo). The schema from before 013, then
  013 pasted twice, then both check scripts: both pass, with no row left behind. The same on a fresh
  project from the folded `schema.sql`. Without 013, the check fails. With 2 rows of each of searches
  74 and 80 in their real shape, a third search under limits of 1 starts.
- The new `on_demand_usage` on the live rows, read-only: runs 74 to 85 are all `failed` with
  `spent_usd` 0, and it returns 0 searches today and $0.
- A test through the real agent loop and gate, with a refused key, ends with `unavailable: true`.

**For main and ui.**

- `end` is sent only by a search that reserved runs, after all of them have ended. A bank-only
  search and a refused search do not send it. `fallback` stays as it is.
- A run that failed with nothing spent sends `missed` with reason `failed` and the text "The agent
  could not reach the model." A billed run with no item keeps reason `discarded` and "could not
  back ... with its sources".
- If writing a run's settlement to the database fails, the stream still says `unavailable: true`,
  but the run stays unsettled, so the search counts. This is rare, and main accepted it.

**Accepted cost of the rule (main, 2026-11-01).** While the model is out of reach, the daily limits do not stop a
visitor. The limit of 300 requests an hour still holds, and each try pays one on-topic check of
about $0.00002 on TypeSafe, so about $0.006 an hour per visitor at most. A Surprise me pick fails
for free in an outage.

**Not changed.** `begin_on_demand_run` (006): no code calls it, and a migration after the launch
drops it.

## The likely-topic fill (step 3, approved 2026-11-01, not run)

**What visitors typed.** `on_demand_runs` has 21 searches on 19 names. 18 of the 19 now have
published items. Only "Space oceans" has none (its one item was discarded), so visitors give one
topic directly. The other 29 are classics, chosen to match how visitors type and what they asked
about: short plain names, exotic physics (Antimatter, Wormholes), missions (Skylab, James Webb) and
well-known objects (Olympus Mons).

**Names are short on purpose.** A search matches the bank only on the exact name, ignoring case
(`topic_named` in `agent/bank.py`). "Why Mars is red" does not serve a visitor who types "Mars".
So "Moon" does not match "The Moon" either; only the list of suggestions helps there.

**Checked against the live bank (read-only):** 30 distinct names, and none has a topic row except
"Space oceans".

| # | Topic | Group | Why | Eval |
| --- | --- | --- | --- | --- |
| 1 | Mars | Solar system | Classic | eval |
| 2 | Jupiter | Solar system | Classic | eval |
| 3 | Saturn | Solar system | Classic | eval |
| 4 | The Moon | Solar system | Classic; a visitor asked about its dark side | eval |
| 5 | Pluto | Solar system | Classic | eval |
| 6 | Comets | Solar system | Classic; a visitor asked about meteoroids | eval |
| 7 | Meteor showers | Solar system | A visitor asked about meteoroids | |
| 8 | Enceladus | Solar system | Goes with "Space oceans" | |
| 9 | Lunar eclipses | Solar system | A visitor asked about solar eclipses | |
| 10 | Supernovae | Stars | Classic | exact |
| 11 | Neutron stars | Stars | Classic | eval |
| 12 | Betelgeuse | Stars | Classic | |
| 13 | Alpha Centauri | Stars | Classic | |
| 14 | Brown dwarfs | Stars | A visitor asked about red dwarfs | |
| 15 | Constellations | Stars | Classic | |
| 16 | Nebulae | Stars | Classic; a visitor asked about cosmic clouds | eval |
| 17 | Dark matter | Cosmos | Classic | exact |
| 18 | The Milky Way | Cosmos | Classic | eval |
| 19 | Andromeda Galaxy | Cosmos | Classic | eval |
| 20 | Exoplanets | Cosmos | Classic; a visitor asked about the Drake equation | eval |
| 21 | The Fermi paradox | Cosmos | A visitor asked about the Drake equation | |
| 22 | Time dilation | Cosmos | Visitors asked about wormholes and antimatter | |
| 23 | Hawking radiation | Cosmos | Visitors asked about black holes | |
| 24 | The observable universe | Cosmos | Classic | |
| 25 | The Space Race | Exploration | A visitor asked about space travel | |
| 26 | Cassini-Huygens | Exploration | Classic mission | |
| 27 | New Horizons | Exploration | Classic mission | |
| 28 | Parker Solar Probe | Exploration | Classic mission | |
| 29 | Space debris | Exploration | Classic | |
| 30 | Space oceans | Visitors | Typed by a visitor; no published item | |

**Reserves with no eval overlap:** Oort cloud, Yuri Gagarin, The speed of light, Kepler Space
Telescope, The multiverse.

**Left out on purpose:** Artemis and Starship. They change quickly, and evergreen topics never
retire, so their items would go out of date.

**Estimate.**

- Jobs: 179, which is 30 topics x 6, less the 1 "Space oceans" job already tried. `daily` can
  retry that slot.
- Anthropic: about **$4.50 to $5.00**. The 2 October build measured $4.98 for 180 jobs. The mean
  since 20 October is about $0.025 a job, or about $4.50.
- TypeSafe: about $0.04, from the prepaid balance.
- Time: about 19 minutes on 3 workers (174 jobs took 18 min 18 s on 2 October).

**The cap it counts against.** Only the Console limit: the "$5 for the 30-topic fill" line in
November's $32. It does not count against the $20 live cap or the $3.25 daily cap, because those
read only `on_demand_runs`, and Curator runs do not write there. The `--cap` is a hard stop on
this one run. A job reserves its $0.17 limit before it starts, so with `--cap 5.00` no job starts
once the spend passes $4.83. At the top of the estimate, about 5 jobs stay open, and `daily` takes
them from its own budget.

**What the fill gives.** Learn and Quiz list a topic only when all 6 slots are published.

- By the measured rates, about 36% to 48% of items go to review (65 of 180 in the first build, 10
  of 21 in the last fill) and about 8% to 14% are discarded. Expect about **65 to 85 items in
  review**, on top of the 5 there now.
- Few topics reach 6 slots without that review, so the Learn and Quiz lists grow only after Vedant
  works through the queue (`python -m curator review`, free). The later the fill, the less time
  this leaves before the launch on 3 November.

**Before it runs:** a working key (the local `.env` key too, with the one cheap test call from
earlier fills, on Vedant's word), and the Console at $32.

**Also found:** `on_demand_runs` has no run between 2026-10-30 00:19 UTC and the cutoff. So the "2
real local searches" of the deploy order left no row there, and Vedant's live search may be the
first real parallel search. Main should weigh this when reading its result.

## Current goal

Make a live search on the Explore page run all six items at once instead of one at a time, so
it ends in about 25 to 35 s instead of about 100 s, and build November's budget, both before
the LinkedIn launch on Tuesday 3 November. Go/no-go on Sunday 1 November: if parallel search is
not deployed and verified on the live site by then, the launch runs on the current version.

Read first: `docs/PLAN.md`, "Faster live searches: every run at once" (the plan, its
measurements and decisions) and "The launch week's code review and November's budget" (the
build list, and the decision recorded at its end), and the 2026-10-28 latency entries under
Decisions in `docs/SESSIONS.md`.

## Where things stand

- **This folder:** `../cqa-latency` (`C:\Users\vedan\cqa-latency`), a git worktree on
  `session/latency`, with its own `.venv` (Python 3.12.10), `node_modules` and a copy of `.env`
  (load it with python-dotenv and an explicit path, `load_dotenv(".env")`; never `source` it).
- **`main`** has everything so far and was pushed on 2026-10-28: universal topics and Surprise
  me (the explore session, now closed) and this session's docs. `session/latency` started the
  2026-10-30 work at `main` (`200185a`).
- **The live bank:** migration 009 applied. After two fills, a Jev re-check and the review
  queue, 37 of 44 topics are on every level. 8 slots are missing on 7 topics: 2 open to a retry
  (the daily run takes them) and 6 out of tries, listed in `docs/PLAN.md` under "Universal
  topics", waiting for Vedant to decide what to do with them. The review queue is empty.
- **Keys and limits:** Vedant changed the TypeSafe key on 2026-10-28 (the old one returns
  401); the new one is in all three local `.env` files, Vercel and the GitHub Actions secrets.
  The Anthropic workspace hit its October limit; Vedant raised it by about $2 (an exception to
  hard rule 1). October's spend after this session's runs is close to that new limit, so keep
  paid work small until 1 November.
- **Checks** (`.github/workflows/checks.yml`), run here before the push: see the session log in
  `docs/PLAN.md`.
- **Decided, not yet built:**
  - November: option A. Launch days 14 searches a day for everyone, 5 a visitor, $3.25 a day;
    $20 for live research in November, ending on 1 December; Console at $32 for the month (changed 2026-10-30).
  - Parallel search: reserve every run at the start ($0.17 each, $1.02 a search), the usual
    daily cap $1.55, partial fit in plan order, questions played easiest first, a tagged agent
    log, one log line for every 429 (Vedant agreed to this in place of a count per run).

## Done

- On `main` (landed at `a8c5947`, not pushed): November's budget (`afcfe33`, `37a6696`, `48c49c5`, `a712d09`) and the 429 hook (`a8c5947`).
- `f136300`: progress events per live run (stage and status line); `progressed` in `src/search.ts`.
- `ac435e0`: `AgentLog.tsx` item tags and the `open` prop; `itemTag` in `src/search.ts`.
- `537f4ed`: migration 010, its fold into `supabase/schema.sql`, and `supabase/checks/010_parallel_searches_check.sql`. Main approved the SQL.
- `6cc26b4`: parallel search (one reservation call, a named thread per item, $1.55 usual daily cap, `RunTimes`).
- `53fffc3`: the page accepts `estimate_seconds`.
- `c1333cf`, `b237318`, `6db69b4`: plan, sessions and handoff records.
- `14290fc`: a failed run-time read waits 60 s before the next try (main's review). Test added.
- `170fc92`: the verifiers' pool threads take the run's thread name, so their 429 lines name the item (approved by main).
- `2106039`: the log's tag column widened to 96 px, no wrap ("MEDIUM EXPL" wrapped at 64 px in the drive).
- Main approved `a8c5947..6db69b4` for the drive and the real searches.
- Headless drive against the free stub API (2026-10-30): every check passed, no console errors.
- Drive, full search: first question at 3.3 s; search ended at 6.4 s. The stub's six runs take 2 to 6 s each, 23.5 s in a row.
- Drive, full search: questions played EASY, MEDIUM, HARD although the EASY explanation finished first; log lines tagged and interleaved; explanations open on EASY.
- Drive, phone width 390 px: no sideways scroll.
- Drive, caps fitting 3 items: the 3 questions made; the explanations say "Not started" with today's budget; ended at 5.8 s.
- Drive, stream: 6 results, 36 progress events, every stage with real status lines ("Reading science.nasa.gov"), each item on thread `live-search-<id>-<key>`.
- Dev servers on 5173 and 8787 and the scratch Chrome on 9333 stopped after the drive; all three ports confirmed free.
- Checks pass at `2106039`: 379 Python tests, 155 TypeScript tests, ruff, ruff format, mypy, typecheck, build.

## Next

1. Deploy order. `session/latency` lands on `main` only after all of these:
   a. Vedant pastes migration 010 into the Supabase SQL editor.
   b. Vedant runs `supabase/checks/010_parallel_searches_check.sql`; it must say "CHECK PASSED".
   c. The headless drive passes (done 2026-10-30).
   d. 2 real local searches pass (about $0.17 each, asked one by one).
   The code calls `begin_on_demand_search` only, so before 010 every live search answers "unavailable".
2. Real search times: "before" from one read-only query on `on_demand_runs` (last `finished_at` less first `started_at` per search); "after" from the real searches. Not measured yet.
3. 1 live search after the deploy.
4. `CHANGELOG.md` entry with the before and after times.
5. `docs/DEVELOPMENT.md` for parallel search (approved).
6. Deploy hook with its `curator.yml` env line (approved).
7. The 30-topic fill list for Vedant; on or after 1 November.
8. Per-account limits (after data lands); fold 011 and 012; other sessions' changelog text.

## Blockers

- Vedant: paste 010, then the check script.
- Vedant: approve each real search (paid). Main asked for no real search in this step.
- `src/pages/ExplorePage.tsx` (ui owns it) still says a search takes "about two to three minutes in all" (line 833). With parallel search it is about 30 s. For ui.
- Per-account limits: wait for data's `agent/auth.py` and `src/session.ts` on `main`.
- Migrations 011 and 012: wait for data and media.
- `CLAUDE.md` and `docs/DESIGN.md` drafts: wait for Vedant's approval.
- Vedant: Console to $32 before 3 November; rate-limit tier before the go/no-go.

## Rules to keep in mind

- Edit only the files this session owns (`docs/SESSIONS.md`, "latency owns"); for any other,
  stop and ask Vedant. `docs/DESIGN.md` and `CLAUDE.md` are his.
- Stage by path. Never `git add -A`, `git stash`, `git reset --hard` or `git checkout -- <file>`.
- One session at a time runs the dev servers; never stop a server this session did not start.
- No emojis; commit only when Vedant asks; append each new decision to `docs/SESSIONS.md`.

## Files touched

- `docs/PLAN.md`: the parallel-search plan; the 2026-10-22 section and November's decision at
  its end; the Universal topics section (from the explore handoff) with its landing, the fills,
  the Jev re-check, the review queue and the superscript finding; the session log.
- `CHANGELOG.md`: the 2026-10-28 entry (from the explore handoff) and the bank fill.
- `docs/NEXT_SESSION.md`: the 2026-10-22 update; frozen since.
- `docs/SESSIONS.md`: this session's row, the open questions answered, Decisions appended, the
  uncommitted work marked resolved.
- `docs/handoff/latency.md`.
- Outside git: `TYPESAFE_API_KEY` in the three local `.env` files.
- 2026-10-30, committed: November's budget and the 429 hook (on `main`); `agent/ondemand.py`,
  `agent/store.py`, `agent/limits.py`, `agent/verifiers/__init__.py`, `api/research.py`,
  `api/quota.py`, `src/types.ts`, `src/api.ts`, `src/api.test.ts`, `src/search.ts`,
  `src/search.test.ts`, `src/components/AgentLog.tsx`, `src/components/AgentLog.test.tsx`,
  `tests/test_ondemand.py`, `tests/test_quota.py`, `supabase/migrations/010_parallel_searches.sql`,
  `supabase/schema.sql`, `supabase/checks/010_parallel_searches_check.sql`, `docs/PLAN.md`,
  `docs/SESSIONS.md`, `docs/handoff/latency.md`.
- Outside git (scratchpad, not committed): the stub API and drive scripts, and their screenshots.

## Pre-launch overhaul additions (brief from main, 2026-10-30)

The 2026-10-30 grill-me (`docs/SESSIONS.md`, Decisions, and `docs/handoff/main.md`) added work
to this session and four new sessions beside it: data (accounts), ui (header, cards, progress
rows, ranks), seo (the rename to Curiosity, metadata, prerendering, redirects) and media (topic
images). Everything ships before the launch; code freeze **Monday 2 November 18:00 Dublin**.
This session stays on the critical path; November's budget and parallel search come first and
are must-ship.

On Windows, the existing worktree `C:\Users\vedan\cqa-latency` carries on: with a clean
`git status`, run `git rebase main` there after pulling `main` (its 2026-10-28 work is already
on `main`). On a machine without it, `dev/new-session.sh latency` makes a fresh one.

### Added to "Next"

1. **November's budget** (step 3 above): merged and deployed by **Saturday 31 October**.
2. **Parallel search** (step 4 above), with migration **010** (the number is reserved for you;
   data has 011 and media 012). Go/no-go Sunday 1 November as decided.
3. **Progress events** for ui's new progress rows: each item's stage as it changes (search,
   fetch, write, verify, done or failed) and an estimate in seconds from the measured median for
   its mode and level (the `run_stats` data; say which query or constant, and how it is kept
   current). The event types go in `src/types.ts`, which you own; ui reads them. Keep the
   existing log lines.
4. **`AgentLog.tsx`**: a prop or hook so ui can put it behind "Show details".
5. **Likely-topic fill** (Q20): 30 topics, about $5, on or after 1 November, from November's
   budget (say which cap it counts against). Choose them from what visitors have typed
   (`on_demand_runs`) plus the classics, and list them for Vedant before running.
6. **Deploy hook:** after the Curator publishes a new topic, call the Vercel deploy hook
   (secret `VERCEL_DEPLOY_HOOK_URL` in GitHub Actions, made by Vedant) so seo's prerendered
   pages pick it up. At most once per Curator run.
7. **Per-account limits** (Q5), once data's `agent/auth.py` and `src/session.ts` are on `main`:
   `api/research.py` and `api/quota.py` key a signed-in visitor's limits by account (same numbers),
   guests by the salted IP hash as now; `src/api.ts` sends data's `authHeader()`. Global caps
   unchanged. This is part of accounts, so it is cut with them if they are late.
8. **Fold migrations 011 and 012** into `supabase/schema.sql` as they land.
9. **Docs:** `docs/PLAN.md`, `CHANGELOG.md` and `README.md` stay yours, except the README rename,
   which seo makes. Fold in the other sessions' changelog text.

### Ownership changes

- `api/topics.py` passes to media for the image fields.
- `supabase/migrations/011_*.sql` and `012_*.sql` are written by data and media; you keep
  `schema.sql` and `010`.

## Drafts for Vedant's files (not applied; approve or change the text)

`CLAUDE.md`, hard rule 1, after "(Changed 2026-10-01; ... See `docs/PLAN.md`.)":

> Dated exceptions, decided by Vedant: October 2026's limit was raised by about $2 on 2026-10-28,
> when the bank fill met it; November 2026's is $32 ($20 for the launch month's live research,
> about $5 for the daily Curator, $5 for the 30-topic Curator fill, $2 spare), back to $10 on
> 1 December. Both are in
> `docs/PLAN.md`, "The launch week's code review and November's budget".

`docs/DESIGN.md`, decision 8, the cost line, after "(capped at $10 a month)":

> (dated exceptions: October 2026 about $12, November 2026 $32 for the launch; decided by
> Vedant on 2026-10-28)

`docs/DESIGN.md`, decision 9, the launch sentence, replacing "5 searches a visitor and 20
searches and $2.50 a day for everyone; the $4 monthly cap is unchanged":

> 5 searches a visitor and 14 searches and $3.25 a day for everyone, and live research has $20
> for the calendar month of November (changed 2026-10-28 by Vedant; it was 20 searches and $2.50
> a day under the usual $4 month)
