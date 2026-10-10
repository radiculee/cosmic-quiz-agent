# Next session

Written 2026-10-10, at the end of the session that built the scenes step and most of 10b. It
holds where things stand, the plan for the next session (fixes Vedant found, and two design
questions) and the prompt to paste.

## Where things stand

- **Live** at https://cosmic-quiz-agent.vercel.app: the scenes step (home slideshow, the
  observatory still on inner pages), and from this session's last push the self-hosted fonts,
  the `/privacy` page with a footer link on every page, and the link preview.
- **Session 10a:** committed and pushed. Still open: the SQL editor results for S18 and S19
  (run on 2026-10-10, tables not pasted yet), and the retention counts after the first purge
  (the first scheduled run with the purge is on 2026-10-11).
- **Session 10b, paused by Vedant (2026-10-10):** the repo **stays private** until a round of
  fixes and a README session. Done: the history scan (clean), the docs read-through (three local
  paths replaced), LICENSE (MIT) and NOTICE, `/privacy`, the self-hosted fonts and the link
  preview. Left: the README (a draft is committed; Vedant redoes it in its own session), making
  the repo public (later, on his word), and the domain (Vedant adds the `cosmic` CNAME later).
  Until the domain works, the link preview's image URL (on `cosmic.vedantgaikwad.ie`) does not
  load.
- 338 Python and 134 TypeScript tests; every check passes.

## The plan for the next session

Ask Vedant each open decision first, one at a time, each with a recommendation (his standing
preference). Reproduce every bug before fixing it.

### 1. Scroll bugs (home, the web page, other pages)

What Vedant sees: the scroll misbehaves on the home page and elsewhere; on the web page, while
answering questions, the page jumps back up.

Found by reading the code (not yet reproduced):

- **The web page's jump, most likely:** `src/components/AgentLog.tsx` calls
  `end.current?.scrollIntoView({ block: "nearest" })` for every new log line. The log is its own
  scroll box (`max-h-96 overflow-y-auto`), but `scrollIntoView` also scrolls the window, so each
  line that arrives while the player reads a question further down pulls the page back to the
  log. Fix: scroll only the box (`list.scrollTop = list.scrollHeight`), and only while the
  reader is already at its bottom.
- **Phones, likely:** the home hero's height is `100dvh` and the scene layer is
  `position: fixed; inset: 0`. Both change size when the mobile address bar shows or hides, so
  the hero and the scene jump during a scroll. Candidates: `svh` for the hero's minimum height,
  and a scene layer sized with `lvh` (or a fixed height) so it never resizes.
- **Back and Forward:** the router leaves scrolling to the browser, but pages reload their data
  after `popstate`, so the browser can restore the position before the content is back.
- **Deliberate scrolls to check:** the quiz and the web page smooth-scroll to each new question
  and to the results (`QuizPage.tsx`, `ExplorePage.tsx`), and the web page scrolls to the top on
  "Another new topic".

Question for Vedant: "scroll bugs everywhere" may be two or three root causes (the agent log, the
phone viewport units, Back/Forward), not many. Ask him to list each one (page, device, what he
did, what happened; a short screen recording helps), reproduce each in headless Chrome at desktop
and phone sizes with the scroll position logged before and after, fix the cause, and add the
check to the drive.

### 2. The web page: questions first, the explanation behind a button

Vedant's ask: show the quiz first, and the explanation later behind a button that becomes
clickable once the search is complete.

- Confirm the reason: the explanation can give away the answers, so learning after the quiz
  keeps the questions honest. If that is it, the idea is sound.
- **Server order, a trade-off to decide:** today a search makes the explanation first (about
  20 s), then a question at each level. If only the page order changes, the player waits for an
  explanation they cannot see before the first question. Making the questions first
  (`agent/ondemand.py`'s plan order) gets the first question sooner. But when the daily $0.50
  cap cuts a search short (usually the 4th run), it would then be the explanation that is lost
  rather than a question. Recommend making the questions first.
- **When the button unlocks, to decide:** (a) when the search ends, as asked; (b) when the
  explanation is ready; (c) when the player has answered every question the search made (or
  the search has ended with none left), so it can never spoil an answer. Recommend (c), with
  (a) as the fallback when no question was made.
- A topic the bank already has in full is shown free: use the same order there.
- Tests: `src/search.ts` (pure rules) for the order and the unlock rule; the drive with the free
  stub API from the memory notes.

### 3. Learn: topics in a scrolling list

Vedant's ask: the topics in a scrolling mechanism, easier to use. Clarify what he means first:

- (a) the grid in a fixed-height panel that scrolls on its own, with the difficulty switch and
  search staying in view;
- (b) a horizontal carousel;
- (c) the page scrolls as now, but the difficulty switch and search stick to the top.

Question: a scroll box inside a scrolling page traps the scroll on phones (the page will not
move while a finger is on the box) and adds a second scrollbar over the scene. (c) gives the
same "controls always at hand" with one scroll. Recommend (c), or (a) on wide screens only if
he wants the grid contained.

### 4. Saving progress without accounts (a v2 question)

Today the profile (rank, points, trophies, topics read) is in `localStorage`. It is lost when the
browser's site data is cleared, it does not follow the player to another device, and Safari
deletes script-written storage after 7 days without a visit, which will hit iPhone players.

Options, cheapest first:

1. **A save code (no server):** "Copy my progress" gives a short code (the profile, compressed,
   with a checksum); "Restore" on another device takes it. Free, no personal data, no change to
   the privacy page. Add `navigator.storage.persist()`, which asks the browser not to evict the
   storage.
2. **An anonymous cloud save:** the server keeps the profile under a random secret code; anyone
   with the code restores it. A table, two endpoints and limits; still no personal data, but the
   site starts storing profiles.
3. **Accounts (Supabase Auth, passkeys or email links, free tier):** real sync across devices.
   An email is personal data: the privacy page, deletion on request, a security review and a
   login screen all follow.

Recommend 1 now (small, private, fixes the iPhone loss), and decide 3 together with the v2
newsletter, which needs subscribers' emails anyway, rather than as a feature of its own. The
points and trophies are low-stakes, and accounts carry the weight of the GDPR and a new attack
surface.

### Also open

- Close 10a: Vedant pastes the three SQL result tables (S18, S19); re-run the read-only retention
  counts after the first purge (`retention_counts.py` was a scratchpad script; recreate it:
  timestamps only, never a hash).
- Later sessions: the README, then going public (on Vedant's word), then the domain.

## Prompt for the next session

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md, docs/NEXT_SESSION.md and docs/SECURITY_AUDIT.md.
> The repo stays private for now.
>
> 1. Fixes and design questions, as planned in docs/NEXT_SESSION.md ("The plan for the next
>    session"): the scroll bugs, the web page's order (questions first, the explanation behind
>    a button), the Learn topics list, and how to save progress without accounts. Ask me each
>    open decision first, one at a time, with a recommendation, and question my thinking where
>    a better way exists. Before fixing the scroll bugs, ask me to describe each one, then
>    reproduce it in headless Chrome at desktop and phone sizes.
> 2. Plan before building. Then build, test (pytest, pnpm test, typecheck, build, ruff,
>    mypy --strict), and drive the built site with the vercel.json headers at 1920x1080,
>    1440x900, 1024x768, 768x1024 and 390x844. Show me screenshots and the changes before
>    committing.
> 3. If I paste the SQL editor results, close S18 and S19 in docs/SECURITY_AUDIT.md.
>
> Rules from CLAUDE.md apply: ask before adding any dependency, service or cost; no emojis;
> complete files; commit only when I ask.
