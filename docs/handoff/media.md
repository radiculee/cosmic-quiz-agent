# Handoff: media

Notes for the media session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for this
session. Update them before finishing, and commit them on `session/media`.

Last update: 2026-10-30 (media session: built, tested, dry run done, committed; waiting on Vedant)

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
