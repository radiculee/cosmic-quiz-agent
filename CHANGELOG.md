# Changelog

What changed on the live site and in the repo since the README was rewritten for the public
release. Everything before that, session by session with its decisions, checks and costs, is in
[`docs/PLAN.md`](docs/PLAN.md).

## 2026-11-04

- **A "Being checked" label on items no person has read yet.** On 2026-11-04, a review queue was
  cleared in bulk, not read one by one, and 60 of those items are published. Until an audit clears them, a Learn card or quiz
  question for one of those items shows a small "Being checked" tag beside its mode and level. It needs
  migration 014 (`items.being_checked`), which Vedant pastes before this code goes live.
- **One focus on each landing page.** Above a page's main action there is now only its title and
  one short line; status and small print sit below the action, unless they explain why it is off.
  Home's cards are Quiz (the one solid teal card), Learn and Web, and show a status only once there
  is progress. On the Web page the topic box sits above GO, and returns to the sticky header while a
  search is on the page. (`c37761d`)
- **Seven published items corrected.** An audit of published items with failed or doubtful checks
  found seven sentences that were false or overstated: items 97, 100, 116, 154, 165, 309 and 361.
  They were corrected in the bank. Items 156 and 61 went back to review, because their marked answers
  have no real support in the cited pages, so The International Space Station and The life cycle of
  a Sun-like star are off Learn and Quiz until those levels are decided. Most of the bank has not
  had this audit yet.
- **A contradicted sentence always goes to review.** A sentence Jev labels `contradicts` used to
  pass and publish if its probability was under 0.5. It now goes to review at any probability, and
  still fails at the threshold of 0.8. This applies to new items. (`949af7c`)
- **A leading "The" no longer makes a second topic.** Typing a topic with or without a leading "The"
  finds the same bank topic, so it does not pay for a second one. The Curator's news pick follows
  the same rule. Stored and shown names are unchanged. (`d23815b`, `d6efcaf`, `cf665df`)
- **Unknown addresses answer 404.** An address that is no page now answers HTTP 404 with the site's
  not-found page (`noindex`, no canonical link). A topic address still answers 200, because a new
  topic has no built page until the next deploy, so an unknown topic is still a soft 404.
  (`d022577`, `d819d62`)
- **Fact cards are stricter.** The fact-picking rule rejects a sentence that needs the sentence
  before it, and gives no fact when none stands alone. On the 56 topics it was tuned on, one reader
  marked 55 results good, up from 33. No fact card is live today. (`c907993`, `876ed54`)
- **Every topic has a picture.** The bank holds 56 picture rows, one for each topic, and 28 of them
  are hand-chosen and locked, so a refresh never replaces them. The daily Curator run now fills a
  picture for each new topic, in a step that runs only while the repository variable `TOPIC_IMAGES`
  is `on` (it was set on 4 November, 00:51 UTC). Learn lists a topic only when it is on every
  level, so 37 topics show today and the others, with pictures already saved, appear later.
  (`6b5078e`, `57771af`)

## 2026-11-03

- **Curiosity is live** on `curiosity.vedantgaikwad.ie`. `cosmic.vedantgaikwad.ie`, six typo and
  old subdomains and the `cosmic-quiz-agent.vercel.app` address answer a permanent redirect (308)
  that keeps the path (`vercel.json`). The site has the new title, icons, web manifest and link
  preview, and the not-found page suggests close matches. (`d073f3e`, `1d7f05c`, `c23560f`)
- **Pages are prerendered.** The home, Learn, each topic, Quiz and web pages are built as HTML at
  build time, so they have real text before any script runs; the Quiz page has its own text and
  only structured data that its content supports. The daily Curator workflow has a step
  that calls a Vercel deploy hook after a run that published anything, to rebuild them, but it
  needs the secret `VERCEL_DEPLOY_HOOK_URL`. That secret is not set yet, so the step skips, and a
  new topic gets its page at the next deploy. (`37d919f`, `0b1ca22`, `4624aae`)
- **The README rewritten again** for the site as it is at launch: new screenshots, a real
  launch-day search in place of the stub picture, and the measured searches below. (`10d9ff7`,
  `18b91e9`, `bd2ee17`, `77133fe`)
- **Square topic cards.** Each Learn card is cut directly from the source to a centred
  320 x 320 WebP, never enlarged (the shorter side must be at least 320 px), instead of being
  cropped from a wide image. The link preview is still cut from the source. (`319e2ba`,
  `4ae4b43`)
- **Learn card fixes.** A card shows a topic's whole fact and no longer cuts it mid-word. Links,
  title, WEB tag and alt text were tidied, and a picture's credit names its licence once.
  (`d390f66`, `56e3ffd`, `74ec338`)
- **The easy-first order, measured.** Two searches since the change, each a single
  search (n=1). Search 104, on 2 November: the first question took 21.6 s, the whole search
  97.0 s and cost $0.1561. Search 115, on 3 November: the first question took 41.2 s, the whole search 76.5 s and
  cost $0.1511, with 5 of 6 items published. The two are the same subject under two names, "The Cosmic
  Microwave Background" (search 104, topic 377) and "Cosmic Microwave Background" (search 115,
  topic 397); search 115 was paid only because the names did not match. The 61.3 s search of
  2 November, "Light speed" (first question at 49 s), was also a single search, with every item
  started together. Three searches are too few to show a trend.

## 2026-11-02

- **The EASY question goes first.** A search now makes the EASY question alone, and starts its other
  items when it ends. With that question already in the bank, every live item starts together. If the
  first run fails with nothing spent, the model is out of reach, so the others never start and the
  search does not count. Reservations and caps are unchanged. Expect a new topic to take up to about
  90 s; measured on 2 and 3 November (see above).
