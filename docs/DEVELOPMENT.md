# Development

How to run Cosmic Quiz on your own machine, run its checks and find your way around the code.
The [README](../README.md) is the overview, and [`DESIGN.md`](DESIGN.md) is the decision record.

## What you need

- Python 3.12.
- Node.js 24 and pnpm. `package.json` pins pnpm 11.5.0 in its `packageManager` field.
- For the agent only (the checks need none of these): a Supabase project (the free tier is
  enough), an Anthropic API key and a TypeSafe API key. Give the Anthropic key its own Console
  workspace with a spend limit; this project's is $10 a month.

## Set up

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pnpm install
cp .env.example .env                 # then fill in the keys
```

`.env` is never committed. What each value is for:

| Variable | Used by | What it is |
|---|---|---|
| `ANTHROPIC_API_KEY` | the agent | Claude Haiku 4.5: research, writing and the layer 2 verifier |
| `TYPESAFE_API_KEY` | the agent | Jev: the layer 3 checks and the on-topic check |
| `SUPABASE_URL` | everything that reads or writes the bank | the project's URL |
| `SUPABASE_SECRET_KEY` | the Curator and the server only | bypasses row-level security; never sent to a browser |
| `SUPABASE_PUBLISHABLE_KEY` | the API's public reads | can read only published items |
| `IP_HASH_SALT` | the API | salts the visitor hashes and keys the answer-reveal tokens; long, random and secret |
| `AGENT_MODEL` | optional | overrides the model (default `claude-haiku-4-5`); it needs a price in `agent/config.py` |

## The database

Paste `supabase/schema.sql` into the Supabase SQL editor. It includes every migration, so a new
project needs nothing else. `supabase/migrations/` keeps the changes made after the first build,
in order, for a database that already exists. `supabase/checks/` holds checks to paste after a
migration: each tests the new functions on the live bank and undoes its own rows (it always ends
with an error message, "CHECK PASSED" or "CHECK FAILED").

## Run it

```bash
python -m curator build --topics 3   # research a few topics into the bank (paid; asks first)
python -m dev.api_server             # the API, on port 8787
pnpm dev                             # the site, on port 5173; it sends /api to the server above
```

The command-line tools, and what each one costs:

| Command | What it does | Cost |
|---|---|---|
| `python -m agent learn "Pulsars"` | one explanation at EASY, printed step by step; `--verify` adds the checks | about $0.02 |
| `python -m agent quiz "Pulsars" --difficulty hard` | one quiz question, with all three checks | about $0.03 |
| `python -m curator build` | the 30 evergreen topics, each in both modes at three levels | about $5, capped at $6 |
| `python -m curator daily` | fills up to 6 missing levels, then one topic from the NASA and ESA news, and retires old items | about $0.17, capped at $0.40 |
| `python -m curator complete` | every level a listed topic still lacks (3 tries a level) | about $0.03 a level, capped at $3 |
| `python -m curator fill` | the 30 likely topics visitors will type, each in both modes at three levels; by hand only | about $5, capped at $5 |
| `python -m curator.images` | a picture (NASA or Wikimedia, credited) or a fact card for each topic; `--dry-run` first | free |
| `python -m curator review` | shows each item in review with its sources; you publish or discard it | free |
| `python -m curator review --reported` | the same for items that players' reports have hidden | free |
| `python -m curator upkeep` | stores left-over runs, retires stale items, clears old visitor hashes | free |
| `python -m curator rejev` | re-runs Jev checks that failed | under a cent |
| `python -m evals run` | the 60-item eval (`docs/EVALS.md`); `seed`, `verify-seeded` and `report` follow it | about $2 |
| `python -m evals export` | writes the eval history the analytics page shows | free |
| `python -m dev.check_stats` | compares the live `agent_stats()` with a Python version of it, read-only | free |

The Curator and eval commands print their cost estimate and ask before spending. Every run's
tokens and cost are logged, and the full record of a command-line run is saved under `runs/`.

## The checks

```bash
pytest
ruff check . && ruff format --check .
mypy --strict
pnpm typecheck && pnpm test && pnpm build
```

None of them calls a paid API or the network: the Python tests use a scripted fake model and a
fake web (`tests/conftest.py`). The same commands run on every push and pull request in GitHub
Actions (`.github/workflows/checks.yml`), with no secrets. For dependencies, `pip-audit` (a dev
tool in `requirements-dev.txt`) and `pnpm audit`.

## Deploying

- **Vercel** builds the site with `pnpm build` and serves `dist/` and the Python functions in
  `api/`, in the Dublin region. `vercel.json` holds the security headers, caching, the routing
  and the redirect from the old address. The functions need every variable above except
  `AGENT_MODEL`.
- **GitHub Actions** runs the Curator every day (`.github/workflows/curator.yml`). It needs the
  secrets `ANTHROPIC_API_KEY`, `TYPESAFE_API_KEY`, `SUPABASE_URL` and `SUPABASE_SECRET_KEY`.
  After the Curator it fills topic images (`python -m curator.images`, free), and when the run
  published anything it calls the Vercel deploy hook once, so the prerendered pages are rebuilt.
  The hook's URL is the secret `VERCEL_DEPLOY_HOOK_URL`; without it, that step skips.

## The live-search limits

Every limit and cap is a number in `agent/limits.py` (`LimitSettings`), passed to the database
on each call, so a change is a reviewed code change and a deploy. A temporary change is a dated
set that `limits_at(now)` picks for each request, so it starts and ends by itself: November 2026
(`NOVEMBER_LIMITS`, $20 a month for live research) and, inside it, the launch week of 3 to 9
November (`LAUNCH_LIMITS`). Keep the monthly cap (`usd_per_month`) under what the Anthropic
Console limit leaves after the daily Curator.

A live search runs the EASY question first and alone, then its other items together
(`agent/ondemand.py`). With the EASY question in the bank, every live item starts together. If the
EASY question fails with nothing spent, the others never start: each settles as failed with nothing
spent, and migration 013 does not count the search. One database call
(`begin_on_demand_search`, migration 010) counts the search and reserves every run at $0.17, in
plan order, while today's and the month's caps fit; the items a cap leaves out are reported as
not started. So the day's last search can still make every item only when the daily cap holds
(`searches_per_day` - 1) searches plus one whole reservation of 6 runs: $1.55 for the usual 4
searches, $3.25 for the launch week's 14. Raise `usd_per_day` with `searches_per_day`.

Each run streams progress events for the page's progress rows, with its usual time from
`live_run_estimates()` (the median of the last 30 days of runs at its mode and level). Each run
has its own thread, named `live-search-<search id>-<item>`, and `api/research.py` logs every 429
from Anthropic with the thread's name, so the logs say which item met a rate limit.

## The repository

| Path | What it holds |
|---|---|
| `agent/` | the agent core, shared by the Curator and the API |
| `agent/loop.py` | the tool-calling loop and its budgets |
| `agent/llm.py` | the provider interface and its Anthropic implementation |
| `agent/tools/` | Wikipedia, arXiv, NASA, the news feeds and `fetch_page` with its allow-list |
| `agent/verify.py` | layer 1: cited URLs fetched, quotes word for word, numbers on the pages |
| `agent/verifiers/` | layer 2 (`haiku.py`) and layer 3 (`jev.py`) |
| `agent/gate.py` | the publish rule: published, review or discarded, from the stored results |
| `agent/ondemand.py` | a live search: the limits, the EASY question and then the rest, the streamed log and progress |
| `agent/limits.py` | the live-search limits and caps, and `limits_at`, which picks the dated November and launch-week numbers |
| `agent/store.py`, `agent/bank.py` | the database: writes with the secret key, public reads |
| `agent/web.py` | the HTTP layer the functions in `api/` share |
| `curator/` | the scheduled Curator: build, daily, complete, review, upkeep, rejev, and the topic images |
| `api/` | the Vercel functions, one file per endpoint |
| `src/` | the React and TypeScript site, with its Vitest tests beside the code |
| `tests/` | the Python tests |
| `evals/` | the fixed eval set and its scoring |
| `supabase/` | the schema, its migrations, and the checks to paste after a migration |
| `dev/` | the local API server and the statistics check; never deployed |
| `public/` | the scenes, the fonts and the link-preview image |
| `docs/` | the design record, the session-by-session plan, the evals, the security audit and this page |
