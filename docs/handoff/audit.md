# Handoff: audit

Read-only audit of published items whose stored checks failed or said contradicted. Last update:
2026-11-04. The bank was read twice, a few minutes apart, and both reads were identical.

**7 FALSE items are visible to players now: 97, 100, 116, 154, 165, 309 and 361.** Four come from the
stored-check list you asked for (100, 154, 165, 309). Three come from the wider reading (97, 116,
361). Most of the bank was not read, so the true count may be higher (see Left). No row was changed.

## Done

### The bank

| Measure | Count |
|---|---|
| Items, all statuses | 384 |
| Published | 309 |
| Visible to players (`status = 'published'` and `report_count < 2`, the RLS rule at `supabase/schema.sql:1340`) | 309; no published item has 2 reports |
| Published directly by the gate, no person | 177 |
| Left review through a stamped `reviewed_at` | 66 |
| Left review on 2026-10-02 with no stamp, decided by Vedant per `docs/PLAN.md:339` (includes 154) | 26 |
| Left review with no stamp and pass/pass verdicts, so through `rejev` with no person (inferred from `supabase/schema.sql:848`) | 40 |

- **How checks link to items:** `claim_checks.item_id` to `items.id`. `runs.record` keeps the
  original answer and the gate's first decision.
- **`reviewed_at` undercounts human review.** The 26 items above have verdicts that the gate would
  hold, and no stamp. Their `published_at` values span 13:28:17 to 13:29:55 on 2026-10-02.
- **Item 7:** its run record says `discarded`, but the item went to review and was published in that
  batch. The likely cause is the 2026-10-02 rule change in `agent/gate.py:34-37` (inference).
- **Only item 154 was edited after its checks.** I compared the explanation, question and correct
  option of every item with its run record.

### Findings: stored check says contradicted, or the gate treats it as doubt

The figure in brackets is Jev's contradicts probability, which is the value the gate uses. Pages
named "stored" are the text the agent read, from `cited_pages`.

