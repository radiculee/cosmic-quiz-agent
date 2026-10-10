# Next session

Written 2026-10-10, at the end of the scenes step. It holds what is left to do and the prompt to
paste into the next Claude Code session.

## Where things stand

- Session 10a is committed (ten commits, one per finding, `f6811e8` to `9a97174`) and pushed.
  Migration 008 is applied. The production header scan passed: all six `vercel.json` headers on
  pages, deep routes, a built asset and API replies, and S1 checked live (details under 10a in
  `docs/PLAN.md`).
- Still open in 10a: the SQL editor results for S18 and S19 (the query was run on 2026-10-10;
  the three result tables are still to be pasted), the read-only retention counts now that 008
  is in, and the 10a gate. `docs/SECURITY_AUDIT.md` still shows S5's production scan and S19 as
  pending.
- The scenes step is built and checked locally (see "Scenes" in `docs/PLAN.md`):
  - the home page is a full-screen hero over a slideshow of three scenes (the observatory, the
    piano, the glasshouse; the portal is left out until its arch is lower), with the progress in
    a solid card below the fold;
  - inner pages show the observatory still; small lines below a page's intro sit on solid chips;
  - 334 Python and 134 TypeScript tests; typecheck, build, ruff, ruff format and mypy --strict
    pass. Vedant approved the screenshots; committed and pushed on 2026-10-10.
- The local `TYPESAFE_API_KEY` is still rejected (HTTP 401), so live searches work only on
  production until it is replaced.

## Vedant, before the next session

1. Look at the scenes on production (the deploy checks of `/scenes/*` are recorded under
   "Scenes" in `docs/PLAN.md`).
2. Paste the three SQL editor result tables (S18's statement timeout, S19).
3. `IP_HASH_SALT` (S14): Vercel does not show the stored value, so it cannot be checked. If in
   doubt, replace it with a new value from `python -c "import secrets; print(secrets.token_hex(32))"`
   and redeploy. Side effects, all once: today's per-visitor counts start again, outstanding
   reveal tokens stop working, and a visitor could report an item they reported before.
4. **Optional:** install the latest Python 3.12 and recreate `.venv` (S16). Decide the review
   queue with `python -m curator review` (items 198, 202 and 203).

## Prompt for the next session

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md, docs/NEXT_SESSION.md and docs/SECURITY_AUDIT.md.
> Session 10a and the scenes step are committed and pushed.
>
> 1. Close Session 10a. Record the SQL editor results I paste for S18 and S19, and the
>    production header scan of 2026-10-10 (recorded under 10a in docs/PLAN.md) as S5's
>    production check. Run the read-only retention counts again now that 008 is in. Then
>    update docs/SECURITY_AUDIT.md and the 10a gate in docs/PLAN.md.
> 2. Then Session 10b as planned in docs/PLAN.md, with the scenes step's changes: the OG card is
>    the observatory scene with the title and tagline, and LICENSE and the README say the scene
>    art is not covered by MIT (confirm the generator's name, recorded as one_prompt_design).
>
> Rules from CLAUDE.md apply: ask before adding any dependency, service or cost; no emojis;
> complete files; commit only when I ask.
