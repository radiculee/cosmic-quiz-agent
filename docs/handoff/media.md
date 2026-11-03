# Handoff: media

Notes for the media session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for this
session. Update them before finishing, and commit them on `session/media`.

Last update: 2026-11-03 (media agent: square cards committed, final picture list ready for main)

## Report, 2026-11-03: square cards and the final picture list

Branch `session/media`, rebased on `c23560f`. Nothing is pushed or merged. Main reviews it.

### Done

**The notes commit.** `0ae1d60` keeps the reasons for turned-down pictures in `notes`. The rebase
had no conflict.

**The code change.** `afcf09e` changes `curator/images.py` and `tests/test_images.py`.

- `render` cuts the card directly from the source to a centred 320 x 320 WebP.
- The 1200 x 630 link preview still comes from the source. Its code is unchanged, and a new test
  covers it.
- Minimum source size: the shorter side must be at least 320 px (`CARD_SIZE`), so a card is never
  enlarged.
- Card target 20 KB, limit 32 KB. I started at 30 KB, but the approved Planck map needs 30.9 KB at
  the lowest quality.
- New tests: a square source keeps its whole width, and a wide source gives a centred square.
- No front-end change is necessary. `TopicGrid.tsx` reads width and height from the row, and
  `THUMB` with `object-cover` is already square, on this branch and on `session/ui`. The 640 x 360
  values in `src/` tests are only fixtures.

**The final picture list.**

- 56 cards are rendered, not 55. The bank now has a new topic, Neutron star collisions and
  kilonovae. The fill chooses its picture by itself, so it has no override. Its licence and creator
  match the API, and its card looks good.
- Total bytes for all cards: 672,430 (661,814 without the new topic). The largest card is 30,862
  bytes. 44 of the 56 also get a preview.
- Three cards are over the 20 KB target and under the limit: Skylab and the two CMB maps.
- Light speed: `File:V838_Mon_HST.jpg` is public domain, with no restrictions or non-free flag in
  the Commons API. The Artist field matches the planned credit. Its card looks good.
- `overrides.json` has 27 objects: 11 approved replacements, Light speed, 8 credit corrections,
  6 swaps from step 3 and Red Dwarfs. Each credit is built by `credit_line`, and a script confirms
  that the last match of the licence name is the real licence, so the split in `session/ui` works.

**Cards marked poor at 192 px: 7.** All are swapped. Each swap needs Vedant's approval, because his
plan did not name them.

| Topic | Problem | Now |
|---|---|---|
| The Drake equation | Both ends of the equation cut, captions unreadable | Voyager Golden Record cover, NASA/JPL, public domain. It shows a message to other civilisations, not the equation. The Allen Telescope Array (CC BY-SA 2.0) is the alternative. |
| Types of galaxies | Tiny galaxies, cut caption | PIA14098, 3 x 3 WISE galaxies, NASA/JPL-Caltech/UCLA. All nine survive a square. This is the fill's own choice, so it has no override. It has no elliptical galaxy. |
| The life cycle of a Sun-like star | Heading cut, clutter | ESO "The life cycle of a Sun-like star", ESO/M. Kornmesser, CC BY 4.0 |
| The Big Bang (a keep) | Timeline labels cut | Hubble Ultra Deep Field, NASA and others, public domain. It shows early galaxies, not the Big Bang itself. |
| The Habitable Zone | Kepler-47 diagram labels cut | PIA17999, Kepler-186f artist concept, NASA/Ames/SETI Institute/JPL-Caltech |
| White dwarf planets in second-generation systems | White dwarf lost, only a crescent left | NASA record GSFC_20171208_Archive_e001500, a white dwarf with debris from its planetary system, NASA, ESA, and G. Bacon (STScI). It shows debris, not a planet. |
| Fast radio bursts and their cosmic origins | Nearly all black, thin line | ESO artist's impression that keeps the host galaxy, ESO/M. Kornmesser, CC BY 4.0. It is better but still dark, and the weakest card that is left. |

Titan's lakes and Redshift are less clear than the others, but the subject can still be seen, so I
kept them as planned.

**Credit corrections, read from the Commons API.**

