# Handoff: explore

Notes for the explore session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for
this session. Update them before finishing, and commit them on `session/explore`.

Last update: 2026-10-28 (after the universal-topics and Surprise me commits)

## Current goal

Universal topics and Surprise me, decided by Vedant in a grill-me session on 2026-10-28:

1. **Universal topics.** Learn and Quiz offer the same topics at every difficulty. A topic is
   listed only once it has a published explanation and question at easy, medium and hard.
2. **No difficulty on Explore.** Every live search makes a question and an explanation at each
   level.
3. **Surprise me.** The agent picks a topic the bank does not have yet, and the search runs on it.

The decisions are in "Text for docs/PLAN.md and CHANGELOG.md" below.

## Done

Three commits on `session/explore`, on top of `21a74b5`:

- `f1934b0` Fill every topic at every level with the Curator.
  - Migration `009_universal_topics.sql`, mirrored in `supabase/schema.sql`:
    - `missing_slots()`;
    - `curator_runs.trigger` accepts `complete`;
    - seven renames, and "Bang" merged into "The Big Bang".
  - `MissingSlot` and `SupabaseStore.missing_slots()` in `agent/store.py`.
  - `MAX_SLOT_ATTEMPTS`, `can_retry` and `open_jobs` in `curator/pipeline.py`.
  - In `curator/__main__.py`:
    - `daily` fills up to `FINISH_JOBS_PER_DAY = 6` missing slots before its news topic;
    - new `complete` command (default cap `COMPLETE_CAP_USD = 3.00`), with `report_missing`.
- `1036a3f` List only topics that are on every level. `BankTopic.complete` in `agent/bank.py`;
  `api/topics.py` returns complete topics only.
- `27fa151` Make Explore research every level, and add Surprise me.
  - `plan_search(have)` with no difficulty, in `agent/ondemand.py`.
  - `runs_per_search` goes from 4 to 6 in `agent/limits.py`. The dollar caps are unchanged.
  - `research()` gains the `_surprise` path.
  - New `agent/topic_pick.py` (`HaikuTopicPicker`) and `BankReader.topic_names()`.
  - `api/research.py` takes `{"topic"}` or `{"surprise": true}`, and ignores an old client's
    `difficulty`.
  - The site:
    - `ExplorePage.tsx` loses its difficulty control and gains SURPRISE ME and EASY / MEDIUM /
      HARD explanation tabs;
    - `search.ts` has `explanationSlots`, `firstReady` and a lock over all three;
    - `streamResearch(request)` in `api.ts`;
    - `searchStatus` without a difficulty in `topics.ts`;
    - `explorePath(topic)` in `router.ts`;
    - `AgentLog`, `StatsPanel` and `SearchTab` drop the level.

Checks run in `../cqa-explore` with its own `.venv` on 2026-10-28, matching
`.github/workflows/checks.yml`. All passed:

- `pytest`: 361 passed.
- `ruff check`: clean.
- `ruff format --check`: 98 files formatted.
- `mypy --strict`: no issues in 82 files.
- `pnpm typecheck`: clean.
- `pnpm test`: 149 passed.
- `pnpm build`: built.

The browser check was cut short when the shared main folder changed branch mid-drive. Before it
stopped, these passed:

- no difficulty control on `/explore`;
- an old `?difficulty=` link fills only the topic;
- SURPRISE ME puts the pick in the box and the log;
- a pick skips the on-topic check.

One check failed and is unconfirmed: the empty-box hint should contain "explanations, easiest
first". It may only have been read while the topics were still loading. These were not reached:
answering the questions, the tabs, and the phone width.

Nothing has been spent: no paid run, no migration applied.

## Next

1. **After Vedant lands the branch and applies migration 009**, run
   `python -m curator complete` from this worktree's `.venv`. It asks before spending, and its
   cap is $3. Its closing report gives what is still missing; cross-check it with
   `select mode, difficulty, attempts, in_review from public.missing_slots();` and record the
   result here.
2. **Browser check.** Re-run it in `../cqa-explore` once Vedant says the ports are free; only one
   session at a time runs the dev servers. Use the no-cost stub API, described in Claude's memory
   "drive-app-headless-chrome". Fake `run_learn`, `run_quiz`, `verify_and_decide`, the judge,
   the picker (`Services.picker`), the limits store and `LiveResults`. Set
   `ondemand.RUN_START_SECONDS` to about 4.5 so the sixth run is cut off. Check:
   - no difficulty control, and the hint text;
   - SURPRISE ME, then the three questions easiest first;
   - "Read the explanations" opens on the EASY tab;
   - the MEDIUM tab shows its explanation;
   - the HARD tab says why it was left out and "The agent tries again overnight";
   - no sideways scroll at 390 px.
