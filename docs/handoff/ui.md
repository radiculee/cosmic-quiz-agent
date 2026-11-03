# Handoff: ui

Notes for the ui session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for this
session. Update them before finishing, and commit them on `session/ui`.

Last update: 2026-11-03 (ui: Learn card fixes on `session/ui`, waiting for main's review)

## Learn card fixes (2026-11-03)

Based on `c23560f`. Not pushed and not merged. The older notes below are unchanged.

### Done

All six faults are fixed, in `src/components/TopicGrid.tsx` and `src/topicGrid.test.tsx`.

- `de932bc`, fault 1: a card names the licence once, for example "ESO, CC BY 4.0, via Wikimedia Commons · File page". The licence is linked if it has an address. A credit that does not name the licence keeps the old output. The split uses the last match in the credit, because `credit_line` puts the licence after the author. Each case has a test.
- `adac808`, fault 2: `line-clamp-4` is removed, with a test. `_shorten` in `curator/images.py` cuts a long fact at a space and adds "...", so a fact cannot stop in the middle of a word.
- `8b0ee8f`, faults 3 to 6, as one group because they are in one file:
  - Credit links have `whitespace-nowrap`.
  - The text beside a Read mark has `pr-14`, and the title has `break-words`.
  - The WEB tag is `text-slate`. Contrast on the card goes from 3.89:1 to 6.64:1.
  - The alt text is `topic.name`, with a test. No existing test read the old alt text.

The square thumbnail and `index.html` are not changed.

### In progress

Nothing.

### Left

Main reviews the branch, then lands it.

### Blocked on

Nothing.

### Needs from Vedant

Nothing for these fixes. The thumbnail decision is still his. Faults found and not fixed:

- `pr-14` also narrows the fact text on a read fact card, so a long read card is taller. "White dwarf planets in second-generation systems" takes 5 title lines and 5 fact lines at 1280 px.
- The 170-character limit applies only to facts that the rules pick. I found no limit in `curator/images.py` for a fact replaced by hand (`locked`), and such a fact now shows in full. I did not read the whole `locked` path.
- At 1280 px a card beside a card with a long credit stretches and has an empty area, for example "Binary star systems". The older note below describes a similar case for name-only cards.
- `.venv` in this worktree did not have Pillow, so `pytest` and `mypy --strict` failed before they could run. I installed `pillow==13.0.0`, the version pinned in `requirements-media.txt`. CI installs it through `requirements-dev.txt`, so CI is not affected.

### Files changed

- `src/components/TopicGrid.tsx`
- `src/topicGrid.test.tsx`
- `docs/handoff/ui.md`

### Checks run

Run in `C:\Users\vedan\cqa-ui`, all passing:

- `pnpm install --frozen-lockfile`, `pnpm typecheck`, `pnpm test` (283 tests), `pnpm build`.
- `pytest -q`, `ruff check .`, `ruff format --check .`, `mypy --strict` (89 files).

Headless Chrome on a built copy of the site at 1280, 390 and 320 px, with main's local preview data (40 topics: 36 with pictures, 4 with facts). The server answered `/api/topics` from that file and nothing reached the live site. At each width:

- No sideways page scroll and no card overflow.
- Each credit names the licence once, and all 36 picture credits contain their licence, so the old output was not seen in the browser. A test covers it.
- Licence links match the data. No credit link breaks across two lines.
- All 4 facts show in full. The title never touches the Read mark. All alt text equals the title.
- A 57-letter word set in a read card's title by script gives no overflow.
- No console errors.

Not checked: a real phone, and the live bank's credits.

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

- Header (must ship): `7af0890`, with the sign-in slot named in `77aebd2`. Main checked it in a browser and approved it.
- Explore wait text first said "about 30 seconds in all" (`7af0890`); it now says a minute or two, with the first question under a minute.
- Card button row (must ship): "Read the explanation", "Sources (n)", "Next" in `CardActions`. Both panels start closed and the last choice is kept in `localStorage` (`src/panels.ts`, tested). Used by `QuizCard` (Quiz and Web) and `LearnCard`. Doubts stay visible outside the panels.
- Learn card prototypes were built, B was picked, and the throwaway files are deleted.
- Two fixes main asked for: the iOS zoom test reads template-literal classNames (`2994840`), and the run bar shows its labels at sm and wider (`66063b2`).
- Rover ranks (d): `RANKS` in `src/game.ts` now has Sojourner, Spirit, Opportunity, Curiosity, Zhurong and Perseverance at the same points, each with a `fact` and a `source`. `ProfileStrip` shows the fact. Tests cover the list, the facts and the sources.
  All sources were opened on 2026-11-01 (Vedant checks them):
  - Sojourner: https://science.nasa.gov/mission/mars-pathfinder/ (landing 4 July 1997; Sojourner deployed the night of 5 July).
  - Spirit: https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/ (landed 3 Jan 2004, 7.7 km, ended 2010).
  - Opportunity: same page (landed 24 Jan 2004, 45.16 km, last contact 10 June 2018).
  - Curiosity: https://science.nasa.gov/mission/msl-curiosity/ (landed 6 Aug 2012, Gale Crater; the page reports a 1 km climb of Mount Sharp).
  - Zhurong: https://science.nasa.gov/image-article/apod-2021-june-15-zhurong-new-rover-on-mars/ (Tianwen-1 delivered it; northern Utopia Planitia, mid-May 2021). The "second nation" claim was dropped: NASA's statement says "second nation to ever land", which is disputed, and no page I opened says "operate a rover". I found no CNSA page I could open.
  - Perseverance: https://science.nasa.gov/mission/mars-2020-perseverance/ (landed 18 Feb 2021, Jezero Crater, Ingenuity).

- Rank fact wording made exact (`4a9d6a1`): Zhurong, Curiosity and Spirit now say only what their pages say.
- Learn card B (e): `TopicGrid` draws `topicVisual(topic)` from media's `src/topics.ts`. Image card: 96/112 px thumbnail, credit line with the licence and the file page linked, alt text from the credit. Fact card: a plain outline glyph per category (`FactGlyph.tsx`) and the fact. A topic with neither shows its name only. Read topics get a teal "Read" ribbon and a teal border. The title is the one link, stretched over the card; the credit links sit above it. Tab order: title, licence, file page. `src/topicGrid.test.tsx` renders the grid to markup and checks the links, their order, the fact, the glyph and the ribbon.

- Rebased on origin/main (c9894d6) and passed `{ seconds, choice }` to `afterAnswer` (`08fb147`). `QuizCard`'s `onAnswered` now also gives the option picked.
- Progress rows (f): `src/components/SearchProgress.tsx` with pure helpers in `src/progress.ts`. One row per item (questions first, then explanations). Each row has four stages (Search, Read, Write, Verify), a status line and the time left. `ExplorePage` now handles the `progress` event with `progressed()`. The agent log sits behind "Show details" (closed for each new search).
  - Stage and status come only from `progress` events. The stage bar moves only on an event.
  - Time left is the plan's `estimate_seconds` less the seconds since the run's first progress, on a clock that ticks once a second. Past the estimate it says "Taking longer than usual". No estimate: no time shown.
  - States: waiting ("Starting", whole estimate), running (stage, status, time left), loading from the bank, ready (all four stages filled), left out (rust bar, "Left out").
- Unavailable agent message: `ExplorePage` handles latency's `end` event (cherry-picked b6c1dd5; it drops out at the next rebase). A search that made nothing and ended with `unavailable: true` says "The agent is unavailable just now. This search was not counted. Topics in the bank are still free to play." Other cases keep their text. Logic and test in `src/outcome.ts`, `src/outcome.test.ts`.

- Monday work (2 Nov): the progress panel is now three bars (Easy, Medium, Hard) with one word each and an "Explanations: n of 3 ready" line, under the question card (`37b74fb`). `QuestionStrip` is gone. The agent log and the Mission Control link sit behind Show details; the panel shrinks to one line when every item has ended. The first question's card scrolls to the top once. Next reads "Medium question on the way" until ready. A result card follows the last question of a web search (`fbe48bc`, `src/webResults.ts`). Hint text says a minute or two (`0f386f2`). Explanations still open only after the questions are answered (`explanationLock` in `search.ts`). The Quiz setup screen has a "How the quiz works" card; its words are in `src/quizAbout.ts` for seo's prerender.

## Next

Nothing in progress. Waiting on main for the next item:

1. When main says seo's step 2 is on `main`: in `LearnPage.tsx`, when the topics have loaded and `/learn/<slug>` matches no topic, render `<NotFoundPage topics={topics} />`.
2. When main says accounts are set up: the sign-in slot.

Accepted by Vedant as they are (2026-11-02): the trophy pop-up over the first question, and "Explanations: 0 of 3 ready" when caps leave the explanations out.

Optional, not now (main's note): at sm and wider, a name-only Learn card beside an image card stretches tall and empty. It should be rare once the image fill has run.

## Blockers

- main: the next item. Main wires `SignInButton` into the header slot.

## Files touched

- Header: `SiteHeader.tsx`, `HeaderSettings.tsx`, `RunHud.tsx`, `App.tsx`, `Dropdown.tsx`, `TopicInput.tsx`, `TopicGrid.tsx`, the Learn, Quiz, Explore and Home pages, `header.test.ts`.
- Card buttons: `CardActions.tsx`, `QuizCard.tsx`, `LearnCard.tsx`, `src/panels.ts`, `src/panels.test.ts`.

## Needs from Vedant

- Look at the settings that moved into the header (Quiz difficulty and run length; Web topic box).
- No `lint` script exists in `package.json`. Say whether to add one.