- Meteoroids: ESO/C. Malin
- Event horizons and black hole structure: Event Horizon Telescope/ESO
- Venus's runaway greenhouse effect: JAXA/ISAS/DARTS/Kevin M. Gill (from the file description; the
  Artist field has only Kevin M. Gill)
- Binary star systems: ESA/Hubble & NASA
- Magnetars: ESO/L. Calçada
- Sagittarius A*: EHT Collaboration/ESO
- Quasars: ESO/M. Kornmesser
- Gravitational lensing: ESA/Hubble & NASA, derivative work by Bulwersator

For the two EHT files I kept ESO, because the Attribution field names it and the Artist field names
the EHT.

**Effect of the lower minimum.** Sources under 640 px wide now pass, so the fill's own choice changes
for 2 topics: Planetary nebulae (PIA14443 instead of a fact) and Red Dwarfs (a 604 x 592 Proxima
Centauri picture instead of PIA21473). The overrides cover both. A full dry run shows no other
change.

### In progress

Nothing.

### Left

Main applies the overrides. When you apply them:

1. Render from `download_url`, with the code on this branch.
2. Set `locked` on the override rows. Otherwise `--refresh` replaces them with the fill's own choice.
3. Fill the other topics with this code. The dry run without `--refresh` did not skip Auroras, so it
   has no picture row yet. I did not check the other topics this way.

### Blocked on

Nothing.

### Needs from Vedant

1. Approve or reject the 7 swaps on the sheet. I recommend all 7.
2. Black holes uses the same file as Event horizons, but its credit is still "ESO", because it was
   not on the approved list. It has no override. I recommend the same correction, Event Horizon
   Telescope/ESO. The two cards also show the same picture.
3. The aspect rule is unchanged (0.8 to 2.5). A 2.5:1 source now keeps only 40% of its width in the
   card. No final card is that wide, so I left it. Tell me if you want it tighter.

### Files changed

- `curator/images.py`
- `tests/test_images.py`
- `docs/SESSIONS.md` (the media row and one Decisions entry)
- `docs/handoff/media.md`

Scratch files, outside the repo:

- `C:\Users\vedan\AppData\Local\Temp\claude\c--Users-vedan-cosmic-quiz-agent\9fca8f3d-8dcb-4aa0-968c-f15c813470bf\scratchpad\final\sheet.png`
- `C:\Users\vedan\AppData\Local\Temp\claude\c--Users-vedan-cosmic-quiz-agent\9fca8f3d-8dcb-4aa0-968c-f15c813470bf\scratchpad\final\overrides.json`

### Checks run

All in `C:\Users\vedan\cqa-media`, on the code in `afcf09e`.

- `pnpm install --frozen-lockfile`, `pnpm typecheck` and `pnpm build` pass. `pnpm test`: 278 pass.
- `pytest -q`: exit 0, 546 tests collected. `ruff check .`, `ruff format --check .` and
  `mypy --strict` pass.
- `python -m curator.images --dry-run --topic Auroras`: exit 0, card 8.5 KB, preview 56.7 KB. The
  worktree's `.env` has the bank keys. I read only their names.
- `python -m curator.images --dry-run --refresh`, for all topics: 53 pictures and 3 facts, 0 not
  reached. It writes nothing.
- I looked at `sheet.png` and at each candidate card. No write to Supabase, no paid call, no server
  started.

## Current goal

A real image for every topic card, legally reusable and credited, served from the site's own
origin; and a fact-card fallback where no image fits. Decided in the 2026-10-30 grill-me (Q8, Q9,
Q20; `docs/SESSIONS.md`, Decisions). Image cards are cut third if not verified by the freeze
(Monday 2 November 18:00 Dublin), so the topic API must work unchanged for a frontend that
ignores the new fields.

## Brief

### Decisions that bind this work

- **Source:** the lead image of the Wikipedia page each topic already cites (its explanation's
  sources), or a NASA Image Library result when that page has none. No AI images: this site is
  about checked facts, and a made-up picture of, say, antimatter would mislead.
- **Licence filter, enforced in code:** public domain, CC0, CC BY and CC BY-SA only, read from the
  Commons API (`extmetadata`: `LicenseShortName`, `Artist`, `Credit`, `AttributionRequired`). Store
  the author, licence name and URL, and the file page URL; the card shows the credit line
  required by the licence. Anything else, or anything unclear, is rejected and logged.
