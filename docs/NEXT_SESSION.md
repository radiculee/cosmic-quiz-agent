# Next session

Written 2026-10-13, at the end of the domain session (10b). It holds where things stand, the
to-do list for the README session and the prompt to paste.

## Where things stand

- **Live** at https://cosmic.vedantgaikwad.ie, with a Let's Encrypt certificate (issued about
  14:54 UTC on 2026-10-13, 90 days, renewed by Vercel). Every read-only check passed there:
  the pages and their six headers, the API, the link preview's image, S1, and headless Chrome
  on every page with no CSP violation or error.
- **The old address redirects:** every path on `cosmic-quiz-agent.vercel.app` answers a
  permanent 308 to the same path and query on the new domain (`vercel.json`, held by a packaging
  test). The first version (`/:path*`) missed the home page in Vercel's strict matching; the fix
  (`/:path(.*)`) is live. Deployment URLs keep Vercel's login wall.
- **Pushed on 2026-10-13:** `bfff85e` the redirect, `b60c97c` the earlier docs, `9366531` the
  home-page fix.
- **This session's records:** `docs/PLAN.md` (10b's domain item, the README decisions, the
  session log) and `docs/SECURITY_AUDIT.md` (S1 and S5 on the new domain, S13's counts after
  the purges, S18 and S19 closed: every finding is now fixed or accepted with a reason, except
  S16, the local Python update, which is Vedant's own action outside the repo).
- **Vedant's iPhone check** passed on the new domain (Safari), with a live search on
  "Wormhole": 4 runs, the questions first and the explanation last, $0.103 on Anthropic.
- **The link preview** checked by Vedant in WhatsApp on the new domain: the image, "Cosmic
  Quiz" and the tagline. Of 10b's gate, the README and the public repo are what is left.
- **Review queue:** 9 items (186, 187, 188, 193, 198, 202, 203, 206, 210), for
  `python -m curator review` whenever Vedant wants.
- **The Curator** runs `upkeep` (free) every day until 31 October; from 1 November it runs
  `daily` (about $0.17 a day, capped at $0.40) without any change.
- 341 Python and 148 TypeScript tests; every check passed at the last commit.

## To-do list for the README session

The README is redone in this session, as decided on 2026-10-13 (`docs/PLAN.md`, 10b, "The
README session"): recruiters first, then engineers; the draft's depth with a sharper first
screen; three highlights (it checks itself, it runs on its own, live at a capped cost); the
gate table and costs, the Mermaid diagram, and security and privacy kept; setup and the repo
map moved to `docs/DEVELOPMENT.md`; three screenshots; neutral voice with one "I" line; and a
CI workflow that runs every check on each push, with its badge in the README.

1. **Ask first,** one at a time, each with a recommendation:
   - The "I" line: Vedant's own reason for building it, or a draft for him to edit.
   - The agent-log screenshot: a real search on production (about $0.12, one of Vedant's 2 a
     day) or a real search against the local server (the same cost), rather than the free stub,
     whose log lines are made up. A README should not show invented agent output.
   - Security and privacy: as long as the draft, or a few lines each with links to
     `docs/SECURITY_AUDIT.md` and `/privacy`.
   - How pnpm gets onto the CI runner: `package.json` pins no pnpm version (no
     `packageManager` field; pnpm 11.5.0 and Node 24 locally). The options are the pinned
     `pnpm/action-setup` action (third party) or a `packageManager` field with corepack, if
     Node 24 on the runner still ships it.
   - Anything that would need a new tool or a cost.
2. **Build:** the new `README.md`; `docs/DEVELOPMENT.md` (setup, the checks, the repo map from
   the draft); the three screenshots under `docs/images/`, made with headless Chrome at a
   size that reads on GitHub; `NOTICE` naming the screenshots (they show the scene art);
   `.github/workflows/checks.yml` (every check on each push and pull request, no secrets, no
   paid calls, actions pinned to commits, `permissions: contents: read`) and its badge at the
   top of the README. Every number in the README checked against its source
   (`docs/EVALS.md`, `docs/PLAN.md`, the live analytics).
3. **Check:** the README as GitHub renders it (the Mermaid diagram, the images, the links),
   including on a phone; every relative link resolves; the usual checks pass.
4. **Vedant reads it** as someone who has never seen the project; then the commit and push on
   his word, and the first run of the checks workflow on GitHub passes (its badge green).

## Later: going public (on Vedant's word)

gitleaks again over the commits since the last scan; Vedant's read of `docs/` and `CLAUDE.md`;
`gh repo edit --visibility public`; secret scanning with push protection and Dependabot alerts;
the repo's description and homepage (`https://cosmic.vedantgaikwad.ie`); and the header's
GitHub icon pointed at the repo (`GITHUB_URL` and its label in `src/components/SiteHeader.tsx`).
That closes the 10b gate.

## Prompt for the next session

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md, docs/NEXT_SESSION.md and README.md.
> The repo stays private for now.
>
> This is the README session (10b). Work through the to-do list in docs/NEXT_SESSION.md:
> 1. Ask me the open questions first, one at a time, each with a recommendation.
> 2. Rewrite README.md as decided on 2026-10-13, move setup and the repo map to
>    docs/DEVELOPMENT.md, make the three screenshots, and add the checks workflow.
> 3. Check it as GitHub renders it, and every number against its source.
> 4. Show me the result; commit and push only when I say so.
>
> Rules from CLAUDE.md apply: ask before adding any dependency, service or cost; no emojis;
> complete files; commit only when I ask.
