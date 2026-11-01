# Handoff: data

Notes for the data session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for this
session. Update them before finishing, and commit them on `session/data`.

Last update: 2026-11-01 (data: steps a, b and c done; step d next)

## Current goal

Optional accounts: sign in with Google or an email link, and every player's progress saved in
Supabase so it is never lost. Decided in the 2026-10-30 grill-me (Q1 to Q5; `docs/SESSIONS.md`,
Decisions). **Accounts are the first thing cut** if they are not verified by the freeze (Monday 2
November 18:00 Dublin), so build them to switch off cleanly: with the feature flag off, the site
behaves exactly as today.

## Brief

### Decisions that bind this work

- Sign-in is optional. Guests keep the browser profile (`src/profile.ts`) unchanged.
- Google and an email link (magic link) through Supabase Auth. No passwords. Email goes through
  Resend as Supabase's custom SMTP (free: 3,000 a month, 100 a day).
- Profiles are private. Store **one row per answer**, so a server-scored leaderboard can come
  later without a migration. No display names, no public pages.
- On sign-in, guest progress is **added** to the account with no prompt: topics read and items
  seen are combined (union), the guest's answers are appended, and points, streaks and trophies
  are recalculated from the full answer history using the existing pure functions in
  `src/profile.ts` and `src/trophies.ts`. Merging twice must change nothing (idempotent).
- Signed-in users are limited per account with the same numbers; guests stay per salted IP hash;
  the global caps are unchanged. You build the server-side identity; latency wires it into the
  limits (see "Handoffs").
- GDPR: an account page with export (JSON download) and delete (erasure of every row and the
  auth user). The privacy page says what is stored, why, for how long, and how to delete it.

### You own

- `supabase/migrations/011_accounts.sql` (reserved number; write only this migration).
- `agent/auth.py` (new): verifies a Supabase access token on the server (JWT against the
  project's JWKS, or Supabase's `/auth/v1/user`; choose and justify) and returns the user id or
  None. Fully typed, Pydantic at the boundary, tests in `tests/test_auth.py`.
- `api/account.py` (new) if export and delete need the secret key on the server.
- `src/session.ts`, `src/useSession.ts` (new): the Supabase browser client with the publishable
  key only, sign-in, sign-out, and `authHeader()` for latency to send with API calls.
- `src/profile.ts`, `src/useProfile.ts`, `src/profile.test.ts`: sync and merge.
- `src/pages/AccountPage.tsx`, `src/components/SignInButton.tsx` (new). ui places the button in
  the header; you build it.
- `src/pages/PrivacyPage.tsx`.

### Do not touch

`agent/limits.py`, `api/research.py`, `api/quota.py`, `src/api.ts`, `src/types.ts` (latency);
`vercel.json`, `src/router.ts`, `index.html` (seo); `src/App.tsx`, `SiteHeader.tsx` (ui);
`supabase/schema.sql` (latency folds 011 in). Write the exact text you need in "Requests" below
and ask Vedant.

### Requests to other sessions (fill in as you go)

- seo (`vercel.json`): add the Supabase project origin to `connect-src`, so the CSP reads
  `connect-src 'self' https://fbwezifjjmmczevgpfiw.supabase.co`. Nothing else changes:
  `form-action` stays `'self'`, because sign-in with Google is a top-level navigation
  (`location.assign`) to Supabase and back, not a form post, and the email code is sent with
  `fetch`. `api/account.py` is covered by the existing `api/*.py` functions entry.
- ui: a `/account` route and page slot in `src/App.tsx` and `src/router.ts` (router is seo's; ui
  wires the page); the `SignInButton` slot in the header. Both render nothing while the
  `VITE_ACCOUNTS` flag is off.
- latency: call `authHeader()` from `src/api.ts`; use `agent/auth.py` in `api/research.py` and
  `api/quota.py` to key limits by account (`account_visitor(user_id)` gives a salted key for the
  existing visitor columns, so no schema change).
- latency: player rows reference `items(id)` (migration 011), so the Curator must retire items,
  never delete them.
