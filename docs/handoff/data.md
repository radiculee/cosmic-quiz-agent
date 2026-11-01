# Handoff: data

Notes for the data session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for this
session. Update them before finishing, and commit them on `session/data`.

Last update: 2026-11-01 (data: step a done, `agent/auth.py`; step b next)

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
- Step a, `afe8ef4`: `agent/auth.py` and `tests/test_auth.py` (30 tests).
  - `TokenChecker.user_id(authorization)` asks Supabase's `GET /auth/v1/user` with the
    publishable key and returns the user's UUID, or None. One request, a 5 s timeout, no retry.
  - None for: no or malformed bearer header (no request sent), any 4xx (expired, signed out,
    deleted), an anonymous user, an unexpected reply. 429, 5xx and network errors are also None
    and are logged to stderr.
  - `signed_in_user(authorization)` reads `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` from
    the environment; a guest when they are not set.
  - `account_visitor(user_id, salt)`: sha256 of `"{salt}:account:{user_id}"`, the same form as
    `agent.web.salted_hash`, never the raw id; it cannot match an IP key.

## In progress

- Nothing uncommitted. Next: step b.

## Left

b. `src/session.ts`, `src/useSession.ts`, the `VITE_ACCOUNTS` flag (off by default),
   `SignInButton.tsx`; `@supabase/auth-js` in `package.json` and `pnpm-lock.yaml` in its own
   commit (approved by Vedant). The email carries a link and a 6-digit code.
c. Profile v3 in `src/profile.ts` and `src/useProfile.ts`: guest id, event log, v2 carried over
   as a baseline, the replay, the merge and the outbox.
   - A new `guest_id` after each successful merge, with a test: sign in, sign out, play as a
     guest, sign in again; the second guest's progress is added.
   - An insert refused with `CQ001` is final: drop the row, log it once, no retry. Other errors
     keep the retry.
   - Tests: union, append, idempotent, points recalculated, v2 carried over.
d. `AccountPage.tsx` (export as JSON; delete after the player confirms; sign out) and
   `api/account.py` (delete with the secret key, after `agent/auth.py` checks the token).
e. `PrivacyPage.tsx` (free now: seo's brand pass is on `main`). It says: rows kept until the
   player deletes the account; the per-account limit key is a salted hash of the user id, those
   limit rows stay after deletion and the hash is cleared after a day; the Supabase session is
   kept in local storage.
f. Text for `CHANGELOG.md` and `README.md`, for latency to fold in.
g. After the launch, not now: a purge of long-inactive accounts, in the daily upkeep (latency's).

## Blocked on

- Step d's `api/account.py` needs the request's `Authorization` header, and `ApiRequest` in
  `agent/web.py` does not carry it. `agent/web.py` has no owner in `docs/SESSIONS.md`. The change,
  for Vedant to approve or assign:
  - in `ApiRequest`, add `authorization: str = ""` with the comment
    `# The Authorization header as sent ("Bearer <token>" when signed in); "" when absent.`
  - in `request_from_environ`, add
    `authorization=str(environ.get("HTTP_AUTHORIZATION", "")),`
  latency needs the same field to key `api/research.py` and `api/quota.py` by account.
- `dev/api_server.py` (no owner) needs `account` in its `from api import ...` line and
  `"/api/account": account.app,` in `ROUTES`, for step d to run locally.

## Needs from Vedant

- Run `supabase/migrations/011_accounts.sql` in the Supabase SQL editor after latency's 010. It
  has not run against Postgres yet (no local Postgres here), so a syntax error would show there
  first.
- A Google Cloud OAuth client (web app), with Supabase's callback URL as its redirect.
- In Supabase Auth: Google and email providers on; custom SMTP with Resend; the email template
  with both `{{ .ConfirmationURL }}` and `{{ .Token }}`; site URL
  `https://curiosity.vedantgaikwad.ie`; redirect URLs for localhost, `curiosity.` and the preview
  domain. Keep "Anonymous sign-ins" off (anonymous users get the `authenticated` role and would
  pass migration 011's policies; `agent/auth.py` refuses them as well).
- A Resend account with SPF and DKIM on vedantgaikwad.ie.
- The two unowned-file changes under "Blocked on".
- Pass on the requests above: seo (`connect-src`), ui (route and header slot), latency
  (`authHeader()`, `agent/auth.py` in the limits, retire items and never delete them).

## Files changed

- Step a: `agent/auth.py` (new), `tests/test_auth.py` (new).
- This handoff.
- Earlier (on `main`): `supabase/migrations/011_accounts.sql`, `docs/SESSIONS.md`.

## Checks run

On `session/data` at `afe8ef4`, 2026-11-01, all passing: `pytest` (478 passed), `ruff check`,
`ruff format --check`, `mypy --strict` (86 files), `pnpm typecheck`, `pnpm test` (156 tests),
`pnpm build`. My venv lacked media's `pillow==13.0.0` (already pinned in
`requirements-media.txt`, read by `requirements-dev.txt`); I installed that pin so `mypy` could
check `curator/images.py`. No dependency file changed.
