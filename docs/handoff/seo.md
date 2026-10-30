# Handoff: seo

Notes for the seo session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for this
session. Update them before finishing, and commit them on `session/seo`.

Last update: 2026-10-30 (brief written by main)

## Current goal

Make the site the astronomy quiz that astronomy fans and people in the field find: the rename to
**Curiosity** at `curiosity.vedantgaikwad.ie`, complete metadata, prerendered topic pages that
crawlers can read, and typo-tolerant addresses. Decided in the 2026-10-30 grill-me (Q12 to Q15,
Q21; `docs/SESSIONS.md`, Decisions). The rename and metadata **must ship** by the freeze (Monday
2 November 18:00 Dublin); prerendering is cut second if late.

## Brief

### Decisions that bind this work

- **Name (Q14):** Curiosity, after the Mars rover. The big hero heading becomes CURIOSITY; the
  tagline stays; a short visible line says it is an astronomy quiz.
- **Title tag: open until Monday.** Build everything to read it from `src/brand.ts`, so the final
  wording is one line. Vedant's direction: "Curiosity: Quiz on the wonders of our world beyond
  earth", or something better along those lines. Candidates (keep the searched words "astronomy"
  or "space", and stay near 60 characters):
  - "Curiosity: A Quiz on the Wonders Beyond Earth | Astronomy & Space" (64)
  - "Curiosity: Astronomy Quiz on the Wonders Beyond Earth" (53)
  - "Curiosity: The Wonders Beyond Earth, an Astronomy Quiz" (54)
  Use the second as the placeholder until Vedant picks.
- **Address (Q15):** `curiosity.vedantgaikwad.ie` is canonical. `cosmic.`, `quiz.`, `astro.`,
  `cosmik.`, `curiousity.`, `curiosty.` and `cosmicquiz.` 301 to it, path kept. The existing
  `cosmic-quiz-agent.vercel.app` redirect moves to `curiosity.` too. The repo keeps its name.
- **Typos (Q13):** search wording in titles, descriptions and page text; the subdomain aliases;
  close-match path redirects (`/lern` to `/learn`, `/learn/antimater` to `/learn/antimatter`) and
  suggestions on the 404 page. No look-alike domains (they cost money).
- **Prerendering (Q12):** each Learn topic, `/quiz` and `/explore` built to static HTML with its
  own title, description, canonical link, OG and Twitter tags, the explanation text and sources,
  and JSON-LD (`WebSite` with `SearchAction` on the home page; `LearningResource` or `Article` on
  topic pages; `Quiz` where it fits; validate with Google's Rich Results Test). The React app
  takes over in the browser as now. The build fetches topics with the publishable key and falls
  back to the plain SPA build when the env is absent (CI has no secrets). Vercel serves files
  before `rewrites`, so the catch-all keeps working; confirm it.
- **Previews (Q21):** Vedant supplies `public/og-v2.jpg` (1200 x 630) for the site. Each topic's
  preview is generated at build from its card image (media's WebP) with the topic name and the
  credit. No paid service; state any build dependency's size first.
- The fonts rule stands: no request from a visitor reaches a third party. Images come through the
  `/media/*` rewrite, so `img-src 'self'` holds.

### You own

- `src/brand.ts` (new): name, title, description, tagline, astronomy line, canonical origin.
- `index.html`, `public/robots.txt`, `public/favicon*`, `public/site.webmanifest` (new as needed),
  the sitemap and prerender scripts (`scripts/` or `dev/`, your choice; say where), and their
  tests.
- `vercel.json` (sole editor): redirects, the `/media/*` rewrite to Supabase Storage (media gives
  the bucket path), and the CSP change data asks for (`connect-src` to the Supabase origin only).
- `src/router.ts`, `src/router.test.ts`, `src/pages/NotFoundPage.tsx`, and a close-match module
  (new) with tests.
- The rename in `README.md` (granted by latency, the usual owner, for the rename only).

### Do not touch

Everything ui, data, media and latency own (`docs/SESSIONS.md`). Exception: **your first pass**
replaces the hard-coded "Cosmic Quiz" strings across `src/` with imports from `src/brand.ts`. Do
it first, keep it mechanical, and get it merged on Saturday morning before ui starts editing those
files. Tell Vedant when it is ready to review.

### Order

1. `src/brand.ts` and the mechanical name pass. Review and merge first.
2. `index.html` metadata, favicon set, `robots.txt`, redirects, the 404 close-match.
3. Prerendering, the sitemap and per-topic previews. Ask the latency session for the Curator's
   deploy hook call (it owns `curator/**`); the hook URL is a secret Vedant makes.
4. Before the freeze: the title Vedant picks.

### Cost and dependencies

A prerender may need a dev dependency (for example a render step on Vite's SSR build, which needs
nothing new). Prefer no new dependency; otherwise state its size and licence and ask Vedant first.
Vercel Hobby allows 100 deploys a day; the Curator's hook adds at most a few.

### Needs from Vedant

- DNS CNAMEs for `curiosity.` and the six aliases, and each domain added to the Vercel project.
- `public/og-v2.jpg`.
- After launch: Google Search Console and Bing Webmaster Tools verification; submit the sitemap.
- The title tag, on Monday.

### Verification

- Every check (`pnpm lint typecheck test build`), with tests for the close-match redirects and the
  prerender output.
- `curl` on a built `/learn/<topic>` shows the title, description, text, sources and JSON-LD.
- After deploy: `curl -I` on each alias and `cosmic.` returns 301 to the same path on `curiosity.`;
  the Rich Results Test passes; a pasted link shows the right preview in a chat app; no CSP
  violations in the console.

### Done when

The checks above pass and main's review has no open findings.

## Done

## Next

## Blockers

## Files touched