- Vedant (unowned files): `dev/api_server.py` needs `account` in its import and `ROUTES`, so the
  local server serves `/api/account`; `package.json` and `pnpm-lock.yaml` gain
  `@supabase/auth-js` (approved 2026-10-30, pinned to an exact version).

### Steps

1. Plan first. Explain migration 011 to Vedant before writing it: the tables (`profiles`,
   `answers`, `learned`, `seen`), keys on `auth.users(id)` with `on delete cascade`, RLS policies
   (`auth.uid() = user_id` for select, insert and delete; no update on answers), and any account
   key the limits need. Additive only.
2. `agent/auth.py` and its tests.
3. `src/session.ts`, `useSession.ts`; the sign-in button; the feature flag (an env var read at
   build, off by default).
4. Sync: write answers as they happen (queued and retried offline); read on sign-in; the merge;
   the recalculation. Unit tests for the merge (union, append, idempotent, points recalculated).
5. Account page: export and delete. Privacy page text.
6. Docs in this handoff; the text for `CHANGELOG.md` and `README.md` for latency to fold in.

### Cost and dependencies (hard rule 1)

- `@supabase/supabase-js` (MIT, free). State its gzipped bundle cost and ask Vedant before
  adding it (`package.json` is "ask first"). If it is heavy, consider importing only
  `@supabase/auth-js`.
- Supabase Auth free tier: 50,000 monthly users. Resend free tier as above. Nothing paid.
- Python side: verify JWTs without a new dependency if possible (the standard library cannot do
  RS256/ES256; `PyJWT[crypto]` adds `cryptography`, which is large for the Vercel bundle). Calling
  `/auth/v1/user` with `httpx` (already used) avoids it at the price of one request; say which.

### Needs from Vedant

- A Google Cloud OAuth client (web app), with Supabase's callback URL as the redirect.
- In Supabase: enable Google and email providers; custom SMTP with Resend's credentials; the site
  URL `https://curiosity.vedantgaikwad.ie` and redirect URLs for localhost, `curiosity.` and the
  preview domain.
- A Resend account, with its SPF and DKIM records on vedantgaikwad.ie.
- Paste migration 011 after latency's 010.

### Verification

- Every check (`pnpm lint typecheck test build`, `ruff`, `mypy --strict`, `pytest`).
- Two browsers: sign in on A and play; play as a guest on B; sign in on B and check the merge
  (reads combined, answers added, points recalculated). Sign in again: nothing doubles.
- Read another user's rows with the publishable key: refused by RLS.
- Delete the account: every row and the auth user are gone.
- With the flag off: no sign-in button, no Supabase request, the site as today.

### Done when

The checks above pass and main's review has no open findings.

## Done

- 2026-10-30: plan agreed with Vedant (four choices, each the recommendation; `docs/SESSIONS.md`,
  Decisions). Migration 011 written with his eight changes and main's three review changes. On
  `main` as `bc1779d`, `bfecd2a`, `616c3cb`, `1b868c2`, `e830bbf`.
- 2026-11-01: `session/data` rebased onto `main` (`8d4ff76`). My five earlier commits were already
  on `main` with the same content, so the rebase skipped them.
- Step a, `afe8ef4` (approved by main): `agent/auth.py` and `tests/test_auth.py`.
  - `TokenChecker.user_id(authorization)` asks Supabase's `GET /auth/v1/user` with the
    publishable key; the user's UUID, or None (no or bad header with no request sent, any 4xx,
    an anonymous user, an unexpected reply; 429, 5xx and network errors are logged too). One
    request, 5 s timeout, no retry.
  - `signed_in_user(authorization)` reads `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`.
  - `account_visitor(user_id, salt)`: sha256 of `"{salt}:account:{user_id}"`, never the raw id.
- `8fab178` (granted by main): `ApiRequest.authorization` in `agent/web.py`, read from
  `HTTP_AUTHORIZATION` ("" when absent), with two tests in `tests/test_auth.py`.