3. **One real Surprise me search locally** (about $0.17, after checking `/api/quota`), to confirm
   the pick, the six-run order and the cutoff.
4. **Update this session's row in `docs/SESSIONS.md`** once universal topics is on `main`.
5. **Vedant's own files, if he agrees:**
   - **`CLAUDE.md`, v1 bullets:** the web page becomes "a typed topic, or one the agent picks,
     researched live at every level". Add a bullet: "Every topic on Learn and Quiz exists at all
     three levels (changed 2026-10-28 by Vedant)."
   - **`docs/DESIGN.md`:**
     - decision 9: six runs a search;
     - decision 13: no difficulty on the web page;
     - "each topic has a verified explanation per difficulty" becomes a rule enforced by
       listing.

## Blockers

- **Migration 009 is not applied.** Without it, `daily` and `complete` stop with a bank error,
  because `missing_slots()` does not exist. See "Before this is pushed".
- **Ownership.** Most of these files are latency's under `docs/SESSIONS.md`. The work was
  written before that file existed, and it was committed as one unit. Latency builds parallel
  search on top of it once it is on `main`. Explore makes no further edits to latency's files
  without asking Vedant.

## Files touched

- **Python:** `agent/bank.py`, `agent/limits.py`, `agent/ondemand.py`, `agent/store.py`,
  `agent/topic_pick.py` (new), `api/research.py`, `api/topics.py`, `curator/__main__.py`,
  `curator/pipeline.py`.
- **Database:** `supabase/schema.sql`, `supabase/migrations/009_universal_topics.sql` (new).
- **Python tests:** `tests/test_api.py`, `tests/test_curator.py`, `tests/test_ondemand.py`,
  `tests/test_quota.py`, `tests/test_store.py`, `tests/test_topic_pick.py` (new).
- **Site:** `src/api.ts`, `src/search.ts`, `src/search.test.ts`, `src/topics.ts`,
  `src/topics.test.ts`, `src/router.ts`, `src/router.test.ts`, `src/pages/ExplorePage.tsx`,
  `src/pages/LearnPage.tsx`, `src/pages/StatsPanel.tsx`, `src/components/AgentLog.tsx`,
  `src/components/stats/SearchTab.tsx`.
- **This handoff:** `docs/handoff/explore.md`.

## Text for docs/PLAN.md and CHANGELOG.md

Latency owns both files and folds this in. The commit hashes hold if the branch lands on `main`
by fast-forward; after a rebase, use the new ones.

### For docs/PLAN.md: a new section before "## Later - v2: Newsletter"

```markdown
### Universal topics (2026-10-28)

Vedant asked for three changes, decided in a grill-me session on 2026-10-28:

1. **Every topic at every level.** Learn and Quiz showed different topics at each level. On
   2026-10-28, LEARN had 38 / 31 / 31 topics at easy / medium / hard and QUIZ 39 / 31 / 27, so
   27 of 44 topics missed a slot. A slot is a mode at a difficulty. There were two causes:
   - a search on the web page made its explanation at one level only;
   - the Curator never retried a job it had run once (`attempted_jobs`).
2. **No difficulty on the web page.** Every search makes all three questions and all three
   explanations.
3. **Surprise me.** The agent picks a topic the bank does not have yet.

Decisions (Vedant, on the recommended options):

| Question | Decision |
|---|---|
| Visitor-typed rough names | Rename them, then fill. "Bang" duplicates "The Big Bang", so its runs and items move there and the empty topic is deleted |
| Slots that cannot be filled | Learn and Quiz list a topic only when all 6 slots are published (`api/topics.py`). A slot gets 3 tries in all, from the Curator and live searches; runs that ended in `llm_error` do not count. The rest is reported |
| Items in review | A slot with an item in review waits for the review queue and is not retried |
| How the web page makes 6 items | One run at a time as before: the 3 questions, then the explanations, easiest first, until the 180-second start limit. The daily Curator makes the rest |
| Limits | `runs_per_search` goes from 4 to 6, about $0.17 a search. Searches a day and the dollar caps are unchanged |
| The daily Curator | Fills up to 6 missing slots first, oldest topic first, then its news topic while the $0.40 cap allows |
| The one-off fill | `python -m curator complete`, capped at $3 |
| Surprise me's topic | One Haiku call proposes up to 3 topics in a theme drawn at random in code (`agent/topic_pick.py`). Code takes the first valid name not in the bank |
| Surprise me's guardrails | It counts as a search. The limits are read before the paid pick, and a failed pick counts nothing. It skips the on-topic check: visitors' custom topic names are kept out of its prompt, as in `curator/discover.py` |
| The page | SURPRISE ME beside GO. After the questions, EASY / MEDIUM / HARD explanation tabs open on EASY. A level not made says the agent tries again overnight |

Renames (migration 009): Meteroid to Meteoroids, Red light shift index to Redshift, Space Travel
to Human spaceflight, Cosmic clouds to Interstellar clouds, Dark side of the moon to The far side
of the Moon, Wormhole to Wormholes, Drake Equation to The Drake equation. Old Learn addresses for
these topics change.

This replaces "The web page makes whole topics" (Session 8): a search no longer has a chosen
level.

Built:

- Migration 009:
  - `missing_slots()`: every slot a listed topic lacks, with its tries and whether it waits in
    review;
  - `curator_runs.trigger` accepts `complete`;
  - the renames and the merge.
- `python -m curator complete`, and the daily finish step (`curator/__main__.py`,
  `curator/pipeline.py`).
- `BankTopic.complete`, with `/api/topics` listing complete topics only.
- `plan_search` without a difficulty; `agent/topic_pick.py`; `/api/research` takes `{"topic"}` or
  `{"surprise": true}`.
- The web page's SURPRISE ME button and explanation tabs.
- `f1934b0`, `1036a3f`, `27fa151`. 361 Python and 149 TypeScript tests.
```

