# Next session

Written 2026-10-12, at the end of the session that fixed the scroll bugs and settled the design
questions planned here on 2026-10-10. It holds where things stand, what is left and the prompt to
paste.

## Where things stand

- **Live** at https://cosmic-quiz-agent.vercel.app: everything up to 10b's last push (the scenes,
  the self-hosted fonts, `/privacy`, the link preview). This session's work is **committed but
  not pushed**, so production does not have it yet.
- **This session** (details in `docs/PLAN.md`, "Fixes and design questions" under Session 10):
  - The web page no longer pulls the player back up while a search streams: the agent log
    scrolls only its own box.
  - On an iPhone the home page and the scene no longer jump when Safari's toolbar hides (`svh`
    for the hero and shell, `lvh` for the scene layer), and the slideshow's fade was reworked
    (each image on its own layer, one band instead of a mask on phones).
  - A search makes its questions first and the explanation last; the explanation opens once
    every question is answered, and counts towards Explorer when opened.
  - Learn keeps its controls in a bar at the top while the grid scrolls.
  - Saving progress across devices waits for accounts in v2, with the newsletter.
  - Vedant checked it all on his iPhone over Wi-Fi before the commit: it works.
- **Session 10a:** still open: the SQL editor results for S18 and S19 (run on 2026-10-10, tables
  not pasted yet), and the retention counts after the first purge (the first scheduled run with
  the purge was due on 2026-10-11).
- **Session 10b:** paused by Vedant; the repo **stays private** until the README session. Left:
  the README (a draft is committed), making the repo public (on his word) and the domain (he adds
  the `cosmic` CNAME). Until the domain works, the link preview's image does not load.
- 340 Python and 148 TypeScript tests; every check passes.

## The plan for the next session

1. **Push** this session's three commits on Vedant's word, then check production: the deploy
   succeeded, the pages load with no CSP violation, and Vedant repeats his iPhone check on the
   live site (the web page while a search streams, the home page's scroll and fade, the Learn
   bar). A real search costs about $0.12; the drive's stub is free.
2. **Close 10a** if Vedant pastes the three SQL result tables: S18 (the anon statement timeout)
   and S19 (`public.rls_auto_enable`) in `docs/SECURITY_AUDIT.md`. Re-run the read-only retention
   counts after the purge (`retention_counts.py` was a scratchpad script; recreate it:
   timestamps only, never a hash).
3. **Later sessions:** the README, then going public (on Vedant's word), then the domain.

## Prompt for the next session

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md, docs/NEXT_SESSION.md and docs/SECURITY_AUDIT.md.
> The repo stays private for now.
>
> 1. Push the three commits from the fixes session and check production as planned in
>    docs/NEXT_SESSION.md; I will repeat the iPhone check on the live site.
> 2. If I paste the SQL editor results, close S18 and S19 in docs/SECURITY_AUDIT.md, and re-run
>    the retention counts.
>
> Rules from CLAUDE.md apply: ask before adding any dependency, service or cost; no emojis;
> complete files; commit only when I ask.
