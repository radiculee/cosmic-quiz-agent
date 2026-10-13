# Next session

Written 2026-10-13, at the end of the session that started the domain step of 10b. It holds where
things stand, the to-do list and the prompt to paste.

## Where things stand

- **Live** at https://cosmic-quiz-agent.vercel.app: everything through the fixes session
  (`71a5712`, pushed 2026-10-12 and deployed at 15:33 UTC; production checked read-only).
- **The domain (10b), in progress:**
  - `cosmic.vedantgaikwad.ie` is added to the Vercel project `cosmic-quiz-agent` (Vercel CLI,
    signed in as `radiculee`; `vedantgaikwad.ie` was already on the account, so no TXT check).
  - Vedant added the record at Web Hosting Ireland: `cosmic`, CNAME, `cname.vercel-dns.com`, TTL
    14400 (the same kind of record as `www`). By 14:21 UTC all four of the domain's DNS servers
    and Google's and Cloudflare's resolvers returned it (zone serial 2026101300).
  - At the end of the session Vercel had not verified the domain yet, so there was no HTTPS
    certificate (`vercel domains inspect` still said "not configured properly"; it retries on
    its own, and the dashboard's Domains page has a Refresh). Vedant runs the checks on the new
    domain himself.
- **Decided 2026-10-13** (Vedant, each as recommended; recorded in `docs/PLAN.md` under 10b):
  the domain first, then the README session, then going public; the old address redirects in
  `vercel.json`, deployed only once the new domain answers over HTTPS.
- **Not committed, in the working copy:**
  - `docs/PLAN.md`: the fixes session's push, deploy and production check; the Security
    Checkpoint seen on 2026-10-12 (Vercel's automatic protection, gone by 2026-10-13); today's
    two decisions.
  - `vercel.json`: the redirect (a permanent 308; source `/:path*`, only the host
    `cosmic-quiz-agent.vercel.app`, to `https://cosmic.vedantgaikwad.ie/:path*`).
  - `tests/test_packaging.py`: its test, which also holds the domain to `index.html`'s `og:url`
    (16 packaging tests pass).
  - This file.
  - **Do not push the redirect before the new domain answers over HTTPS**, or the old address
    would send every visitor to a domain that does not work yet.
- **10a:** the retention counts after the purge, read-only on 2026-10-13 at 14:21 UTC
  (timestamps only; scratchpad `retention_counts.py`): 0 of 19 live runs still hold a visitor
  hash (7 did before the first purge); 3 request windows, none older than a day; the one report
  keeps its hash, 10 days old (under the 30 decided). Both scheduled runs since migration 008
  succeeded (2026-10-11, 2026-10-12). Still open: S18 and S19, waiting for the SQL editor tables.
- 340 Python and 148 TypeScript tests; every check passed at the last commit.

## To-do list for the next session

1. **Confirm the domain.** Vedant reports his checks. Then read-only: `vercel domains inspect`
   shows it configured; `https://cosmic.vedantgaikwad.ie` answers `/`, `/learn/quasars`,
   `/explore/stats` and `/privacy` with 200 and the six `vercel.json` headers; `/api/topics`
   and `/api/quota` answer 200; `/og-v1.jpg` is the 1200x630 JPEG; S1 holds on the new host (a
   cross-site GET that reaches a function gets 403, a `text/plain` POST gets 415); headless
   Chrome shows no CSP violation, console error or blocked load, with the fonts and scenes
   loading from the new host. If Vercel still has not verified it, find out why before anything
   else.
2. **Ship the redirect.** Show the diff; run pytest, ruff, mypy --strict, typecheck and build;
   commit (the redirect and the docs) and push on Vedant's word. After the deploy:
   `https://cosmic-quiz-agent.vercel.app/learn/quasars?x=1` answers 308 to
   `https://cosmic.vedantgaikwad.ie/learn/quasars?x=1`, `/api/topics` on the old host answers
   308, and the new host is not redirected (no loop).
3. **Vedant on the new domain:** on his iPhone, one real search on the web page (about $0.12,
   one of his 2 a day: the questions first, the log never pulling him up, the explanation after
   the last answer), the home page's scroll and fade, and the Learn bar; the link shared in
   WhatsApp shows the preview (image, title, tagline).
4. **Record it:** `docs/PLAN.md` (10b's domain item ticked with what was checked; the session
   log); `docs/SECURITY_AUDIT.md` (S13: the retention counts above; S18 and S19 if Vedant pastes
   the tables); this file for the session after.
5. **Plan the README session** (Vedant redoes the draft in a session of its own): ask him first
   what he wants from it (who it is for, how long, what to keep from the draft), one question
   at a time with a recommendation.
6. **Later, going public** (on Vedant's word): gitleaks again over the commits since the last
   scan, Vedant's read of `docs/` and `CLAUDE.md`, `gh repo edit --visibility public`, secret
   scanning with push protection and Dependabot alerts, the repo's description and homepage,
   and the header's GitHub icon pointed at the repo (`GITHUB_URL` and its label in
   `src/components/SiteHeader.tsx`).

## Prompt for the next session

> Read CLAUDE.md, docs/DESIGN.md, docs/PLAN.md, docs/NEXT_SESSION.md and docs/SECURITY_AUDIT.md.
> The repo stays private for now.
>
> Work through the to-do list in docs/NEXT_SESSION.md, in order:
> 1. Confirm the domain cosmic.vedantgaikwad.ie (I will report my own checks first), with the
>    read-only checks listed there.
> 2. Ship the redirect from cosmic-quiz-agent.vercel.app that is waiting in the working copy:
>    show me the diff, run every check, and commit and push only when I say so, never before
>    the new domain answers over HTTPS. Then check the redirect on production.
> 3. I check the new domain on my iPhone and share the link in WhatsApp.
> 4. Record the results in the docs, and close S18 and S19 if I paste the SQL editor tables.
> 5. Plan the README session: ask me what I want from it, one question at a time, each with a
>    recommendation.
>
> Rules from CLAUDE.md apply: ask before adding any dependency, service or cost; no emojis;
> complete files; commit only when I ask.