| Item | Topic | Sentence | Verdict and confidence | Route to published | Class | Evidence | Suggested correction |
|---|---|---|---|---|---|---|---|
| 154 | The International Space Station | Stored: "The date 1 January 1998 refers to when the first ISS module was launched..." Still live: "The other dates relate to the Moon landings and lunar missions, which were entirely different space programs and took place decades earlier." | contradicts 0.67 (0.78) on the removed sentence; says_nothing 0.89 on the live one | Person, 2026-10-02 | STALE-CHECK for the stored check. **FALSE** for the live sentence | The removed sentence is not in the explanation. "The other dates" still covers the option 1 January 1998, which is not a lunar date. "The first ISS module was launched in 1998" (stored page). "launch of the Russian-built Zarya module atop a Proton rocket on 20 November 1998" (live page). https://en.wikipedia.org/wiki/International_Space_Station | "The other dates do not mark the start of crewed occupation: 20 July 1969 and 15 April 1972 fall in the Apollo era, and the first ISS module was not launched until November 1998." |
| 100 | Sagittarius A* | "For context, Earth orbits the Sun at 150 million kilometres, making Sagittarius A*'s accretion disk only slightly smaller than Earth's orbit." | contradicts 0.50 (0.67) | Bulk, 2026-10-03; approved at re-check, 2026-10-05 | **FALSE** | "a diameter of 51.8 million kilometres... Earth is 150 million kilometres... from the Sun" (stored). 51.8/150 is about 0.35. https://en.wikipedia.org/wiki/Sagittarius_A%2A | "For context, Earth is 150 million kilometres from the Sun, so this diameter is well under half of that distance and far smaller than Earth's orbit." |
| 165 | The Voyager probes | "The radioisotope thermoelectric generators may supply enough power to keep science instruments running until 2036." | contradicts 0.25 (0.50) | Bulk, 2026-10-03; approved at re-check, 2026-10-05 | **FALSE** | "may supply enough electric power to return engineering data until 2036. As of 2026, only two instruments are operational" (stored). https://en.wikipedia.org/wiki/Voyager_1 | "The radioisotope thermoelectric generators may supply enough electric power to return engineering data until 2036; as of 2026, only two of Voyager 1's instruments are operational." |
| 309 | Antimatter | "All the mass of both the particle and antiparticle transforms into pure energy, making antimatter extraordinarily powerful for energy release." Also: "they convert completely into energy" | contradicts 0.37 (0.58) | Person, 2026-10-28 | **FALSE** (an overstatement; low severity) | "neutrinos, and sometimes less-massive particle-antiparticle pairs. The majority of the total energy of annihilation emerges in the form of ionizing radiation." "usually proportional to the total mass" (stored). The item's own previous sentence names the lighter pairs. https://en.wikipedia.org/wiki/Antimatter | "when a particle and its antiparticle collide, they annihilate, releasing energy usually proportional to their total mass (E=mc²)." and "Most of that energy emerges as ionizing radiation, which makes annihilation an extraordinarily concentrated energy source." |
| 210 | Wormholes | "Bronnikov first demonstrated the theoretical possibility of traversable wormholes, but Thorne and Morris's work was independent and came later." | contradicts 0.46 (0.64) | Person, 2026-10-21 | JEV-WRONG | The splitter cut the sentence at "K. A. Bronnikov", so Jev saw a fragment without Ellis. "first demonstrated in a 1973 paper by Homer Ellis and independently in a 1973 paper by K. A. Bronnikov"; "independently discovered in 1988" (stored). https://en.wikipedia.org/wiki/Wormhole | None needed |
| 38 | Europa's hidden ocean | "The water layer encompasses all water in any form, from the solid ice shell at the surface down to the interface with the rocky mantle." | contradicts 0.11 (0.40) | Person, 2026-10-02 | JEV-WRONG for this sentence | "divided into the metallic core, rocky mantle and hydrosphere"; "the thickness of the outermost water layer is 120-170 km"; the ice shell and ocean vary inside the hydrosphere (stored). https://arxiv.org/abs/2403.01336 Two other sentences are UNCLEAR: "two or three times" is not on the page, and "kept from freezing by tidal heating" meets "the ocean can persist even in the absence of tidal heating" (at higher ice viscosity) | Optional: "...kept liquid in part by tidal heating..." |
| 25 | Auroras | Distractor: "Spontaneous light emission from nitrogen and oxygen molecules at high altitudes in low-pressure regions" | supports 0.54 (supports probability 0.70) | Person, 2026-10-02 | JEV-WRONG | "caused by charged particles from the Sun colliding with atoms"; "forbidden transitions of atomic oxygen" (atoms, not molecules). The stored page has no "spontaneous". https://en.wikipedia.org/wiki/Aurora | None needed |
| 198 | Antimatter | "These pairs would have opposite charges and properties, causing them to cancel each other out perfectly, leaving no net baryonic excess." | contradicts 0.37 (0.58) | Person, 2026-10-21 | UNCLEAR | "otherwise equal numbers of left-handed baryons and right-handed anti-baryons would be produced" (stored) supports the net zero. "Cancel each other out perfectly" and "opposite charges and properties" are not on the page. https://en.wikipedia.org/wiki/Baryogenesis | Optional: "Equal numbers of each would leave no net excess of baryons." |
| 186 | Olympus Mons | "Its enormous size is unique in the solar system because Mars lacks mobile tectonic plates." | contradicts 0.29 (0.52) | Person, 2026-10-21 | UNCLEAR | "is likely because Mars lacks mobile tectonic plates"; "approximately tied with Rheasilvia on Vesta as the tallest mountain"; the page also names prolonged activity, weaker gravity and less erosion (stored). "Unique" is not proven false. https://en.wikipedia.org/wiki/Olympus_Mons | Optional: "Its extraordinary size is likely because Mars lacks mobile tectonic plates." |
| 50 | Neptune and Triton | "The capture mechanism worked through extreme tidal forces." | contradicts 0.09 (0.40) | Bulk, 2026-10-03 | UNCLEAR | The stored page gives rival mechanisms. Gas drag is one. In three-body capture a binary "becomes unbound by tidal forces". The "extreme" tides it describes come "Following capture". Separately, the item says Triton will break apart, but the page gives "either a collision with Neptune's atmosphere or the breakup". https://en.wikipedia.org/wiki/Capture_of_Triton | Optional: "After capture, extreme tides reshaped its orbit." |
| 156 | The International Space Station | Marked answer: "A higher altitude would require much more fuel..." | says_nothing 0.94 (supports 0.01) | Person, 2026-10-02 | UNCLEAR | Neither cited page mentions fuel. Haiku's "supporting" quote only gives the orbit. The live page offers partial support: altitude was "allowed to fall around the time of each NASA Space Shuttle flight to permit heavier loads". The stem is also doubtful: the page puts the ISS "below" the belts, so going higher enters them. https://en.wikipedia.org/wiki/International_Space_Station | Recommend a rewrite or discard, because the answer has no cited support |
| 61 | The life cycle of a Sun-like star | Marked answer: "...radiation pressure to push the outer layers outward faster than gravity can pull them inward" | says_nothing 0.23 (supports 0.42) | Person, 2026-10-02 | UNCLEAR, with strong doubt | Haiku's quote concerns the core, not the envelope. "when the core within the shell contracts, the layers of the star outside the shell must expand. The detailed physical processes that cause this are complex." https://en.wikipedia.org/wiki/Red_giant No reference found says outright that radiation pressure is wrong | Recommend a rewrite: "The core contracts and heats, shell fusion increases, and the outer layers expand greatly and absorb most of the extra energy." |

