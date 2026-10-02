# Evals

How the agent and its three-layer publish gate are measured, and what the first full run found.
Raw results live in `evals/results/` (gitignored); this page keeps the numbers that decided things.

## Method

- **Fixed topic set:** 20 astronomy topics (`evals/topics.py`) at EASY, MEDIUM and HARD: 60 quiz items
  per run. Results are only comparable while the set stays the same.
- **Planted errors:** 40 items that passed, each with one deliberate fault, 10 per type. Code plants
  a wrong number and a fake quote; Haiku plants an unsupported claim and a distractor rewritten to be
  true. A fixed seed makes the set reproducible. Layers 2 and 3 run on every planted item, even ones
  layer 1 already rejects, so each layer is measured on its own.
- **Hand review:** Vedant judged a stratified sample of 10 generated items with both verifiers'
  verdicts beside each one.
- **Re-scoring is free:** the publish decision (`agent/gate.py`) is a pure function of stored
  verification results, so rules and thresholds are compared without calling a model again.

Commands: `python -m evals run`, `seed RUN_DIR`, `verify-seeded RUN_DIR`, `report RUN_DIR`. Every
paid command prints its cost estimate and asks first.

## First full run (2026-10-01, `20261001T131332Z-full`)

### Layer 1: code checks

| Difficulty | Passed layer 1 | Model calls | Time | Agent cost |
|---|---|---|---|---|
| EASY | 19/20 | 3.5 | 10.5 s | $0.019 |
| MEDIUM | 19/20 | 4.3 | 14.9 s | $0.025 |
| HARD | 13/20 | 5.8 | 21.3 s | $0.029 |
| All | 51/60 (85%) | 4.5 | 15.6 s | $0.024 |

- 0 unfetched URLs in any passed item (target 0).
- Four of the nine failures were text-matching artifacts, not misquotes: empty brackets left by the
  Wikipedia text API, an invisible zero-width joiner, an en dash against a hyphen, and LaTeX in arXiv
  abstracts. Matching now ignores typographic variants and the tools clean the text before the model
  reads it. **Re-scored with the fix: 55/60 (92%)**, above the 90% target. The remaining five are
  genuine: one garbled quote, three numbers not on the cited pages, one run over its step budget.

### Planted errors

| Fault | Layer 1 | Haiku | Jev | Handled under all_must_pass |
|---|---|---|---|---|
| Wrong number | 10/10 | 9/10 | 9/10 | 10/10 |
| Fake quote | 10/10 (dropped) | 3/10 | 2/10 | 10/10 |
| Unsupported claim | 0/10 (by design) | 8/10 | 7/10 | 8/10 |
| Distractor made true | 0/10 (by design) | 9/10 | 10/10 | 10/10 |

38 of 40 faults never reach a player. The two misses are planted sentences the sources arguably do
support ("a lunar month", "a one-way membrane"), so they look like planting noise rather than misses.
A fake quote counts as handled when layer 1 drops that citation; the item may still publish on its
other, valid citations, which is what the live pipeline does.

### Verifiers on generated items

| Rule | Published directly | Planted faults handled |
|---|---|---|
| **all_must_pass (chosen)** | 43% (22/51) | 38/40 |
| hybrid (Haiku's explanation doubts alone do not block) | 69% (35/51) | 37/40 |
| jev_only | 76% (39/51) | 37/40 |
| haiku_only | 49% (25/51) | 38/40 |

- Haiku and Jev agree on pass / not pass for 61% of items. In 17 items Haiku had doubts and Jev
  passed: some were real errors Jev missed (a claim that the Great Red Spot was "continuously
  observed since 1831"; the source says continuous observation began in 1878), others were
  nitpicks that the hand review judged correct.
- **Jev calibration:** all 159 answer and distractor verdicts at confidence 0.97 or above were right.
  The threshold sweep (0.6 to 0.95) moved results by at most one or two items, so 0.8 stays.
- Jev caught 9 of 10 wrong numbers, better than its documentation's warning suggested, but layer 1
  still checks numbers in code.

### Cost and speed

| Part | Per item | Time |
|---|---|---|
| Agent research and writing (Haiku) | $0.024 | 15.6 s |
| Layer 2 verifier (Haiku) | $0.006 | 3.7 s |
| Layer 3 (Jev) | $0.0002 | 0.3 s |

Full run plus planted errors: $1.98 Anthropic, $0.018 TypeSafe. Cost per item published directly
under all_must_pass: $0.08.

## Decision (Vedant, 2026-10-01)

Keep **all_must_pass** with the Jev threshold at **0.8**. An item publishes only when all three layers
pass; any doubt goes to the review queue and any failure is discarded. This favours accuracy over
volume: in the hand review, nothing published was wrong, the one discarded item had a real factual
error, and two items Haiku sent to review were judged correct. Revisit if the review queue grows
faster than it can be cleared; the hybrid rule and a less strict Haiku prompt are the measured
alternatives.
