# Handoff: data

Notes for the data session (`docs/SESSIONS.md`). They replace `docs/NEXT_SESSION.md` for this
session. Update them before finishing, and commit them on `session/data`.

Last update: 2026-10-30 (brief written by main)

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

- seo: CSP `connect-src` must allow the Supabase project URL (state the exact origin), and the
  OAuth redirect needs no `form-action` change (check and say so).
- ui: a `/account` route and page slot in `src/App.tsx` and `src/router.ts` (router is seo's; ui
  wires the page); the `SignInButton` slot in the header.
- latency: call `authHeader()` from `src/api.ts`; use `agent/auth.py` in `api/research.py` and
  `api/quota.py` to key limits by account.

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

## Next

## Blockers

## Files touched
