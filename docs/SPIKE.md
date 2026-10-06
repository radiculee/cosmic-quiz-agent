# Spike results

## Session 1 - Claude tool-calling spike (2026-10-01)

**Question:** does the search -> fetch -> cite loop work on Claude Haiku 4.5, and what does one run
really cost?

**Answer:** yes. 3 of 3 runs passed the code-enforced citation check, at an average of **$0.019 per
LEARN run**, well under the $0.05 to $0.10 estimate in `PLAN.md`. Quote accuracy is the weak spot,
and one explanation contained a factual error the citation check cannot catch. Both point to the
verifier planned for Session 3.

### Setup
- Model: `claude-haiku-4-5`, no extended thinking, `max_tokens` 4096, strict tool schemas,
  automatic prompt caching (`cache_control` on every request).
- Tools: `search_wikipedia`, `fetch_page` (allow-list: wikipedia.org, nasa.gov, esa.int; pages
  trimmed to 12,000 characters, about 3,000 tokens) and `submit_answer`.
- Budgets: 12 model calls, 120 s, 200,000 input tokens per run. None were reached.
- Command: `python -m agent learn "<topic>" --difficulty easy|medium|hard`. Full logs are in
  `runs/` (gitignored).

### Results

| Topic | Difficulty | Outcome | Model calls | Pages fetched | Citations kept / dropped | Quotes verbatim | Time | Cost |
|---|---|---|---|---|---|---|---|---|
| Neutron stars | easy | passed | 3 | 1 | 5 / 0 | 5 of 5 | 31.2 s | $0.0130 |
| Why the sky on Mars is red | medium | passed | 5 | 3 | 4 / 0 | 3 of 4 | 15.8 s | $0.0231 |
| Cosmic microwave background | hard | passed | 5 | 2 | 4 / 0 | 3 of 4 | 15.0 s | $0.0209 |
| **Total** | | **3 / 3** | | | **13 / 0** | **11 of 13** | | **$0.0570** |

Tokens per run (input at full price / cache write / cache read / output):

| Topic | Input | Cache write | Cache read | Output |
|---|---|---|---|---|
| Neutron stars | 2,957 | 4,598 | 0 | 851 |
| Mars sky | 3,398 | 10,328 | 16,916 | 1,028 |
| CMB | 3,454 | 8,527 | 10,398 | 1,148 |

Prices used: $1.00 / MTok input, $1.25 cache write (5-minute TTL), $0.10 cache read, $5.00 output.
**To check against the Console:** these three runs should show about $0.057 of usage on the
`local-dev` key.

### Prompt caching
- The system prompt plus tool definitions is about 1,250 tokens, below Haiku 4.5's 4,096-token
  minimum, so the first one or two calls of every run are never cached.
- Once a fetched page is in the history, the prefix passes 4,096 tokens and caching starts: each
  later call writes the new part and reads the rest.
- Measured effect, compared with the same tokens at the uncached price:

  | Topic | Without caching | Actual | Change |
  |---|---|---|---|
  | Neutron stars (3 calls) | $0.0118 | $0.0130 | +10%: the cache was written on the last call and never read |
  | Mars sky (5 calls) | $0.0358 | $0.0231 | -35% |
  | CMB (5 calls) | $0.0281 | $0.0209 | -26% |

- **Conclusion:** keep automatic caching on. It saves 25 to 35% on runs of four or more calls, and
  the loss on short runs is a fraction of a cent. The Curator, which researches once and then
  drafts and verifies several items in the same conversation, should benefit more.

### Quality findings
1. **Two quotes were not real quotes.** On the Mars run, the model "quoted" a sentence that does
   not appear in the page text it was given (a paraphrase presented as a quote). On the CMB run, it
   joined two separate passages into one quote. The URLs were genuine, so the citation check kept
   both. The verbatim-quote count is measured in `agent/verify.py`; it should become a gate.
2. **One factual error.** The CMB explanation says fluctuations arose "as early as the first
   billionth of a billionth of a billionth of a second" (10^-27 s). The cited source says "the
   first nonillionth (10^-30) of a second". The URL and the quote were both valid, so only a
   verifier comparing claims to sources can catch this.
3. **Grounding was otherwise good.** Every cited URL was fetched (0 dropped), every run used
   Wikipedia search before fetching, and the medium and hard runs went looking for a second source
   on their own.
4. **Behaviour:** Haiku made parallel tool calls (two searches or two fetches at once) without
   being asked, and called `submit_answer` without needing a nudge. Strict tool schemas meant no
   invalid arguments in any run.
