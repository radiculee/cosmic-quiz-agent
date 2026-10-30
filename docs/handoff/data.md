# Handoff: data

Notes for the data session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for this
session. Update them before finishing, and commit them on `session/data`.

Last update: 2026-10-30 (data: migration 011 written, not yet run on the live database)

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

- Plan agreed with Vedant: four choices, each the recommendation (`docs/SESSIONS.md`, Decisions,
  2026-10-30, data). Row claimed. Committed `599a4e8`.
- `supabase/migrations/011_accounts.sql` written, with Vedant's eight changes of 2026-10-30
  (Decisions, second data entry):
  - Five tables: `player_answers`, `player_reads`, `player_runs`, `player_searches`,
    `player_baselines`. Event ids are browser UUIDs; baselines are keyed on
    `(user_id, guest_id)`.
  - Every row references `auth.users(id) on delete cascade`; `item_id` references
    `public.items(id)` (items are never deleted).
  - RLS on; per table, two policies (select own, insert own). All privileges revoked from `anon`
    and `authenticated`, then only select and insert granted to `authenticated`. No update, no
    delete.
  - `check_player_row()` before each insert: server `created_at`, a future `at` clamped to now,
    and the row caps (2,000 answers, 500 reads, 200 runs, 50 searches a day from midnight UTC;
    20 baselines in all), refused with SQLSTATE `CQ001`. The caps are listed in the header.
  - The comment that a future leaderboard must re-score from `item_id` and `choice`, never from
    `correct` or `points`; `topic` is a snapshot, `item_id` the source of truth.

## In progress

- Nothing. Migration 011 is written and committed; it waits for latency's 010 and for Vedant to
  run it.

## Left

1. `agent/auth.py` and `tests/test_auth.py`: check a token with `/auth/v1/user`; also
   `account_visitor(user_id)`, a salted hash of the user id (never the raw id) for
   `on_demand_runs.user_hash`.
2. `src/session.ts`, `src/useSession.ts`, the `VITE_ACCOUNTS` flag, `SignInButton.tsx`. The email
   carries a link and a 6-digit code.
3. `src/profile.ts`, `src/useProfile.ts`: profile v3 (guest id, event log, v2 carried over as a
   baseline), the replay, the merge, the outbox. Required by Vedant:
   - A new `guest_id` after each successful merge, with a test: sign in, sign out, play as a
     guest, sign in again; the second guest's progress is added.
   - An insert refused with `CQ001` is final: drop the row, log it once, no retry. Other errors
     keep the retry.
   - Tests: union, append, idempotent, points recalculated, v2 carried over.
4. `AccountPage.tsx`: export (JSON), delete (the player confirms first), sign out.
   `api/account.py`: delete with the secret key only, after `agent/auth.py` checks the token.
5. `PrivacyPage.tsx`, only after seo's brand pass is on `main` and this branch is rebased. It
   must say: rows are kept until the player deletes the account; the per-account limit key is a
   salted hash of the user id, those limit rows stay after deletion and the hash is cleared
   after a day; the Supabase session is kept in local storage.
6. Text for `CHANGELOG.md` and `README.md`, for latency to fold in.
7. Follow-up after the launch (not now, Vedant 2026-10-30): a purge of long-inactive accounts,
   in the daily upkeep (latency's).

## Blocked on

- Nothing for steps 1 to 4. Step 5 waits for seo's brand pass on `main`.

## Needs from Vedant

- Run `supabase/migrations/011_accounts.sql` in the Supabase SQL editor after latency's 010. It
  has not been run against Postgres yet (no local Postgres on this machine), so a syntax error
  would show there first.
- A Google Cloud OAuth client (web app), with Supabase's callback URL as its redirect.
- In Supabase: Google and email providers on; custom SMTP with Resend; the email template with
  both `{{ .ConfirmationURL }}` and `{{ .Token }}`; site URL `https://curiosity.vedantgaikwad.ie`;
  redirect URLs for localhost, `curiosity.` and the preview domain.
- A Resend account with SPF and DKIM on vedantgaikwad.ie.
- Pass on the requests above: seo (`connect-src`), ui (route and header slot), latency
  (`authHeader()`, `agent/auth.py` in the limits); the `dev/api_server.py` line and adding
  `@supabase/auth-js` to `package.json` (unowned files).

## Files changed

- `supabase/migrations/011_accounts.sql` (new)
- `docs/SESSIONS.md` (my row; two Decisions entries)
- `docs/handoff/data.md`

## Checks run

On `session/data`, 2026-10-30, all passing: `pytest` (361 passed), `ruff check`,
`ruff format --check`, `mypy --strict` (82 files), `pnpm typecheck`, `pnpm test` (149 tests in
13 files), `pnpm build`. None of them run SQL, so they do not test migration 011; it was
checked by reading it, and for balanced brackets and plain ASCII.
