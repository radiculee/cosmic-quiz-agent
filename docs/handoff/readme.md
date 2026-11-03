# Handoff: readme

Launch day, Tuesday 3 November 2026. Branch `worktree-agent-ad519171765432cf2`, from `e4ed271`.
Work commits: `18b91e9` (images), `10d9ff7` (README), `6ed5e54` (this file). The head is the commit
that makes main's two review fixes (2 findings on `6ed5e54`).
Not pushed, not merged.

## Done

- `README.md` rewritten to agree with the live site. Facts still true are kept as they were.
- Four images in `docs/images/`:
  - `home.webp` (new): the live home page, from a clean browser profile.
  - `quiz-answer.webp` (replaced): the live site. The old one showed the answer before the button row.
  - `analytics.webp` (replaced): the live site. The old one showed October and the $10 limit.
  - `agent-log.webp` (replaced): the free stub. The old one showed one item at a time, with no bars.
- The README no longer uses `public/og-v1.jpg`. Nothing in `public/` changed.

### Each claim changed, with its source

| Claim | Source |
|---|---|
| Hero is `docs/images/home.webp` | Live home page, shot today |
| Renamed from Cosmic Quiz on 30 October 2026; the repo keeps its name | `CLAUDE.md`, `docs/DESIGN.md` |
| 39 topics | Live `/api/topics`, home page |
| Quiz runs of 10 or 30; 60 opens as the bank grows | Live `/quiz`: "EASY: 39 of 60 questions so far. 60 opens as the bank grows." |
| Right or wrong at once, then the buttons; panels start closed and stay as last left | Live quiz, `src/components/CardActions.tsx`, `src/panels.ts` |
| Surprise me, easy question first, three bars, explanations line, Show details, results card | Stub drive of this commit's code; `agent/ondemand.py`; `src/webResults.ts` |
| Rover ranks, Sojourner to Perseverance, with facts and source pages | `src/game.ts`, live home page |
| Sticky header with navigation and page settings | Live site |
| Six items, own thread, easy first; a refused key costs one call, not six | `agent/ondemand.py`, `docs/PLAN.md` "The EASY question first" |
| 163 of 391 runs (42%); 166 review; 34 discarded; 28 no answer; 70 Jev errors; 295 published | Live `/api/stats`, Mission Control. 28 is 391 less 363 answers. Rule for errors: `_combine` in `agent/gate.py` |
| 4 searches and $1.55 a day, $4 a month (README said $0.50) | `agent/limits.py` `LimitSettings` |
| 2 searches, 300 requests, 10 reports; launch 5, 14, $3.25; November $20 | `agent/limits.py`; live `/api/quota` says limit 5 |
| A search reserves all its runs when it starts, up to $1.02 | `agent/limits.py`, `agent/config.py` ($0.10 + $0.07 a run), 6 runs |
| A search with every run failed and nothing spent does not count | `CHANGELOG.md` 2026-11-01, migration 013 |
| 145.2 s (118.9 to 171.6 s, n=4); 61.3 s and 49 s (n=1) | `CHANGELOG.md` 2026-11-02, `docs/handoff/latency.md` |
| Easy-first order: first question 21.6 to 41.2 s, whole search 50.0 to 97.0 s (n=3; one search made 5 items) | Main's read of `on_demand_runs`, 3 November (searches 104, 110, 115). I did not query the table |
| The two six-item easy-first searches cost $0.1561 and $0.1511 | The same read (searches 104 and 115) |
| About 20 s one-time cost, inferred | `CHANGELOG.md`, `docs/handoff/latency.md` |
| "Under a minute" and "a minute or two" | Live `/explore` |
| Prerendered pages with their own tags and text; 43 sitemap addresses | Live `/sitemap.xml`, `/learn/antimatter`; `scripts/prerender/` |
| Eight addresses redirect permanently, path kept (308 on the live site) | `curl` on each today; `vercel.json` |
| `/lern` and near-match 404 | `src/closeMatch.ts`, `docs/handoff/seo.md`. The live `/lern` answers 200 and the app moves it |
| 391 runs for $10.05, $0.026 a run, $0.062 an item; 20.1 s, p95 42.7 s | Live `/api/stats`, Mission Control |
| Caching saved $2.87, about a quarter | Mission Control; 2.87 of (8.24 + 2.87) is 26% |
| A six-item search about $0.17 is an estimate; one measured at $0.20 (n=1) | `docs/PLAN.md` line 1922, `agent/limits.py`; `docs/handoff/latency.md` ($0.2005) |
| CSP allows itself plus connections to the Supabase address | Live header, `vercel.json` |
| Sign-in off; Learn card pictures not live | Live site shows neither; `src/session.ts`; `/api/topics` has no image field. Migrations 011 and 012 not applied: from main's brief |

### Removed as old