- **Every item at once, measured.** Before the change above, this was the time with every item
  started together. A new topic's six items used to run one after another:
  a median of 145.2 s (118.9 to 171.6 s, 4 searches, 2026-10-28 to 2026-10-30, last run finished
  less first run started). The first search to succeed since the change took 61.3 s, with its first
  item at 35 s and its first question at 49 s. That is one search (n=1), "Light speed", not a median.
  About 20 s of it looks like a one-time cost, not the search itself: the first model call after more
  than a day without a run took about 20 s, once for each kind of item, which fits the API compiling
  the strict tool schemas again. Without those first calls this search would have taken about 41 s,
  but no search has yet been measured that way.

## 2026-11-01

- **A search the model never answered is free.** A search counts against the daily limits unless
  every run of it failed with nothing spent, as a refused key or an outage leaves it. The dollar caps
  are unchanged. The page says the agent is unavailable, and each run says it could not reach the
  model. (Migration 013, `55fc118`, `e2ed90f`, `6a4c6eb`)
- **A daily run that never reached the model fails.** When every job of the daily Curator ended with
  no item and nothing spent, the workflow now goes red. A refused key had left that day's run green.
  (`c55ba49`)

## 2026-10-30

- **November's budget for the launch.** Live research gets $20 for the calendar month of
  November 2026 (usually $4), so the launch cannot use up the month in its first days. The launch
  week (the UTC days 3 to 9 November) now allows 14 searches and $3.25 a day for everyone (was 20
  and $2.50), still 5 a visitor: at about $0.17 a six-item search, the whole week at full use
  costs about $17. Both windows are dated in code (`limits_at` in `agent/limits.py`), so the usual
  limits come back after 9 November, and the $4 month on 1 December, with no deploy. The
  Anthropic Console limit is $32 for November ($20 here, about $5 for the daily Curator, $5 to
  fill the bank with 30 likely topics, $2 spare) and goes back to $10 on 1 December. Mission
  Control shows the caps in force, so November shows $20 for live research and $32 for the
  Anthropic limit. Also from the launch code review: a refusal message can no longer fail on a
  stray brace.

## 2026-10-28

- **Every topic at every level.** Learn and Quiz now list a topic only once it has an
  explanation and a question at easy, medium and hard, so each level offers the same topics.
  The new `python -m curator complete` fills the gaps, and the daily run fills up to six a day.
  Seven visitor-typed topic names were tidied, and "Bang" merged into "The Big Bang".
  (`f1934b0`, `1036a3f`)
- **Explore researches every level.** The difficulty control is gone: a search makes a question
  and an explanation at each level, and after the questions the explanations open in EASY,
  MEDIUM and HARD tabs. Whatever a search's time limit leaves out, the agent writes overnight.
  (`27fa151`)
- **Surprise me.** A button on Explore asks the agent to pick a topic the bank does not have yet,
  then researches it. It uses one search, and a pick that fails counts nothing. (`27fa151`)
- **The bank filled for every level.** Two Curator runs and a re-check of the items the Jev
  outage had held, each item in doubt read against its sources: 37 of the 44 topics now have an
  explanation and a question at every level; 7 stay off Learn and Quiz until their last slot is
  filled.

## 2026-10-21

- **Launch week for the LinkedIn post.** For the UTC days 3 to 9 November 2026, each visitor
  gets 5 live searches a day (usually 2), and everyone together 20 searches and $2.50 a day
  (usually 4 and $0.50). The $4 monthly cap on live research is unchanged, so the launch never
  spends more than a usual month. The dates are in code (`limits_at` in `agent/limits.py`), so
  the window opens and closes by itself, with no deploy. (`3765728`)
- **Review queue cleared.** The 9 items the publish gate was unsure about were judged against
  their sources: 5 published, 4 discarded (one had two right answers, one a false claim in its
  explanation, one presented unconfirmed galaxy candidates as confirmed, one a "wrong" option
  that is a real mechanism). The bank holds 190 published items. (`0cbcf4f`)

## 2026-10-19

- **Version 1 complete, and the repo public** under the MIT licence, after one more secret scan
  of the whole history (clean). Secret scanning with push protection and Dependabot alerts are
  on. (`b6f60cd`)
- **The header's GitHub icon** links to the repo instead of the author's profile. (`3389a49`)
- **Local Python updated** to 3.12.10 and the virtualenv rebuilt (security audit finding S16).
  (`5dffe9f`)

## 2026-10-17

- **Difficulty is a dropdown** on Learn, each topic, Quiz and Explore, built on the browser's
  own select, so a phone shows its native picker. The Learn bar is one row at every width
  (74 px tall on a phone, was 130 px). (`1304f0c`)
- **No more zoom on iPhone forms.** A test now fails if any text field is under 16 px, which
  makes iOS zoom in; it caught the Report box, now 16 px. (`1304f0c`)

## 2026-10-13

- **"Analytics for nerds" is now "Mission Control"**, everywhere on the site. (`024f0fe`)
- **The README rewritten** for recruiters first, then engineers, with three screenshots of the
  live site and every number checked against its source; setup and the repo map moved to
  [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md). (`52b98d2`)
- **Checks on every push and pull request** in GitHub Actions: the Python tests, lint, format
  and types, and the site's typecheck, tests and build, with no secrets and no paid calls.
  pnpm is pinned to 11.5.0 for CI and Vercel alike. (`4883f3c`)
