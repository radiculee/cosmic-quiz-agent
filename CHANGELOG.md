# Changelog

What changed on the live site and in the repo since the README was rewritten for the public
release. Everything before that, session by session with its decisions, checks and costs, is in
[`docs/PLAN.md`](docs/PLAN.md).

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
