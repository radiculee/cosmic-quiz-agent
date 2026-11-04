# Handoff: main (coordinator)

Notes for the main session (`docs/SESSIONS.md`), which plans, writes the other sessions' briefs
and reviews their branches. It edits no code: only `docs/SESSIONS.md` and `docs/handoff/*.md`
(and `docs/DESIGN.md` and `CLAUDE.md` when Vedant approves the exact text).

Last update: 2026-11-02, 04:35 Dublin, on Windows, when Vedant ended the session and closed every
worktree session. "Next session: start here" below is current. The sections after it are the
record: where they differ, the newer one wins.

## Read first (a new main session)

1. `CLAUDE.md`, then this file down to "How Vedant wants main to work".
2. `docs/SESSIONS.md`: "The pre-launch overhaul (2026-10-30)" ownership, then the newest entries
   under Decisions.
3. Only when needed: `docs/handoff/<name>.md` on each session's branch. They hold the detail.

First message for a new main session on Windows:

> You are the "main" session for Curiosity (repo cosmic-quiz-agent), the coordinator and reviewer
> for the launch on Tuesday 3 November. Code freeze is Monday 2 November 18:00 Dublin. Read
> CLAUDE.md, then docs/handoff/main.md from the top down to "How Vedant wants main to work", then
> the newest Decisions in docs/SESSIONS.md. Also read your memory files planner-role and
> agent-prompt-style. Run the commands under "Check first" in that handoff. Update the Curiosity
> Launch Board (https://claude.ai/artifact/4jKPNn9EFeGssaVp8UshfX) if anything has changed. The
> worktree sessions are closed, so start one only when its task is next. Then tell me in short:
> where things stand, what you are waiting on, and the next thing I must do. We do DNS and HTTPS
> for curiosity. first, together, using "Next session: start here". Do not push, land or start
> anything until you have told me that.

## Launch day: start here (written 2026-11-03, 14:55 Dublin)

This replaces the section below where they differ. Date check: launch day is Tuesday 3 November.

**Update, Wed 4 November, 00:55 Dublin. Steps 1 to 5 and 7 below are done.** Vedant said yes to all.
The bank has 56 picture rows and no facts, 28 locked. All 39 live cards show a picture, and `/learn`
is clean at 1280 and 390. The other 17 topics have pictures saved, but Learn lists a topic only when
it is on every level, so they appear later, including Black holes, The Habitable Zone and Fast radio
bursts. `TOPIC_IMAGES` is on, from 00:51 UTC, on his word. This file and `docs/SESSIONS.md` are
committed. His iPhone check passed at 01:06. Open: step 6 (he posts). New, 01:20: ui is building one
focus on each landing page (brief `brief-ui-landing.md` in the scratchpad below). Review its report
by commit hash, land with `git merge --ff-only <sha>`, and push on his word. Scripts and the fill's log:
`C:\Users\vedan\AppData\Local\Temp\claude\49a50dcdfe0361ef\983996c7-8a36-46eb-825a-3a7b5780f729\scratchpad\`.

**Live:** `main` and `origin/main` are at `4ae4b43` on `curiosity.vedantgaikwad.ie`. GitHub Checks
passed. `cosmic.`, the six aliases and the `vercel.app` address answer 308 and keep the path. The
home page and each prerendered page carry the new title. The preview image is `public/og-v2.jpg`.
The GitHub website field says `curiosity.`. The README is rewritten and live.

**Decided by Vedant today:**
- Accounts off for launch. The 30-topic fill moves to this week.
- Console at $32, confirmed by him.
- Learn cards go live BEFORE the LinkedIn post. He has not posted yet.
- Cards: 17 replacement pictures, V838 for Light speed, 6 doubtful pictures kept, 8 credit fixes,
  and a square card cut directly from the source (compact cards stay).

**Stopped at 15:40 UTC, on Vedant's session limit. No agent is running.** Live code is `4ae4b43`
(`main` equals `origin/main`, Checks green): square 320 x 320 cards and the Learn card fixes. 012 is
pasted and confirmed. **Only Auroras has a picture**, as the real upload test. `TOPIC_IMAGES` is
not set. He has NOT posted on LinkedIn: hold the post until the cards are done.

**His open question (he has not answered):** yes or no to 7 picture swaps he has not seen, and one
credit. Sheet numbers: 32 Drake equation (Golden Record), 16 Types of galaxies (9 WISE spirals), 10
Life cycle of a Sun-like star (ESO), 21 The Big Bang (Ultra Deep Field, was a keep), 52 The Habitable
Zone (Kepler-186f), 36 White dwarf planets (debris), 55 Fast radio bursts (ESO, still dark). Credit:
Black holes becomes "Event Horizon Telescope/ESO", the same file as Event horizons. Main recommends
yes to all. Do not run the fill before his answer: a fill writes its own choice for any topic that
has no locked row, and the pictures go live at once.

**Files**, in
`C:\Users\vedan\AppData\Local\Temp\claude\c--Users-vedan-cosmic-quiz-agent\9fca8f3d-8dcb-4aa0-968c-f15c813470bf\scratchpad\final\`:
`sheet.png` (all 56 at real size), `overrides.json` (27 rows), `cards\`, `downloads\`. Reports:
`docs/handoff/media.md`, `docs/handoff/ui.md`.

**Next, in order, after his yes:**
1. Write a scratch script (not in the repo) for the overrides. For each row: download `download_url`,
   `curator.images.render`, upload through `MediaStore`, save with `locked = true`. Use the `credit`
   exactly as given: the card splits it at the licence. Add a Black holes row. Types of galaxies has
   no override, because it is the fill's own choice. Read `overrides.json` as UTF-8. Use the main
   `.venv`, which has Pillow.
2. Run `python -m curator.images` from the main folder, set `PYTHONIOENCODING=utf-8`. Locked rows are
   skipped, and Auroras is left alone. It makes no model call. The earlier dry run took 141 s.
3. Check `/api/topics`: each card has a picture and none has a fact. Check a few `/media` files.
4. Set the repository variable `TOPIC_IMAGES=on`, on his word (`gh variable set`).
5. Drive `/learn` at 1280 and 390: no CSP violation, no page error. Vedant looks on his iPhone.
6. Tell him to post, and to run the link through LinkedIn's Post Inspector first.
7. Commit this file on his word. It is still uncommitted.

**Found today, for this week:**
- A leading "The" makes a second, paid topic: `agent/bank.py:393`, `src/topics.ts:12`. Topics 377
  and 397 are the same subject. Retire 397 with the fix (his yes was read as covering this).
- Item 154 had a false sentence (first ISS module "1 January 1998"). Removed on his word. Jev had
  marked it contradicted at 0.67, and it was still published, probably at human review. Audit other
  reviewed items. Its stored sentence check stays, so the count is one too high.
- An unknown address answers HTTP 200, not 404. No deploy hook is set. Per-topic previews are open.
- The fact-picking rule scored 0 of 4: `_DANGLING_START` in `curator/images.py` needs work.
- CHANGELOG lacks today's work and still calls easy-first unmeasured. `docs/DEVELOPMENT.md` line 3
  and `docs/DESIGN.md` lines 52, 58, 121 and 156 are old. latency's $32 drafts wait for Vedant.
- `.claude/worktrees/` sits inside the main folder, so `load_dotenv` finds the main `.env` from
  there. Run stubs and tests from a worktree outside the main folder.

## Next session: start here (written 2026-11-02, 04:35)

**Live:** `main` and `origin/main` are at `fa23eda` on `cosmic.vedantgaikwad.ie`. GitHub Checks
passed, and the live site served the bundle built from the tested tree. It holds the easy-first run
order and ui's six pieces (3 bars, question on top, Next waits, Web results card, new text, Quiz page
text). This file is uncommitted in the main folder: do not lose it, and commit it on Vedant's word.

**Sessions:** Vedant closed them, so their `cc-msg` addresses are dead. Restart one in its worktree
with the command in the memory file planner-role. Worktree `.env` files still hold dead keys, on
purpose.

| Branch | Head | Against `fa23eda` | State |
| --- | --- | --- | --- |
| latency | `e5a41fb` | 1 ahead, `docs/handoff/latency.md` only | Stopped. Needs the measurement below in its CHANGELOG. Land its note with the next batch |
| ui | `fa8b0ab` | 1 ahead, `docs/handoff/ui.md` only | Land with the next batch |
| seo | `b02190a` | 14 ahead, 0 behind | Approved by main, its checks as seo reported them. Held for HTTPS |
| data | `adabfde` | 7 ahead, 9 behind, may add a handoff commit | Steps d and e not reviewed. Accounts off |
| media | `8d4ff76` | 51 behind, 2 uncommitted files | No report since 30 October. Could not be reached |

**The first real search of the easy-first order** (search 104, "The Cosmic Microwave Background",
2 November 04:24:49 UTC, read from `on_demand_runs`; n=1):

| Item | Finished after | Outcome | Spent |
| --- | --- | --- | --- |
| Quiz easy | 21.6 s | published | $0.0270 |
| Explanation easy | 41.3 s | published | $0.0232 |
| Explanation medium | 41.7 s | published | $0.0228 |
| Quiz medium | 45.8 s | published | $0.0245 |
| Explanation hard | 81.6 s | published | $0.0306 |
| Quiz hard | 97.0 s | discarded | $0.0280 |

Whole search 97.0 s, $0.1561, against search 86's 61.3 s and first question at 49 s (also n=1, all
items at once). So the first question came sooner, the whole search took longer, and it passed
latency's "up to about 90 s" estimate. Both are single searches on different topics, so this shows
no trend. The player got 2 of 3 questions, because the hard one was discarded. `started_at` is the
reservation time for every run of a search, so it does not show when a later run really began.
Vedant reports that the search worked; main saw a screenshot of it running, not its end.

A search of "Soyuz spacecraft and crewed missions" (search 98) started at 04:08 UTC on the live
site, before this push, so it ran all at once. It did not come from main's stub, whose writes are in
memory. Vedant's screen showed 1 of 2 left after search 104, so it may be another visitor or
Vedant on another address. Not looked into further.

**Checked 2026-11-03, 13:26 UTC:** launch day, and the 18:00 freeze has passed with DNS not done.
All seven hosts are still "no such name" and not on Vercel. `origin/main` is still `fa23eda`.
The Curator run of 2 November proved the GitHub key: `Done: 9 jobs run, 5 published, 2 for review,
2 discarded`, about $0.24, both modes. Today's run had not started yet. Whether landing seo after
the freeze is still wanted is Vedant's call.

### Do these in order

1. **DNS and HTTPS, with Vedant, before the 18:00 freeze.** Still "no such name" at 03:54 UTC. At
   Web Hosting Ireland he adds seven CNAMEs, TTL 14400, target `cname.vercel-dns.com` (what `cosmic`
   uses and has proven at this host; Vercel's first choice is
   `b3b826af597f5d11.vercel-dns-017.com`): `curiosity`, `quiz`, `astro`, `cosmik`, `curiousity`,
   `curiosty`, `cosmicquiz`. Leave `cosmic` alone. Main checks over DoH. Then, on his word, main adds
   the seven hosts with `vercel domains add <host> cosmic-quiz-agent`. Records go first: on
   2026-10-13 Vercel's lookup before the record existed left the certificate stuck. If one sticks:
   he presses Refresh on the Domains page, then `vercel certs issue <host>`, which may print
   "Response Error" and still work. Trust `/v6/domains/<host>/config`, with `MSYS_NO_PATHCONV=1`.
   There is no CAA record, and DNSSEC looks off. Checks: HTTPS on each host.
2. **Land seo `b02190a`, then ui `fa8b0ab`, on Vedant's word.** First check Vercel's build: it needs
   the bank values, or the prerender makes only the 4 fixed pages, and Node 22.18 or newer. Rerun
   every check. After the deploy: `cosmic.` and each alias answer 301 to the same path on
   `curiosity.`, `/learn/antimatter` shows its text, title and JSON-LD, and there are no CSP
   violations. Then restart ui for the NotFoundPage hook.
3. **Daily Curator, about 12:00 to 13:30 UTC.** First real test of the GitHub key. Read the log's
   `Done:` line. Check that it runs both modes, then see whether later first calls are fast.
4. **Fill, on main's word only.** Needs: Console at $32, one cheap key test from the `.env` it uses,
   the key copied to `cqa-latency/.env` just before. 30 topics, `--cap 5.00`. Vedant then reviews
   about 65 to 85 items before 3 November. Restart latency for this and give it the measurement
   above for the CHANGELOG, marked n=1.
5. **Media.** Start a session in `cqa-media`. Ask for a report and why `curator/images.py` and
   `tests/test_images.py` are uncommitted. Images need 012, its dry run read, `TOPIC_IMAGES=on`, and
   seo's `/media` rewrite, so they come after step 2. Third on the cut list.
6. **Data.** Review steps d and e. Only if Vedant turns accounts on: the setup in
   `docs/handoff/data.md`, the wiring (ui, seo, latency) and the real checks.

### Waiting on Vedant

1. DNS records (step 1).
2. **Accounts on or off for launch.** Main recommends off: never run against real Google, Resend or
   Supabase Auth, and 011 has never run on Postgres. Told to him on 2 November; no answer yet.
3. Whether a media window was still open. If it holds work, read it before closing.
4. A screenshot of 013's check: it must end with an error reading CHECK PASSED.
5. Console limit to $32, and the rate-limit tier.
6. Approve or change latency's `CLAUDE.md` and `docs/DESIGN.md` drafts ($32).
7. `public/og-v2.jpg`: the current preview image still says COSMIC QUIZ.
8. After DNS: Search Console, sitemap, Bing, links in (order in `docs/handoff/seo.md`).
9. Optional: `VERCEL_DEPLOY_HOOK_URL`. The workflow skips it if missing.

Accepted by Vedant on 2 November (his "yes" to landing, read by main as covering all three; he did
not object when told): a trophy can cover the first question on a new player's first search; the
line reads "Explanations: 0 of 3 ready" when caps left them all out; two slow batches could pass
300 s and leave runs unsettled.

**Free stub drive:** `stub_api.py`, `serve_stub.py`, `drive.mjs`, `show.py` in
`C:\Users\vedan\AppData\Local\Temp\claude\c--Users-vedan-cosmic-quiz-agent\6aee6f91-32a5-43c7-8609-1ceb8aa63077\scratchpad\`,
if still on disk. Run `stub_api.py` with the tested worktree as the working directory, or it
imports other code. It takes only the two read-only bank values from the main `.env`. A topic
starting `FailEasy` fails easy at $0, and `Fit2` lets the caps fit two items.

## Where things stood (2026-11-02, 03:50)

**Update after that:** Vedant said yes, so latency `7b00bf3` and ui `1261fa7` (cherry-picked with
`-x`) are on `origin/main` at `fa23eda`. GitHub Checks passed, and the live site serves the bundle
built from the tested tree (`index-BHC2xZzn.js`). The real search is next. Vedant moved DNS and
HTTPS to the next main session: keep it before the 18:00 freeze, and walk him through it first.
Accounts are still off. Their `connect-src` is in seo's held work and their site URL is `curiosity.`,
so turning them on depends on DNS as well.

**Live:** `main` and `origin/main` are at `2435f0c` on `cosmic.vedantgaikwad.ie`. GitHub Checks
passed. It holds November's budget, parallel search, the Curiosity name, the sticky header, card
buttons, rover ranks, Learn cards B, progress rows, sign-in groundwork (flag off, no auth code in
the bundle), the fill command (not run), the red daily run, and free failed searches.

**Database:** 010 and 013 are pasted and confirmed by read-only calls. 011 and 012 are not pasted.
013's check script is **not confirmed**: Vedant reported "success row passed", but that script can
only end with an error reading CHECK PASSED or CHECK FAILED. Main asked for a screenshot.

**Anthropic key:** the old key stopped working after 2026-10-30. Vedant replaced it on 2 November
in GitHub (03:03 UTC), Vercel (redeployed) and the main folder's `.env`. The free models call gives
200, and search 86 proved Vercel's key. **The worktree `.env` files still hold old keys, on
purpose:** a local `dev.api_server` writes to the live bank, so a working key there would spend
money. Copy the key to `cqa-latency/.env` only just before the fill. ui asked for a key; the
answer is no. Today's daily Curator run (about 12:00 to 13:30 UTC) is the first real test of the
GitHub key: read the log's `Done:` line, because until `1f4c9e2` a failed run showed green.

**The one real search:** search 86, "Light speed", six runs, 2 November 03:10 UTC: **61.3 s**, $0.2005,
against a before median of 145.2 s (n=4). Explanations at 35, 35, 46 s (published); questions at
49, 52, 61 s (review). Runs 92 to 97 ("Pulsars", 401, $0) came from ui's local server, on Vedant's
"start the api key and test"; ui has stopped those servers. latency's cause for the slow first
call is about 20 s of grammar compile after a long idle gap, from `strict: true`. It is inferred
from timing, not measured. No 429s. Decided: no warm-up now, keep `strict: true`; the daily Curator
should keep the schemas warm, so check that today's run covers both modes.

### The sessions

| Session | Branch head | State | Next |
| --- | --- | --- | --- |
| latency (fresh, tab titled "latency") | `455e77f` + 7 dirty files | **Editing the easy-first run order** | Main reviews it, then browser test with ui |
| ui | `1261fa7`, 4 ahead, clean | Done, idle, untested in a browser | Browser test on the stub, then land |
| data | `adabfde`, 7 ahead, clean | Steps d and e done, idle | Main reviews after the must-ship work |
| seo | `b02190a`, 14 ahead, 0 behind `fa23eda`, clean | Rebased, reads /quiz text from `src/quizAbout.ts`, approved by main, held for HTTPS | Land by this hash when HTTPS works. First check that Vercel's build has the bank values and Node 22.18 or newer, or the prerender makes only the 4 fixed pages or fails |
| media | `8d4ff76`, 51 behind, 2 dirty files (`curator/images.py`, `tests/test_images.py`) | **No report since 30 October** | Ask it for a report. Its dry run is in `docs/handoff/media.md` in its worktree |

The old latency session ("Latency session handoff setup") has stood down and may be closed. The
fresh one reports as "Latency session handoff for Curiosity".

**Reaching sessions:** names change and go stale. Use the `uds:\\.\pipe\LOCAL\cc-msg-...` address
in a session's latest message. On 2 November: latency `cc-msg-4526a580a51ab4275110bcc89f035fa5`,
ui `cc-msg-e97a950bf88ae55c644849f80ed4f689`, data `cc-msg-f3ae8a432344f4fbc97d34b118615cb9`, seo
`cc-msg-68ae3e0030fa580e622b279460c480c6`, media unknown (last named "Media session handoff
setup"). They hold main's old address, so a new main must send each its address. A session that
looks stuck may simply not have received messages: the old latency got its batch days late.
Update at 03:55: the main restarted at 03:50 sent latency, ui, data and seo its address; ui and seo
replied. Media could not be reached: its old name is gone and no address is known. The previous
main (`cosmic-quiz-agent-20`) has stood down, and its window may be closed.

### Decided by Vedant on 2 November (grill-me, sent to the sessions)

- **Run order (latency):** the easy question alone first, then the other live items together. If
  easy is from the bank, all start together. Easy failed at $0: start nothing else, settle the
  others as failed, `unavailable: true`. Easy billed with no item: start the others. Reservations
  and dollar caps do not change. Estimates, not measured: easy at about 25 s warm or 40 s cold,
  whole search about 75 to 85 s.
- **Progress (ui):** 3 bars for the questions only, one word each (Waiting, Researching, Ready,
  Left out), and "Explanations: n of m ready". No stage labels, status line or countdown.
- **Layout (ui):** the question on top, progress under it, agent log and Mission Control link
  behind "Show details". Main's defaults, not overruled: a finished panel shrinks to one line, and
  the page text says "a minute or two".
- **Waiting (ui):** the answered card stays; Next is disabled with "Medium question on the way".
- **Web results card (ui):** score, Correct and Incorrect tiles, like Google's quiz. No "Explain my
  results" (paid) and no weak-topic quiz for launch.
- **Google goal (seo):** Vedant wants to show for "astronomy quiz" and in AI Overview. He has been
  told Google decides, there is no special markup, and a new subdomain will not rank by launch.
- **Title:** "Astronomy Quiz: Test Your Space Knowledge - Curiosity" (`a6fa07e`).
- **Prerender build change:** approved by Vedant directly to main.
- **Fill:** the 30 topics in `FILL_TOPICS`, $5.00 cap, eval overlap kept. Vedant reviews about 65 to
  85 items before 3 November. Run only after: Console at $32, one cheap key test from the `.env` it
  uses, and main's word.
- **Failed searches:** a whole search that failed at $0 does not count (013, live).

### What main does next, in order

Update at 04:15: steps 1 and 2 are done. latency `7b00bf3` and ui `1261fa7` are approved: merged in
a scratch worktree, pytest, ruff, mypy, typecheck, vitest (249) and build pass, and the stub drive
passed at 1280 and 390 px, including a failed easy (one start, six settled at $0), caps and a
bank-only search. A live easy with the bank holding the others is covered by tests only, because no
bank topic is partly filled. Step 3 waits for Vedant's word. Accepted risk to confirm with him: two
batches could pass 300 s, leaving runs unsettled; the longest stored run is 61.8 s.

1. When latency commits: review the run order (`agent/ondemand.py`) and its tests.
2. Build ui and latency together in a scratch worktree (`git worktree add --detach`). Drive it on
   the free stub. Check: easy runs alone and shows first; the bars move; Next waits; the results
   card; "Show details"; ui's three notes (a bank-only search has no panel, the page does not move
   after the last question, the "Another new topic" fallback). Remove the worktree with
   `cmd /c rmdir /s /q`, then `git worktree prune`: `git worktree remove` leaves `node_modules`.
3. Land by reviewed hash, run every check, then push on Vedant's standing word for the must-ship
   work. Say what is going before pushing.
4. Ask Vedant for one real search. Send latency the word to measure it.
5. Tell ui and seo to rebase. seo then reads its /quiz text from `src/quizAbout.ts`.
6. Ask media for a report. Review data's d and e. Accounts stay off for launch unless Vedant
   finishes the setup (main recommended off); his answer is open.
7. When DNS and HTTPS work: land seo (steps 2 and 3, CSP, /media rewrite). The /media rewrite ships
   with it, so the image fill depends on DNS too. Then ui's NotFoundPage hook.

Scratch scripts, if still on disk, in
`C:\Users\vedan\AppData\Local\Temp\claude\c--Users-vedan-cosmic-quiz-agent\5a621cff-85ec-4608-a3df-a578337e6f58\scratchpad\`:
`stub_api.py` (the free API on 8790: run with the main folder as the working directory),
`serve_stub.py <dist> 4180 8790` (dist plus a streaming proxy), `progress.mjs` (needs new selectors
for the bars), `serve_cards.py` (sample images and facts), `grid.mjs`. Chrome: `--headless=new
--remote-debugging-port=9333` with a scratch `--user-data-dir`. Never use 8787 for this, and never
stop a server you did not start.

### Waiting on Vedant

1. **DNS and HTTPS for `curiosity.`** and the seven aliases, each added to Vercel. Still NXDOMAIN
   at 03:47 UTC. Blocks all of seo, the Google goal and the images. Vedant will do this with the
   next main session: walk through it with him early, using `docs/handoff/seo.md` and the memory
   file dns-and-vercel-cli-from-this-pc, and check the result over DoH before landing seo.
2. A screenshot of 013's check.
3. Console limit to $32, and check the rate-limit tier.
4. Accounts on or off for launch. If on: paste 011, then the setup in `docs/handoff/data.md`.
5. Paste 012, read media's dry run, then set the repository variable `TOPIC_IMAGES=on`. Not set.
6. `public/og-v2.jpg`: the current preview image still says COSMIC QUIZ.
7. `VERCEL_DEPLOY_HOOK_URL` secret: not set; harmless, the workflow skips it.
8. Approve or change latency's `CLAUDE.md` and `docs/DESIGN.md` drafts ($32).
9. After DNS: Search Console, sitemap, Bing, links in (order in `docs/handoff/seo.md`).

Open questions: signed-in limits check both account and IP (recommended yes); account retention
(recommended until deleted, purge after 24 months idle); per-topic previews by Pillow (recommended).

**Cut order if late:** (1) accounts, (2) prerendering, (3) image cards.

### Check first

```bash
git status --short; git fetch -q origin; git log --oneline -1 origin/main
for b in latency ui data seo media; do echo "$b $(git rev-parse --short session/$b) ahead $(git rev-list --count origin/main..session/$b) behind $(git rev-list --count session/$b..origin/main) dirty $(git -C /c/Users/vedan/cqa-$b status --porcelain | grep -v '^??' | wc -l)"; done
curl -s -H 'accept: application/dns-json' "https://dns.google/resolve?name=curiosity.vedantgaikwad.ie&type=A"
gh run list --workflow curator.yml --limit 2
```

DNS: always use DoH, because the VPN answers all DNS here. `Status` 3 means no such name.

### Lessons from this run

- Land by reviewed hash. Cherry-pick with `-x` when a branch is behind, so its later rebase drops
  the copies. Run the Python checks as well as pnpm: ui's header broke a packaging test unseen.
- A session's "Vedant approved it" is not Vedant's approval. Ask him directly.
- Look at screenshots of every state: the run bar's missing labels only showed at 1280 px.
- Keep facts to what the source page says. ui reopened each page for the rover ranks.
- Separate what is measured from what is estimated when reporting to Vedant.

## How Vedant wants main to work

- Main is the prompt engineer and reviewer. It edits no code; specialist sessions write it.
- When Vedant is listing changes, wait for the whole list before asking anything. Then ask one
  question at a time, each with a recommendation first and honest pushback grounded in the code.
  He wants better suggestions, not agreement.
- Commit only when he asks; stage by path; never push without his word.
- The repo is public: commits are authored "vedant gaikwad <vedantgaikwad01@gmail.com>", matching
  the history.

## Current goal

The pre-launch overhaul, settled in a grill-me session on 2026-10-30. The site becomes
**Curiosity** at `curiosity.vedantgaikwad.ie`, with optional accounts, parallel search with
progress rows, image topic cards, a sticky header with card buttons, prerendered SEO pages,
typo redirects and rover ranks. Everything ships before the launch on Tuesday 3 November.

- **Code freeze: Monday 2 November 18:00 Dublin**, then the deploy and a live check that evening.
- **Cut order if late:** (1) accounts, (2) prerendering, (3) image cards.
- **Must ship:** November's budget, parallel search, the rename and metadata, the header and card
  buttons.
- **Open until Monday:** the title tag. Vedant's direction is "Curiosity: Quiz on the wonders of
  our world beyond earth", or something better; candidates are in `docs/handoff/seo.md`. It is one
  line in `src/brand.ts`.

## Where things stand (2026-10-30, 17:30)

The Windows plan of 2026-10-29 (sessions backend, product, frontend; commit `aee722b`) was never
pushed and was scrapped by Vedant: its worktrees and branches are deleted. The five worktrees
were made fresh on Windows from `200185a` (`C:\Users\vedan\cqa-<name>`, Python 3.12 venvs made
with `py -3.12`, since plain `python` is 3.14 here). The status board for Vedant is the
"Curiosity Launch Board" artifact on claude.ai (sessions, his checklist, gates, decisions).

Decided today, beyond the 22 grill-me decisions:
- November's Anthropic Console limit is **$32** (Vedant): $20 live research, about $5 for the
  daily Curator, $5 for the 30-topic fill, $2 spare. The fill counts against the Console only.
- Main approved for latency (Vedant left it to main): small edits to `agent/stats.py`,
  `agent/config.py` (the Console limit by date), `agent/verifiers/__init__.py` (thread names),
  `.github/workflows/curator.yml` (one env line, not yet made) and `docs/DEVELOPMENT.md`.
- seo may edit two tests in `tests/test_packaging.py` and add the brand plugin to
  `vite.config.ts`. Lint is not a check (CI runs none).
- Main lands a branch by its reviewed commit hash, never by branch name.

On `main` (not pushed; every CI check passes at `85084fa`):
- latency: November's budget, Mission Control's caps by date, the 429 log (up to `a8c5947`).
- seo step 1: `src/brand.ts` and the name pass; README links kept on `cosmic.` until DNS.
- data: migration 011 as a file (not run) and its decisions; ui: its handoff. Copied with
  `git cherry-pick -x`, so each session's `git rebase main` drops them by itself.

Reviewed and approved, held off `main`:
- **latency, parallel search** (`537f4ed`..`cda56a5`): lands only after Vedant pastes 010, the
  check script says CHECK PASSED, and 2 real local searches pass. Before 010 every live search
  fails. The headless drive passed (first question 3.3 s, search 6.4 s on the stub).
- **seo step 2** (`86b984e`, `bdbb48f`): metadata, icons, 8 redirects, close-match 404. Its
  canonical URL, preview image and redirects point at `curiosity.`, so it lands only when
  `curiosity.vedantgaikwad.ie` loads over HTTPS.

Not reviewed:
- **media** sent no report. Its worktree has uncommitted edits to files it does not own
  (`agent/bank.py`, `src/types.ts`: latency's; `requirements-dev.txt`: ask first). It was told
  to stop and report why; nothing of it is on `main`.

Open for Vedant: push `main` by Saturday (November's budget); paste 010 and its check; A or B
for the Learn card (main recommends B); approve latency's `CLAUDE.md` and `docs/DESIGN.md`
drafts ($32); DNS for `curiosity.`; the setup checklist on the board.

## Where things stand (2026-10-30, 02:00)

- **On `main`, not pushed yet** (pushed only if Vedant says so before leaving the Mac):
  - `659ae30` Brief five parallel sessions for the pre-launch overhaul
  - `c69bac2` Record the rename to Curiosity and optional accounts (`CLAUDE.md`, `docs/DESIGN.md`,
    Vedant's approved text)
  - the commit with this file
- **No code has been written** for the overhaul. No session has started work.
- **The Mac** has worktrees `~/cqa-{latency,data,ui,seo,media}` on `session/<name>` at `c69bac2`,
  each with a Python 3.12 `.venv` and `node_modules`, and an empty `.env` (template only). They
  are Mac-only and hold no work; leave them, or remove them later with
  `git worktree remove ~/cqa-<name>` and `git branch -d session/<name>`. Any Claude sessions still
  running in the Mac's main folder should be quit.

## Continuing on Windows

1. **Get `main`.** In `C:\Users\vedan\cosmic-quiz-agent`: `git pull --ff-only`. If the Mac's
   commits were not pushed, push them from the Mac first; otherwise the briefs are not on Windows.
2. **latency already has a worktree** on Windows (`C:\Users\vedan\cqa-latency`, branch
   `session/latency`, from 2026-10-28, its work already on `main`). Do not run the script for it.
   In that folder: `git status` (it must be clean), then `git rebase main`. Its handoff then
   includes the new section.
3. **The other four**, from the main folder in PowerShell:
   ```powershell
   foreach ($n in "data","ui","seo","media") { dev\new-session.ps1 $n }
   ```
   The script copies the Windows `.env` (with the keys) into each worktree. Then in each folder:
   `python -m venv .venv`, `.venv\Scripts\activate`, `pip install -r requirements-dev.txt`,
   `pnpm install`. Node must be 20.19 or newer, or 22.12 or newer (Vite 8); `node --version` to check.
4. **Start the sessions**, each in its own terminal inside its worktree: `claude`, then `/model`
   (table below), then this first message with the name filled in:
   > Read CLAUDE.md, docs/SESSIONS.md and docs/handoff/<name>.md, then docs/DESIGN.md and
   > docs/PLAN.md. You are the "<name>" session, in the worktree ../cqa-<name> on branch
   > session/<name>. Your brief is in your handoff. Follow "Parallel sessions" in CLAUDE.md and
   > edit only the files your session owns. Tell me your plan before changing code.
5. **Start seo first.** Its `src/brand.ts` pass (the name in one place) merges before ui edits
   the same files. Until then, ui builds only its two throwaway card prototypes.

### Models (set with `/model` in each session)

| Session | Model | Why |
| --- | --- | --- |
| main (review) | Opus 5.5, high effort | Review needs the most judgement about how things break |
| latency | Opus 5.5, high effort | Threads, the cost guard and a live migration on the critical path |
| data | Opus 5.5, high effort | Auth, RLS and GDPR deletion: security mistakes are costly |
| seo | Sonnet 5.5 (Opus 5.5 for the prerender step if it struggles) | Mostly well-specified metadata and config |
| ui | Sonnet 5.5 | Well-specified frontend work in many files |
| media | Sonnet 5.5 | A bounded pipeline with clear rules and tests |

Opus uses up a plan's limits faster; if a limit is hit, latency and data keep Opus first.

## Timeline

- **Fri 30 Oct:** sessions start (Windows). seo begins with `src/brand.ts`.
- **Sat 31 Oct:** seo's brand pass merges first; ui rebases onto it. latency ships November's
  budget (deployed by Saturday), then parallel search. data: migration 011 and auth. ui: header,
  card buttons, two card prototypes for Vedant to pick from. media: the image pipeline and 012.
  seo: metadata, robots.txt, redirects, the 404 close-match.
- **Sun 1 Nov:** parallel search go/no-go. The fills run on November's budget (30 likely topics,
  about $5; images, free). ui: progress rows, the chosen card, rover ranks. seo: prerendering.
  latency: per-account limits once data's auth is on `main`.
- **Mon 2 Nov:** Vedant picks the title tag. Merges in review order: latency, seo, media, ui,
  data. Freeze at 18:00. Deploy, DNS switch, live check.

## Review protocol

1. A session tells Vedant a piece is ready: rebased onto `main`, every check green, its handoff
   updated.
2. Vedant asks main to review. Main reads `git diff main...session/<name>` and the handoff, and
   checks the piece against its brief, the hard rules in `CLAUDE.md` and the ownership table.
   Findings go back through Vedant as a numbered list; nothing merges with an open finding.
3. Vedant lands it from the main folder: `git merge --ff-only session/<name>`. Every other session
   then rebases onto `main`.

## Vedant's setup tasks (all free; each brief's "Needs from Vedant" has the detail)

- [ ] Google Cloud OAuth client (web), with Supabase's callback as the redirect URL (data).
- [ ] Supabase: enable Google and email providers; custom SMTP with Resend; site URL
      `https://curiosity.vedantgaikwad.ie` and redirect URLs for localhost and previews (data).
- [ ] Resend account, with SPF and DKIM records on vedantgaikwad.ie (data).
- [ ] DNS CNAMEs for `curiosity.` and the aliases `quiz.`, `astro.`, `cosmik.`, `curiousity.`,
      `curiosty.`, `cosmicquiz.`, each added to the Vercel project; `cosmic.` stays and redirects (seo).
- [ ] A Vercel deploy hook, saved as the GitHub Actions secret `VERCEL_DEPLOY_HOOK_URL` (latency).
- [ ] `public/og-v2.jpg`, 1200 x 630, CURIOSITY over one of the scenes (seo).
- [ ] Approve new dependencies when asked: `@supabase/supabase-js` (data), Pillow for the Curator
      only (media), any prerender dev dependency (seo).
- [ ] Paste migrations 010, 011, 012 in that order when each is ready.
- [ ] Check the Anthropic rate-limit tier before the go/no-go; raise the Console limit to $27
      before 3 November and back to $10 on 1 December (already planned).
- [ ] The title tag, on Monday.
- [ ] After launch: Google Search Console and Bing Webmaster Tools; submit the sitemap.

## Verification for the whole overhaul

- Each branch: every check in `.github/workflows/checks.yml` (`pnpm lint typecheck test build`,
  `ruff`, `mypy --strict`, `pytest`) plus its brief's own tests.
- A headless drive against the stub API (one session at a time runs the dev servers on 5173
  and 8787).
- 2 real local searches (about $0.17 each, asked for one by one): 25 to 40 s for the whole
  search, the first question in about 17 s.
- Accounts: the two-browser merge, RLS refusing another user's rows, delete removing everything,
  and the site unchanged with the flag off.
- Live: `curl -I` on `cosmic.` and each alias returns 301 to `curiosity.`; `curl` on
  `/learn/antimatter` shows its text, title and JSON-LD; Rich Results Test passes; no CSP
  violations; a pasted link shows the right preview.

## Edits applied to Vedant's files (2026-10-30, `c69bac2`)

Approved by Vedant. `CLAUDE.md`: the name Curiosity, the new domain, optional sign-in under v1,
the free tiers for Resend, Supabase Auth and Storage under hard rule 1, and session tokens and
RLS under hard rule 5. `docs/DESIGN.md`: the rename and domain in Context and Repo layout,
decision 15 (the overhaul), and "Player state" changed to optional accounts.

## Done

- 2026-10-30: the grill-me session (22 decisions); the five briefs; `docs/SESSIONS.md` rows,
  ownership and decisions; the approved `CLAUDE.md` and `docs/DESIGN.md` edits. On the Mac only:
  Node 22.23.4 in `~/.local/share/node22`, Python 3.12 through uv, the five worktrees.

## Next

- Vedant: the "Open for Vedant" list in "Where things stand (2026-10-30, 17:30)".
- main: read media's report and decide with Vedant who commits its edits; land latency's
  parallel search after 010 and the real searches; land seo step 2 after DNS.
- Each session, on restart: `git rebase main` first. ui waits for Vedant's card pick.

## Blockers

- None for starting. Setup tasks above gate data (OAuth, Resend), seo (DNS, og-v2.jpg) and
  latency's deploy hook.

## Files touched

- `docs/handoff/main.md` (this file), `docs/handoff/data.md`, `docs/handoff/ui.md`,
  `docs/handoff/seo.md`, `docs/handoff/media.md`, the last section of `docs/handoff/latency.md`,
  `docs/SESSIONS.md`, `CLAUDE.md`, `docs/DESIGN.md`.