5. **Latency:** about 15 s per run. The first call of the first run took 19.7 s, which looks like a
   one-off cold start; every other call took 1 to 9 s.

### What this changes in later sessions
- **Session 2:** keep the loop as is. Consider asking for quotes on separate lines per citation
  and fewer, longer citations, to reduce stitched quotes.
- **Session 3:** make the verbatim-quote check a hard gate (drop a citation whose quote is not on
  the fetched page), and have the verifier check numbers and named claims against the quotes.
  This would have caught both quote problems and the 10^-27 error.
- **Session 4 (Curator volume):** at measured prices, a Curator topic (one research run, three
  quiz drafts and three verifier passes) is likely to cost $0.05 to $0.08, to be confirmed in
  Session 3. That allows over 100 topics a month within the $10 cap.
- **Eval cost (Session 3):** a 20-topic eval run is likely to cost $1 to $2, below the $2 to $3
  estimate.

### Jev second-opinion smoke test (2026-10-01)
TypeSafe Jev (`typesafe-sdk` 0.7.2, default `jev-latest`) answered one Choice question per claim:
does the source passage support, contradict or say nothing about the claim?

| Case | Expected | Jev verdict | Confidence | Time | Input tokens |
|---|---|---|---|---|---|
| Neutron star size, correct claim | supports | supports | 1.00 | 328 ms | 436 |
| Spin claim against an unrelated passage | says nothing | says nothing | 1.00 | 203 ms | 418 |
| CMB claim with the spike's 10^-27 vs 10^-30 error | contradicts | **supports** | 0.86 (0.09 contradicts) | 204 ms | 440 |

Cost for all three: about 1,300 input tokens, roughly $0.00006.

**Finding:** Jev is fast and confident on whether a passage addresses a claim, but it missed the
numeric error, as TypeSafe's docs warn ("cannot calculate reliably"). It works as a second opinion,
not as the only check. Session 3 adds a code check that every number in an answer appears in a
fetched page, and asks the writer to keep numbers in the form the source uses. At 0.86, this case
would also pass TypeSafe's suggested 0.8 auto-accept threshold, so the threshold alone would not
have caught it.


## Session 7 - Vercel deployment spike (2026-10-06)

Questions planned on 2026-10-01 for running the API on Vercel (Hobby, Fluid compute), answered
against the production deployment with a temporary streaming probe (`api/spike.py`, removed
afterwards) and two live runs. Cost: about $0.05 on Anthropic.

| Question | Result |
| --- | --- |
| Do WSGI `app` functions in `api/` stream? | Yes, line by line: a one-line-a-second stream arrived one line a second (chunked transfer). Live runs streamed every step as it happened. |
| What does the 300-second limit do to a stream? | Vercel closed it at exactly 300 s, after the line at 299 s, with no error: to the client it looks like a normal end. The UI already treats a stream that ends without a result as a fallback to the bank. Live runs take 20 to 45 s; the agent's own budget is 120 s. |
| If the player leaves mid-run, is the paid run still stored and settled? | Yes. A live run disconnected 1.3 s in, right after its reservation, was stored (run 190) and settled at its real cost ($0.025 of the $0.17 reserved) 16 s later. Closing the stream waits for the run, and Vercel keeps the invocation alive meanwhile, so `wait_until` is not needed. |
| Can a visitor choose the address their limits are counted against? | No. A request with forged `X-Forwarded-For` and `X-Real-IP` headers was seen from its real address: Vercel replaces the header, and the app takes its last entry. |
| Cold start | About 1 s for the first request after a deploy; `/api/topics` repeats come from the edge cache in about 0.04 s. |
| Region | Functions ran in `iad1` (Washington) while Supabase is in AWS eu-west-1 (Ireland; the database host's IPv6 address is in AWS's eu-west-1 range). `/api/item`, which makes two database calls, took a median 0.88 s. Moved to `dub1` (Dublin) in `vercel.json`. |

Deployment problems found and fixed:
- Every function failed with `No module named 'pydantic'`: when `pyproject.toml` has a
  `[project]` table, Vercel installs from it and ignores `requirements.txt`, and ours listed no
  dependencies. Both now list the same pins, checked by `tests/test_packaging.py`, and
  `.python-version` pins Python 3.12.
- Live research answered 503 because the Anthropic key was stored under another name
  (`ANTHROPIC_COSMIC_QUIZ_VERCEL_API_KEY`); the SDK and the configuration check read
  `ANTHROPIC_API_KEY`. Renamed in Vercel and redeployed (variables are read at deploy time).