### Findings: code-level citation failures, no false fact established

`CitationCheck.passed` is `len(self.kept) > 0` (`agent/schemas.py:91`), so a bad citation is dropped
and the item can still pass. Ten published items have one: 24, 97, 129, 151, 152, 165, 190, 196, 238
and 277.

- **Items 97, 129, 151, 152, 165, 190, 196 and 277:** I compared the dropped quote with the stored
  page. Each mismatch comes from characters: a lost degree sign, TeX markup, dash handling, pronunciation
  text, or a closing quotation mark and attribution.
- **Item 24:** the dropped quote was not compared, because this script found no stored page for its
  URL.
- **Item 238:** its only dropped citation was a URL not read in the run, and that was the only
  source for "tilted by 98 degrees" as a plane of the moons. The kept arXiv page gives 98 degrees for
  the planet's spin tilt only. Class UNCLEAR on support. I did not establish a false fact.

### Findings outside the stored-contradicted list

These came from reading Haiku's explanation problems and sentences where Jev's contradicts
probability was at least 0.3 under another label. The gate treats a Haiku problem as doubt.

| Item | Topic | Sentence | Stored signal | Route | Class | Evidence | Suggested correction |
|---|---|---|---|---|---|---|---|
| 97 | Sagittarius A* | "Sagittarius A* matters because it holds the Milky Way together." | Haiku problem naming this sentence; Jev pass | Bulk, 2026-10-03 | **FALSE** | The stored page has no such claim. Sgr A* has about 4 million solar masses and the galaxy "Mass 1.15 × 10^12". https://en.wikipedia.org/wiki/Milky_Way | "Sagittarius A* matters because the stars orbiting it let astronomers study a supermassive black hole directly." Then join to the next sentence. |
| 116 | Galaxy collisions | "earlier simulations had suggested a 50% probability of collision within 10 billion years, but new data revealed..." | Jev supports 0.41 (contradicts 0.38); Haiku pass | Gate, no person | **FALSE** | The 50% belongs to the 2025 study: "In 2025, Till Sawala... ran 100,000 simulations... These simulations showed that the chances of a head-on collision... is only 50% within the next 10 billion years." Earlier view: "By 2012... highly likely". https://en.wikipedia.org/wiki/Andromeda%E2%80%93Milky_Way_collision | "This is a dramatic downward revision: by 2012 a collision looked highly likely, but the 2025 simulations gave only a 50% chance within 10 billion years, and in half of the scenarios the galaxies fly past each other with roughly half a million light-years between them." |
| 361 | Skylab space station | Explanation: "23 days (the previous record that Skylab 4 surpassed)". Question: "How many days did the Skylab 4 crew extend the record...?" | Jev supports 0.31 on another sentence in the item; both layers pass | Gate, no person | **FALSE** | Skylab 3 "lasted 59 days, 11 hours and 9 minutes" before Skylab 4 (https://en.wikipedia.org/wiki/Skylab_3). So 84 is the new record, not the extension. The cited Skylab page words it loosely. | Question: "To how many days did the Skylab 4 crew extend the record for human time spent in orbit?" Explanation: "23 days (the earlier Soyuz 11 record, which the Skylab crews passed)". Also replace "a common point of confusion" with: "270 is the volume in cubic metres of Skylab's central workshop, not a number of days." |

### Numbers in the FALSE items (question, correct answer, distractors, explanation)

I ran `numbers_in` from `agent/verify.py` against each item's stored pages, and then read the values.
No paid call.

- **154:** all stated numbers are on the page, except the distractors' 1969, 15 and 1972, which are
  wrong options. 15 April 1972 matches no Apollo 16 event I checked: its launch was "April 16, 1972"
  (https://en.wikipedia.org/wiki/Apollo_16). My correction says only "the Apollo era".
- **100:** all are on the page, but one page figure looks wrong. 51.8 microarcseconds at 8,000 parsecs
  works out to about 62 million km by my arithmetic, not the page's 51.8 million km. Treat as UNCLEAR.
  My correction does not depend on it, but the item still repeats 51.8 million km.
- **165, 309 and 97:** every number is on the page.
- **116:** 2%, 4 to 5, 50%, 10, 12% and 110 are all on the page. 110 km/s is a speed offered as an
  option to a probability question: not false, but a weak distractor.
- **361:** 84, 23, 24 weeks and 270 are on the page. The fault is how they are read (above). 59 days
  is not on the cited page, so my correction leaves it out.

### Why such an item could be published

**Can a contradicted check pass without a human? Yes, below a contradicts probability of 0.5. Between
0.5 and 0.8 it needs a person. At 0.8 or above it is discarded.** The threshold is 0.8
(`agent/config.py:138`). From `agent/gate.py:79-83`:

```python
else:
    if contradicts >= threshold:
        fail.append(f"contradicted ({contradicts:.2f}) {label}")
    elif contradicts >= JEV_DOUBT:
        doubt.append(f"possibly contradicted ({contradicts:.2f}) {label}")
```

- **Test on the pure function, no model call:** a sentence labelled `contradicts` at probability 0.49
  gave `('pass', ())`; at 0.50 it gave `borderline`. With Haiku passing, `_combine` then returns
  `published`. On-demand runs use the same `verify_and_decide`.
- **In the bank, nothing has used that gap alone.** Items 38 and 50 have `contradicts` labels under
  0.5, but Haiku's doubts held both for a person. The other seven labelled items had Jev verdict
  borderline. Item 154's 0.78 sat just under the discard line.
- **Haiku's answer check is weak.** Items 156 and 61 record `supported` with quotes that do not
  contain the claim. The gate checks that a quote is on a page, not that it proves the answer.
- **A person can override anything in review.** `curator/review.py:136` calls
  `store.decide_review(item.id, decision)`, with no block on a contradicted sentence. The reviewer
  sees the Jev reason, but `_jev_lines` shows sentences only as a summary count.
- **The queue was cleared in bulk once.** `docs/PLAN.md`: "the 35 items held only by Haiku's
  explanation doubts were published, then the last 3 as well, to be cleaned up later." Items 97, 50,
  100 and 165 went through this clearing. I found no later clean-up of the 35 in the plan lines I
  read, and did not search the whole plan.
- **A re-check did not catch two.** `docs/PLAN.md` records items 100 and 165 as re-checked and
  approved on 2026-10-05. Both are FALSE here, and Haiku had named the fault in each.
- **Agent-assisted decisions also let doubtful text through.** Items 186, 198, 210 and 309 were
  decided on Claude Code's reading.
- **`rejev` publishes without a person, by design.** `apply_jev_recheck` deletes the old Jev checks
  and sets `reviewed_at` to null (`supabase/schema.sql:821` and `:848`). All 40 items it published
  are pass/pass, so they are not on the lists above.
- **The sentence splitter breaks on initials.** `_SENTENCE_END` in `agent/verifiers/jev.py` split
  "K. A. Bronnikov", which caused the false alarm on item 210. It can also hide a sentence from a
  fair check. I did not count the other cases.

## In progress

Nothing.

## Left

Not read, so nothing is claimed about them:

- **Jev sentence checks on published items:** the 1,895 `supports` were not read, apart from the
  near-misses below. Of the 111 `says_nothing`, I read only those on items I opened.
- **Near-misses, sentence read but not judged:** 6, 33, 77, 98, 111, 135, 187, 208, 257, 269, 279,
  307, 310, 341 and 387. Items 281 and 373 were compared with their pages: their dates and figures match. Item 281's
  "completely unknown" overstates, because "About 18% of the far side is occasionally visible".
- **Haiku explanation problems:** there are 104 on published items. I read each one as stored (cut
  to 420 characters). I compared about 15 items with their pages. These looked unproven or Haiku's
  own misreading: 11, 14, 96, 313, 315 and 311. The other flagged items were not compared, including
  9, 16, 18, 24, 36, 46, 48, 53, 67, 89, 157, 225, 254 and 289.
- **Haiku distractor `unclear` checks:** 10 on published items, read only as part of opened items.
- **Items where both verifiers passed:** 217, read only where listed above.

This audit covers visible published items only. The 18 items in review and 57 discarded items were
not assessed.

## Blocked on

Nothing. All data was read with GET; the corrections wait for Vedant.

## Needs from Vedant

1. **Corrections to the 7 FALSE items.** Recommend applying the suggested text. The changes are
   small, and each one fixes a sentence players can see now.
2. **Items 156 and 61.** Recommend a rewrite or discard, because their marked answers lack cited
   support. Item 61's mechanism is doubtful too.
3. **The gate gap under 0.5.** Should a `contradicts` label under 0.5 go to review? Recommend yes. It
   adds few items, and it closes the only machine route for a contradicted sentence. Not changed.
4. **A wider audit.** Recommend comparing the rest of the Haiku-flagged items with their pages, because 97 was found
   there. It needs no paid call. Your decision on scope.

## Files changed

- `docs/handoff/audit.md` (this file). No code and no bank rows.

## Checks run

- GET requests only to Supabase: `items`, `claim_checks`, `sources`, `topics`, `runs`,
  `curator_runs`, `cited_pages`. No PATCH, POST or RPC. No paid call.
- GET requests to public Wikipedia pages with a generic client name: Skylab 3, Milky Way, Red giant,
  International Space Station, Red-giant branch, Apollo 16.
- `jev_verdict` from `agent/gate.py` run on two sample checks. `numbers_in` run on 7 items.
- No project tests were run, because no code changed.
- **Shared temp folder warning from main:** this did not affect any finding. My scratch files were
  in my session scratchpad, and I wrote every file there myself. I moved to
  `%TEMP%\cqa-audit-only`, read the bank again, and compared. All 6 tables (384 items, 5,296 checks,
  1,191 sources, 60 topics, 412 runs, 8 curator runs) and all 36 stored-page files were identical.