And a line for "## Session log":

```markdown
- 2026-10-28 - Universal topics and Surprise me. A topic is listed on Learn and Quiz only once
  both modes are published at every level. Live searches make all six items. A new
  `python -m curator complete` fills the gaps (66 slots to retry, cap $3), and the daily run
  fills up to six a day. SURPRISE ME lets the agent pick a topic the bank lacks. Migration 009
  adds `missing_slots()`, tidies seven visitor-typed names and merges "Bang" into "The Big Bang".
  361 Python and 149 TypeScript tests. Nothing spent before the fill.
```

### For CHANGELOG.md: a new "## 2026-10-28" section at the top

```markdown
## 2026-10-28

- **Every topic at every level.** Learn and Quiz now list a topic only once it has an
  explanation and a question at easy, medium and hard, so each level offers the same topics.
  The new `python -m curator complete` fills the gaps, and the daily run fills up to six a day.
  Seven visitor-typed topic names were tidied, and "Bang" merged into "The Big Bang".
  (`f1934b0`, `1036a3f`)
- **Explore researches every level.** The difficulty control is gone: a search makes a question
  and an explanation at each level, and after the questions the explanations open in EASY,
  MEDIUM and HARD tabs. Whatever a search's time limit leaves out, the agent writes overnight.
  (`27fa151`)
- **Surprise me.** A button on Explore asks the agent to pick a topic the bank does not have yet,
  then researches it. It uses one search, and a pick that fails counts nothing. (`27fa151`)
```

## Before this is pushed

Pushing `main` deploys the site, and the scheduled Curator runs from `main`. In order:

1. **Run migration 009 in the Supabase SQL editor.** Paste
   `supabase/migrations/009_universal_topics.sql` and run it once; it is safe to run again.
   - **Before it:** `python -m curator daily` and `complete` stop with a bank error, so the
     scheduled run would fail every day and add no news topic.
   - **Check it:** `select count(*) from public.missing_slots();` should give 67 (the count
     below). `select name from public.topics where name in ('Bang', 'Meteroid');` should return
     nothing.
2. **Know what Learn and Quiz hide until the fill.** Counted read-only on 2026-10-28 from the
   live rows, as `missing_slots()` will count them after the migration:
   - 44 topics listed. 17 are complete and stay visible; The Big Bang stays complete with
     Bang's items added.
   - 27 are hidden until filled, with 67 missing slots: 32 explanations and 35 questions.
   - 66 slots can be retried: 32 explanations and 34 questions.
   - 1 waits in review: Red Dwarfs, quiz medium. `python -m curator review` publishes or
     discards it; Red Dwarfs stays hidden until then.
   - The newest topics may change these counts by the time the migration runs.
3. **Run `python -m curator complete`** after the migration, before the push if possible, so
   the site does not lose 27 topics in the meantime.
   - **What it costs:** 66 jobs, about $1.85 on Anthropic typical (32 x $0.027 + 34 x $0.029).
   - **The cap:** a hard cap of $3 (`COMPLETE_CAP_USD`), plus under $0.02 on TypeSafe. Each
     job reserves its $0.17 ceiling, so a run of bad luck stops at the cap, and the daily run
     finishes the rest, six a day.
   - **The October budget:** October had spent $6.04 of the $10 Console limit by the morning of
     2026-10-28, so $3 fits.
   - **After it:** slots that fail again stay open for one more try (3 in all). Its closing
     report lists every topic still hidden, with each slot's tries.
