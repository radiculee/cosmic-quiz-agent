# Handoff: media

Notes for the media session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for this
session. Update them before finishing, and commit them on `session/media`.

Last update: 2026-10-30 (brief written by main)

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

### Done when

The checks above pass and main's review has no open findings.

## Done

## Next

## Blockers

## Files touched