- `76ae3c3`: `@supabase/auth-js` 2.118.0 (MIT, released 2026-10-15, one dependency: `tslib`) in
  `package.json` and `pnpm-lock.yaml`, approved by Vedant.
- Step b, `61eb143`: `src/session.ts`, `src/useSession.ts`, `src/components/SignInButton.tsx`,
  with `src/session.test.ts` (20 tests) and `src/components/SignInButton.test.tsx`.
  - The flag: accounts are on only when the build sets `VITE_ACCOUNTS=on`,
    `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`. Off (the default), the auth library
    is not in the build at all and nothing is sent to Supabase; `SignInButton` renders nothing.
    Checked by building the button alone both ways: off, one 4.05 KB (gzipped) file; on, the
    same plus auth-js as its own 25.9 KB chunk. The site's own bundle is unchanged (358.20 kB).
  - On, auth-js loads only when a visitor starts a sign-in, comes back from one (`?code=` or
    `?error_description=`) or has a saved session (`cosmic-quiz:session` in local storage).
  - Google: a top-level redirect to Supabase and back to the same page. Email: one message with
    a link and a 6-digit code (PKCE); a link opened in another browser says to use the code.
    After a return, Supabase's parameters are removed from the address.
  - Sign-out ends this browser's session only (`scope: "local"`).
  - `authHeader()` gives `{ Authorization: "Bearer <token>" }` for a signed-in player and `{}`
    for a guest, without loading anything. For latency's `src/api.ts`.
  - `SignInButton`: signed in, an "Account" link to `/account`; otherwise a "Sign in" button
    that opens a panel (Escape and an outside click close it; focus starts on Google).

- `36cf875` (granted by main): `.env.example` lists `VITE_ACCOUNTS`, `VITE_SUPABASE_URL`,
  `VITE_SUPABASE_PUBLISHABLE_KEY`, empty.
- Step c, `ad9ecb0`: `src/profile.ts`, `src/useProfile.ts`, `src/profile.test.ts` (29 tests, 19
  new).
  - Each pure update (`afterAnswer`, `afterRun`, `afterLearn`, `afterLiveRun`) takes an
    optional stamp and appends an event (UUID and ISO time) to `profile.log`. The pages are
    unchanged. `newStamp()` times only go up, so same-millisecond events keep their order.
  - `replay(baselines, events)` rebuilds the totals through the same updates: counts add up,
    best streak and tiers take the highest, lists join, events in time order and each once by
    id. Tested: same as playing, idempotent, order-independent, points recalculated.
  - Guest storage v3 (`cosmic-quiz:profile:v3`): guest id, baseline, profile with its log. A v2
    (or v1) profile carries over as the baseline with a new guest id; the v2 entry is left as
    it was. Past 5,000 events the oldest are folded into the baseline.
  - The merge on sign-in: the guest's baseline and events go to the five tables with
    `Prefer: resolution=ignore-duplicates`. Only when the server has every row does the
    browser start a fresh guest with a new guest id. Then the account's history is read and
    replayed, with anything still pending; no pop-ups for a merge.
  - Signed in: each update's events go to an outbox (cached under
    `cosmic-quiz:account:v1:<user id>`), sent at once and in batches of 500; a failed batch is
    retried row by row. `CQ001`: the row is dropped and a warning logged once per table, no
    retry. Other failures: retried after 30 s and when the browser comes back online.
  - Sign-out: a fresh guest is shown; the account cache is removed unless rows are unsent.
  - With accounts off there is no remote at all: nothing is sent (tested). The off build still
    has no auth or Supabase code; the main bundle grew from 358.20 kB to 370.36 kB (113.64 kB
    gzipped, +4.45 kB) with the history and replay code, which guests use too.

## In progress

- Nothing uncommitted. Next: step d.

## Left

d. `AccountPage.tsx` (export as JSON; delete after the player confirms; sign out) and
   `api/account.py` (delete with the secret key, after `agent/auth.py` checks the token); then
   the `dev/api_server.py` route (granted by main).
e. `PrivacyPage.tsx`. It says: rows kept until the player deletes the account; the per-account
   limit key is a salted hash of the user id, those limit rows stay after deletion and the hash
   is cleared after a day; the session is kept in local storage under `cosmic-quiz:session`.
