# Handoff: ui

Notes for the ui session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for this
session. Update them before finishing, and commit them on `session/ui`.

Last update: 2026-10-30 (brief written by main)

## Current goal

The site's controls and cards: a sticky header with navigation and each page's settings, a
button row on every question card, progress rows for a live search, rover ranks, and the Learn
topic cards with images. Decided in the 2026-10-30 grill-me (Q7, Q8, Q10, Q11, Q16; `docs/SESSIONS.md`,
Decisions). The header and card buttons **must ship** by the freeze (Monday 2 November 18:00
Dublin); the image cards are cut third if late.

## Brief

### Decisions that bind this work

- **Header (Q10):** sticky on every page. It holds the brand (from seo's `src/brand.ts`, never a
  hard-coded name), navigation (Learn, Quiz, Web), data's `SignInButton` slot, and that page's
  settings: difficulty and search on Learn; run length, timer, score and End run on Quiz; the
  topic box and searches left on Web. On a phone it must fit one row or collapse sensibly;
  propose how.
- **Per-question actions stay on the card (Q10, Q11).** After an answer: right or wrong and the
  correct answer at once, then a button row: "Read the explanation", "Sources (n)" (the links and
  Jev's source check together, reusing `SourcesList.tsx` and `SourceCheckPanel.tsx`) and "Next".
  Both panels start closed and remember the last choice (in the browser profile or
  `localStorage`; coordinate with data if it goes in the profile). The same row goes on the web
  search's question cards.
- **Progress rows (Q7):** a new `src/components/SearchProgress.tsx`. One row per item (Easy,
  Medium and Hard question, then the three explanations), each moved by the real streamed steps
  (search, read, write, verify), with time left from latency's per-level median estimate. A status
  line names the real work ("Reading nasa.gov", "Checking the answer against 3 pages"), never
  random words. The agent log goes behind "Show details". No timer-driven fake progress.
- **Rover ranks (Q16):** `RANKS` in `src/game.ts` becomes Sojourner, Spirit, Opportunity,
  Curiosity, Zhurong and Perseverance, at the same points (0, 1,000, 3,000, 7,500, 15,000,
  30,000). Each has a one-line fact shown with the rank (for example "Spirit: landed 2004, drove
  7.7 km"). Every fact needs a NASA or CNSA source URL you have opened, recorded beside it; Vedant
  checks them. Saved profiles carry over (ranks come from points).
- **Learn cards (Q8):** each topic is a card with its image and credit, from media's fields; a
  topic with no image gets the fact card (a category illustration and one key fact). The opened
  marker already exists (`TopicGrid.tsx`, the pixel tick); make it clearly visible on the new
  card. The layout cannot be settled in conversation: **build two throwaway prototypes on
  Saturday** (separate files, fake data, not merged), Vedant picks one, then build that one.
- Design tokens, fonts and scene rules in `CLAUDE.md` apply. No emojis. Accessible: keyboard,
  focus rings, reduced motion, `aria-expanded` on the toggles, alt text from media's credit
  data.

### You own

- `src/components/SiteHeader.tsx`, `QuizCard.tsx`, `CardActions.tsx`, `LearnCard.tsx`,
  `TopicGrid.tsx`, `RunHud.tsx`, `ModeCard.tsx`, `ProfileStrip.tsx` and the other components not
  listed under another session, with their tests.
- `src/components/SearchProgress.tsx` (new), `src/components/FactCard.tsx` (new, if needed).
- `src/pages/HomePage.tsx`, `LearnPage.tsx`, `QuizPage.tsx`, `ExplorePage.tsx`,
  `TrophiesPage.tsx`, `common.tsx`, and `src/components/TopicInput.tsx`, `DiceIcon.tsx` (passed
  from explore, which is done).
- `src/App.tsx` (wiring pages, including data's `/account` page).
- `src/game.ts`, `src/game.test.ts` (ranks only; scoring is unchanged).
- `src/index.css`.

### Do not touch

`src/search.ts`, `src/api.ts`, `src/types.ts`, `src/components/AgentLog.tsx` (latency);
`src/brand.ts`, `src/router.ts`, `src/pages/NotFoundPage.tsx`, `index.html`, `vercel.json` (seo);
`src/topics.ts`, `src/useTopics.ts` (media); `src/profile.ts`, `src/session.ts`,
`SignInButton.tsx`, `AccountPage.tsx`, `PrivacyPage.tsx` (data). Write the text you need in
"Requests" and ask Vedant.

### Order

1. **Wait for seo's `src/brand.ts` pass** (Saturday morning; it replaces "Cosmic Quiz" in your
   files), then `git rebase main`. Until then, work only on the two card prototypes (new
   throwaway files).
2. Header, then the card button row. Must ship.
3. Rover ranks.
4. Progress rows, once latency's event types are on `main` (rebase).
5. The chosen Learn card, once media's image fields are on `main`.

### Requests to other sessions (fill in as you go)

- latency: a prop or hook on `AgentLog.tsx` so it can sit behind "Show details"; the progress
  event types in `src/types.ts`.
- data: `SignInButton` (props and states).
- seo: the `/account` route in `src/router.ts`.

### Cost and dependencies

No new dependency expected. If one is needed, state its price and size and ask Vedant first
(`package.json` is "ask first").

### Verification

- Every check (`pnpm lint typecheck test build`), with tests for the remembered open state, the
  rank list and the progress estimate.
- A headless drive against the stub API (ask Vedant before starting dev servers on 5173 and 8787;
  one session at a time): header nav on every page at phone and desktop widths, the button row
  and its remembered state, the progress rows advancing on a stubbed stream, the image card with
  its credit, the fact card, the read marker.

### Done when

The checks above pass and main's review has no open findings.

## Done

## Next

## Blockers

## Files touched