- **Hosting:** resize to WebP, about 40 KB (state the width chosen for the card and the preview),
  upload to a public Supabase Storage bucket, and serve through seo's `/media/*` rewrite so no
  visitor request reaches Wikimedia or NASA. Free tier: 1 GB stored, 5 GB transferred a month.
- **No model calls.** The fill is code only and free, so it covers every topic (38 today, plus
  latency's 30 likely topics once they land).
- **Fallback:** a topic with no acceptable image gets a category (for example star, planet,
  galaxy, particle, mission, cosmology) and one key fact taken from its published explanation
  (choose it in code from the explanation text; no model call; Vedant can override). ui draws the
  fact card.

### You own

- `curator/images.py` (new), run as `python -m curator.images` (add `if __name__ == "__main__"`),
  so `curator/__main__.py`, which latency owns, is not touched. Tests in `tests/test_images.py`,
  with recorded API responses, never live calls.
- `supabase/migrations/012_topic_images.sql` (reserved number): image columns on topics (or a
  `topic_images` table: say which and why) and the Storage bucket with its policy.
- `api/topics.py`, `src/topics.ts`, `src/useTopics.ts`, `src/topics.test.ts` (passed from
  latency and explore for this work): the image fields in `/api/topics`. Additive: existing
  fields unchanged.
- A GitHub Actions step, or a note for latency, so new topics get images after each Curator run.

### Do not touch

`curator/__main__.py`, `curator/pipeline.py`, `agent/**` except what `api/topics.py` imports
(ask latency), `supabase/schema.sql` (latency folds 012 in), `vercel.json` (seo; give seo the
exact rewrite you need). Frontend components are ui's.

### Cost and dependencies (hard rule 1)

- Pillow for WebP (free, HPND licence). It must **not** reach the Vercel function bundle: put it
  in a Curator-only requirements file or in `requirements-dev.txt`, and confirm with `pytest
  tests/test_packaging.py`. Ask Vedant before adding it (`requirements*.txt` is "ask first").
- Wikimedia asks for a descriptive `User-Agent` with contact details; use the project's.
- NASA Image Library: free, no key. Commons API: free.

### Needs from Vedant

- Paste migration 012 after 010 and 011.
- Approve the Pillow dependency.

### Verification

- Every check (`ruff`, `mypy --strict`, `pytest`, and `pnpm lint typecheck test build` for the
  TypeScript side), with tests for the licence filter (each accepted and rejected case), the
  credit line, the resize and the fallback fact.
- A dry run (`--dry-run`) prints each topic's chosen image, licence and credit without uploading;
  Vedant reads the list before the real fill.
- After the fill: every topic has either an image with a credit or a fact; `/api/topics` returns
  them; each image loads from `/media/...` on the preview deploy.

### Done

- `curator/images.py` (`python -m curator.images [--dry-run] [--topic NAME] [--refresh]`): code only,
  no model calls, no cost. Wikipedia lead image of the cited pages, then NASA, then a fact card.
- `supabase/migrations/012_topic_images.sql`: a `topic_images` table (not columns on `topics`, so
  the 003 column grant is untouched, one row is an image or a fact never half of each, and
  `locked` and `notes` stay out of the browser's grant) and the public bucket `topic-images`
  (WebP only, 512 KB; only the secret key writes, no policy lets a browser role write or list).
- `/api/topics` adds `image` or `fact` per topic (left out when absent; a bank without 012 lists
  topics as before). `src/topics.ts` adds `topicVisual()` and `FACT_CATEGORIES`.
- Small additive edits to latency's `agent/bank.py` (`TopicImage`, `TopicFact`, two optional
  fields on `BankTopic`) and `src/types.ts` (the matching types), as Vedant approved.
- Pillow 13.0.0 in `requirements-media.txt` only; `requirements-dev.txt` includes it for the
  tests. `tests/test_images.py` (71+ tests, recorded API replies in `tests/fixtures/images/`)
  checks Pillow never enters `pyproject.toml` or `requirements.txt`.
- Checks: `ruff check`, `ruff format --check`, `mypy --strict` clean; 438 pytest; `pnpm typecheck`,
  `pnpm test` (156) and `pnpm build` pass. There is no `pnpm lint` script in this repo.

## Dry run (read-only, 2026-10-30, live bank)

44 pictures (38 Wikipedia, 6 NASA) and 4 facts for 48 topics, nothing uploaded. The full output is
what `python -m curator.images --dry-run` prints; Vedant should read it before the real fill.
Things to look at:

- **NASA picks (6):** the asteroid belt, Open and globular star clusters, Types of galaxies, Mars
  rovers, The Drake equation, Red Dwarfs. The library has no licence field, so these rest on the
  credit rule; check each picture actually fits its topic (the Drake equation one especially).
- **Facts (4):** Planetary nebulae, Sagittarius A* (since fixed: a TIFF lead image is now used),
  Tidal locking, White dwarf planets in second-generation systems. Two of the facts are weak
  ("A secondary, less common population ...", "Over Earth's entire ... this has stretched ...").
  To replace one: edit the row in the table editor and set `locked = true`.
- A few NASA credits repeat a word ("ESA/Hubble & NASA NASA") because the library's own fields do.
- Credits run up to about 190 characters for Hubble pictures; ui should let the line wrap.
- Fact categories are keyword guesses (`black-hole`, `galaxy`, `cosmology`, `particle`, `mission`,
  `star`, `planet`, `small-body`, else `space`); ui needs art for each and for `space`.

## Next (needs people)

1. **Vedant:** read the dry run; paste migration 012 after 010 and 011 (SQL editor); then run
   `python -m curator.images` for real. Before that, one read-only check that the secret key works
   on Storage: the first real upload is the test (the bucket exists only after 012).
2. **seo (vercel.json, exact change):** a rewrite placed BEFORE the SPA catch-all
   `/((?!api/).*)`:
   `{ "source": "/media/:path*", "destination": "https://<SUPABASE_URL host>/storage/v1/object/public/topic-images/:path*" }`
   The files are uploaded with `Cache-Control: max-age=31536000` and hashed names. The CSP needs
   no change (`img-src 'self'`). Each topic's link preview file is `image.preview`
   (1200 x 630, absent when the source was too small: use the site-wide `og-v2.jpg` then).
3. **latency (curator.yml, exact step),** after the Curator step and before any deploy hook:
   ```yaml
   - name: Fill topic images
     continue-on-error: true
     run: |
       pip install -r requirements-media.txt
       python -m curator.images
   ```
   Add `requirements-media.txt` to the job's `cache-dependency-path`. It needs only the
   `SUPABASE_URL` and `SUPABASE_SECRET_KEY` already in the job. It skips topics that have a
   picture and retries those with a fact, so it is cheap on most days.
   Also: fold `012_topic_images.sql` into `supabase/schema.sql`, and add the `/media/*` address
   to the README/docs if wanted. Latency's 30 likely topics get pictures from the next run.
4. **ui:** draw `topicVisual(topic)` (`src/topics.ts`) on topic cards: the image with its
   `credit` line linked to `page_url` and `licence_url`, or the fact card, or nothing. Sizes: card
   640 x 360 (16:9).

## Blockers

- Migration 012 not yet applied (Vedant). The real fill, the preview-deploy check of `/media/...`
  and the Storage key check wait for it and for seo's rewrite.

## Files touched

`curator/images.py`, `supabase/migrations/012_topic_images.sql`, `tests/test_images.py`,
`tests/fixtures/images/*`, `api/topics.py`, `src/topics.ts`, `src/topics.test.ts`,
`requirements-media.txt` and `requirements-dev.txt` (one line; approved), `docs/handoff/media.md`,
`docs/SESSIONS.md` (my row and two Decisions). Edits to latency's files, as approved:
`agent/bank.py`, `src/types.ts`. Committed on `session/media` in three commits (the fill; the API and TypeScript surface; the docs). Not pushed.

## Approvals and edits outside media's files

Vedant answered four questions in this session, so these were approved, not assumed:
small additive edits to `agent/bank.py` and `src/types.ts` (latency's); Pillow 13.0.0 (HPND
licence, free) in `requirements-media.txt`; the Actions step as a note for latency; code and
tests, then a dry run, before any upload. He did not name `requirements-dev.txt` (one added line,
`-r requirements-media.txt`, so the tests and CI can import Pillow): main should confirm it.
Pillow's wheel size was not measured. It is not in `pyproject.toml` or `requirements.txt`.