f. Text for `CHANGELOG.md` and `README.md`, for latency to fold in.
g. After the launch, not now: a purge of long-inactive accounts, in the daily upkeep (latency's).

Not yet seen in a browser: the sign-in panel has unit tests but no header slot yet, so it has
not been drawn on a page. I will drive it in headless Chrome once ui places it or at step d.

## Blocked on

- Before accounts are turned on: `player_answers.seconds` is `NOT NULL` in migration 011, but
  the pages do not pass an answer's seconds to `afterAnswer` today, so those answer rows would
  be refused (HTTP 400, not `CQ001`) and retried for ever. Two fixes, both recommended:
  1. ui: pass the seconds (and the option picked) in the new optional argument. In
     `QuizPage.tsx`, `afterAnswer(p, next.difficulty, question.id, question.topic, score,
     correct, next.streak, { seconds, choice })`; the same in `ExplorePage.tsx`'s `onAnswered`.
  2. data: make the column nullable like `choice`, as a guard: in 011,
     `seconds real check (seconds >= 0)` with the comment "null until the pages send it"; if
     011 has already been run, also `alter table public.player_answers alter column seconds
     drop not null;`. Needs main's approval, since 011 was approved.

## Needs from Vedant

- Run `supabase/migrations/011_accounts.sql` in the Supabase SQL editor after latency's 010. It
  has not run against Postgres yet (no local Postgres here), so a syntax error would show there
  first.
- A Google Cloud OAuth client (web app), with Supabase's callback URL as its redirect.
- In Supabase Auth: Google and email providers on; custom SMTP with Resend; the email template
  with both `{{ .ConfirmationURL }}` and `{{ .Token }}`; site URL
  `https://curiosity.vedantgaikwad.ie`. Redirect URLs, as a sign-in returns to the page it
  started on: `https://curiosity.vedantgaikwad.ie/**`, `http://localhost:5173/**` and the
  preview domain's pattern. Keep "Anonymous sign-ins" off (anonymous users get the
  `authenticated` role and would pass migration 011's policies; `agent/auth.py` refuses them as
  well).
- A Resend account with SPF and DKIM on vedantgaikwad.ie.
- To turn accounts on (only after they are verified): in Vercel, `VITE_ACCOUNTS=on`,
  `VITE_SUPABASE_URL` (the same value as `SUPABASE_URL`) and `VITE_SUPABASE_PUBLISHABLE_KEY`
  (the same as `SUPABASE_PUBLISHABLE_KEY`; browser-safe under hard rule 5); the same three in
  `.env` locally. `.env.example` (no owner) should list them, commented out.
- Pass on the requests above: seo (`connect-src`, and `PATHS.account = "/account"` in
  `src/router.ts`), ui (the `/account` page slot and `<SignInButton />` in the header), latency
  (`authHeader()` from `src/session.ts` in `src/api.ts`, `agent/auth.py` in the limits, retire
  items and never delete them).

## Files changed

- Step a: `agent/auth.py` (new), `tests/test_auth.py` (new).
- `agent/web.py` (one field, one line), `tests/test_auth.py`; `.env.example`.
- `package.json`, `pnpm-lock.yaml`.
- Step b: `src/session.ts`, `src/session.test.ts`, `src/useSession.ts`,
  `src/components/SignInButton.tsx`, `src/components/SignInButton.test.tsx` (all new).
- Step c: `src/profile.ts`, `src/useProfile.ts`, `src/profile.test.ts`.
- This handoff.

## Checks run

On `session/data` at `ad9ecb0`, 2026-11-01, all passing: `pytest` (480 passed), `ruff check`,
`ruff format --check`, `mypy --strict` (86 files), `pnpm typecheck`, `pnpm test` (196 tests in
15 files), `pnpm build` (one JS file; no auth or Supabase code in it). My venv lacked media's
`pillow==13.0.0`, pinned in `requirements-media.txt`; I installed that pin. No other dependency
changed.
