# Next session

Written 2026-10-09, during Session 10a. It holds what is left to do and the prompt to paste into the
next Claude Code session.

## Where things stand

- Session 10a's audit is done and recorded in `docs/SECURITY_AUDIT.md`: 19 findings, none High
  (5 Medium, 10 Low, 4 Info).
- Fixed on Vedant's choice, each with its test (nothing committed yet):
  - S1: the API refuses requests other sites' pages send, and a POST must carry JSON.
  - S2: 10 reports a day per visitor, and `python -m curator review --reported`.
  - S3: the limits are read before the paid on-topic check.
  - S4: redirects are followed in code, with each hop checked against the allow-list; the
    default port only; dot segments resolved.
  - S5: security headers in `vercel.json`, checked locally on every page with no CSP violation.
  - S13: migration 008, a daily purge of visitor hashes.
  - S17: IPv6 visitors counted by their /64.
- Accepted for now: S6 to S12 and S14, to revisit after launch. S15 is accepted, with the
  defences in code.
- Checks: 330 Python and 116 TypeScript tests; typecheck, build, ruff, ruff format, mypy
  --strict and the control-character scan all pass. `pnpm audit` and pip-audit (pinned in
  `requirements-dev.txt`) are clean.
- The local `TYPESAFE_API_KEY` is still rejected (HTTP 401), so live searches work only on
  production until it is replaced.

## Vedant, to finish 10a

1. Run the SQL editor query in `docs/PLAN.md` (Session 10a, the RLS item) and paste its three
   result tables. They close S19 (`rls_auto_enable`) and confirm the anon statement timeout for
   S18.
2. Paste `supabase/migrations/008_purge_visitor_hashes.sql` into the SQL editor **before** the
   push. Until 008 is in, the scheduled `upkeep` fails.
3. Check that the Vercel `IP_HASH_SALT` is 64 random hex characters (S14).
4. Commit and push when happy. Claude Code then scans production's headers, and the 10a gate
   follows.
5. **Optional:** install the latest Python 3.12 and recreate `.venv` (S16). Decide the review
   queue with `python -m curator review` (items 198, 202 and 203).

## Prompt for the next session

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md, docs/NEXT_SESSION.md and docs/SECURITY_AUDIT.md.
> Session 10a's fixes are committed and pushed, and migration 008 is applied.
>
> 1. Close Session 10a. Record the SQL editor results I paste for S18 and S19. Scan
>    production's response headers, for a page and for an API reply, against `vercel.json`.
>    Run the read-only retention counts again now that 008 is in. Then update
>    docs/SECURITY_AUDIT.md and the 10a gate in docs/PLAN.md.
> 2. Then the scene-backgrounds step (below), and Session 10b after it, as planned in
>    docs/PLAN.md.
>
> Rules from CLAUDE.md apply: ask before adding any dependency, service or cost; no emojis;
> complete files; commit only when I ask.

## After 10a: scene backgrounds and the home slideshow (planned 2026-10-10)

Planned in a grill-me session and approved by Vedant. Four of his AI-generated scenes become a
slideshow on a full-screen home hero: the observatory, the portal, the piano and the glasshouse
(masters in `bg_images/Observatory_images_one_prompt/`). The inner pages show the observatory as
a still.

- **Where the plan is:** `C:/Users/vedan/.claude/plans/pasted-content-id-0e6e-use-the-fluffy-trinket.md`
  ("Scene backgrounds and the home slideshow") holds the decisions, the open questions and the
  prompt to paste.
- **When:** its own step, after 10a is committed and before 10b.
- **What it changes in 10b:**
  - the OG card becomes a scene with the title;
  - LICENSE and the README get a note that the art is kept out of MIT.