- The 13 October search on James Webb (86 s, $0.097, four items).
- "A live search of four items costs about $0.12".
- 54%, 115 of 213, $5.89, $0.028, $0.051, 19.2 s, 36.2 s (as of 13 October, replaced by today's).

## In progress

Nothing.

## Left

- Replace the stub picture with a shot from a real search.
- Mission Control's figures move every day. The README dates them to 3 November 2026.

## Blocked on

Nothing.

## Needs from Vedant

1. **The search picture.** It is from the stub, and the README says so beside it. The topic, the
   `science.nasa.gov/universe/exomoons` address, the scores and the clock are made up. If you want
   a real one, shoot it from a launch search. I recommend this. I also changed the scratch stub's
   Haiku line: its fake record said "borderline" beside "Publish gate passed", which the real gate
   cannot do, so the guarded copy makes that line say "pass". The change is in the scratchpad only,
   not in the repo.
2. **The published share went down.** The README used to say 54%, and today's figure is 42%, because
   it agrees with Mission Control. It is the truth, and a recruiter who opens the site sees it.
3. **A wrong sentence on the live site.** The ISS EASY item's explanation says 1 January 1998 is when
   the first ISS module was launched. From my own knowledge, Zarya launched on 20 November 1998; I did
   not open a source. I kept this item out of the screenshot. Please check it. The site's Report
   button, then `python -m curator review --reported`, is the way to take it out.
4. **`public/og-v1.jpg`** still says COSMIC QUIZ in link previews, until your `og-v2.jpg`.
5. Keep or remove "In the code, not on the site". I added it so the README does not disagree with
   `CLAUDE.md` for a reader of the repo.

## Files changed

- `README.md`
- `docs/images/home.webp` (new), `agent-log.webp`, `analytics.webp`, `quiz-answer.webp`
- `docs/handoff/readme.md` (this file)

### Other files that need a change (not changed; outside this brief)

- `docs/DEVELOPMENT.md` line 3 says "How to run Cosmic Quiz".
- `docs/DESIGN.md` line 58 still gives the $0.50 cap, line 52 the old launch numbers, line 121 "up to
  4 runs, one at a time". Latency's handoff has drafts for some of these. The file is Vedant's.
- `CLAUDE.md` describes sign-in as part of v1, with no note that it is off for the launch.
- `docs/handoff/seo.md` says the redirects are 301. They are 308.
- `CHANGELOG.md` has no line for this README rewrite, and its 2026-11-02 entry still says the
  easy-first order "has not been measured yet", with "up to about 90 s".

## Checks run

- Rendered with `gh api -X POST markdown --input req.json`, `"mode": "markdown"`, and looked at a
  screenshot of every part, with the diagram drawn. All five images load. No console errors.
- After main's two fixes: rendered the same way again and looked at the table and the Cost section.
- Every relative link and image path exists. Live site, `/sitemap.xml`, `/privacy` and
  vedantgaikwad.ie answer 200.
- Search for "cosmic.", "Cosmic Quiz", "COSMIC QUIZ", "sign in", "account", "image": each hit is
  correct. `cosmic.vedantgaikwad.ie` and "Cosmic Quiz" appear once each, as history. "No accounts" is
  true of the live site. README non-ASCII and control characters: none.
- `pnpm install --frozen-lockfile`; `pnpm test`: 278 passed. pytest on `tests/test_packaging.py` and
  `tests/test_seo.py`: 26 passed. No test reads the README, although the brief expected some.
- No real search, no Curator, no paid call. Stub: a scratchpad copy with `load_dotenv` turned off and
  an assertion that no paid key is in its environment.
- Each image looked at: no personal data. Trophy pop-ups dismissed. Ports 8791, 4181, 4182 and 9444 and
  the scratch Chrome were this session's, and all are stopped. Port 8787 was not used.

### Found on the way

The stub at `6aee6f91-.../scratchpad/stub_api.py` removes the paid keys, then `load_settings()` calls
`load_dotenv()`, which searches up from `agent/`. A `.claude/worktrees/` worktree sits inside the main
folder, so from such a worktree that search should find the main `.env` and bring the keys back. I
read this from the code and did not run the old copy to test it. Its fakes make no paid call, but use
the guarded copy (`9fca8f3d-.../scratchpad/make_stub.py` shows the two changes that keep the keys out,
and `fix3.py` beside it the Haiku line).

The premise "the Live line links to cosmic." was already fixed at `e4ed271`.

## Facts I could not verify

- Migrations 011 and 012 not applied, and no image uploaded: from main's brief. The public site shows
  neither feature, which agrees.
- The Anthropic Console limit is really $32. Mission Control's $32 is a dated number in the code, not
  a read of the Console.
- The easy-first figures and costs: from main's read of `on_demand_runs`. I have no access to that
  table and did not run a search.
- The explanation text in the Apollo 11 screenshot (such as "600 million viewers") comes from the bank.
  I did not check it against a source.
