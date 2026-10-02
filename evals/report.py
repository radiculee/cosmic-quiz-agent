"""Scoring and reporting for an eval run.

Everything is computed from stored records, so a report can be rebuilt, or re-scored under another
gate rule or Jev threshold, without calling a model.

"Clean" items are the generated ones. They are treated as correct for false-reject and calibration
figures, which is an approximation: Vedant's hand review of a sample checks that assumption.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from statistics import mean

from agent.gate import GATE_RULES, GateRule, decide, jev_verdict
from agent.schemas import ItemRecord, JevCheck, LayerVerdict, QuizItem, Verification
from evals.seeding import FAULT_TYPES, SeededResult
from evals.topics import DIFFICULTIES

THRESHOLDS = (0.6, 0.7, 0.8, 0.9, 0.95)
CONFIDENCE_BANDS = ((0.0, 0.6), (0.6, 0.8), (0.8, 0.9), (0.9, 0.97), (0.97, 1.01))
HAND_REVIEW_SIZE = 10
HAND_REVIEW_SEED = 7


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}% ({part}/{whole})" if whole else "n/a"


def table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return [*lines, ""]


def _verified(items: Sequence[ItemRecord]) -> list[tuple[ItemRecord, Verification]]:
    return [(r, r.verification) for r in items if r.verification is not None]


def _haiku(v: Verification) -> LayerVerdict:
    return v.haiku.verdict if v.haiku else "error"


def _jev(v: Verification, threshold: float | None = None) -> LayerVerdict:
    if v.jev is None:
        return "error"
    if threshold is None or v.jev.verdict == "error":
        return v.jev.verdict
    return jev_verdict(v.jev.checks, threshold)[0]


# --- Sections ---------------------------------------------------------------------------------


def generation_section(items: Sequence[ItemRecord]) -> tuple[list[str], dict[str, object]]:
    lines = ["## 1. Generation and layer 1 (code checks)", ""]
    rows: list[list[object]] = []
    summary: dict[str, object] = {}
    for label, group in [
        *[(d, [r for r in items if r.run.difficulty == d]) for d in DIFFICULTIES],
        ("all", list(items)),
    ]:
        if not group:
            continue
        passed = [r for r in group if r.run.outcome == "passed"]
        corrected = [r for r in passed if r.run.detail]
        rows.append(
            [
                label,
                len(group),
                pct(len(passed), len(group)),
                len(corrected),
                f"{mean(r.run.model_calls for r in group):.1f}",
                f"{mean(r.run.seconds for r in group):.1f}s",
                f"${mean(r.run.cost_usd for r in group):.4f}",
            ]
        )
        summary[label] = {"items": len(group), "layer1_pass": len(passed)}
    lines += table(
        [
            "Difficulty",
            "Items",
            "Passed layer 1",
            "Passed with a note",
            "Model calls",
            "Time",
            "Agent cost",
        ],
        rows,
    )
    outcomes = Counter(r.run.outcome for r in items)
    lines.append("Outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())))
    unfetched = sum(
        len(r.run.code_check.citations.unfetched)
        for r in items
        if r.run.outcome == "passed" and r.run.code_check
    )
    lines += [f"Unfetched URLs in passed items: {unfetched} (target 0).", ""]
    failures = [r for r in items if r.run.outcome != "passed"]
    if failures:
        lines.append("Items that did not pass layer 1:")
        lines += [
            f"- {r.run.difficulty} {r.run.topic}: {r.run.outcome} ({r.run.detail})"
            for r in failures
        ]
        lines.append("")
    summary["outcomes"] = dict(outcomes)
    summary["unfetched_urls_in_passed"] = unfetched
    return lines, summary


def verifier_section(items: Sequence[ItemRecord]) -> tuple[list[str], dict[str, object]]:
    verified = _verified(items)
    lines = ["## 2. Verifiers on generated items", ""]
    if not verified:
        return [*lines, "No verified items.", ""], {}
    haiku_counts = Counter(_haiku(v) for _, v in verified)
    jev_counts = Counter(_jev(v) for _, v in verified)
    verdicts: tuple[LayerVerdict, ...] = ("pass", "borderline", "fail", "error")
    lines += table(
        ["Layer", *verdicts],
        [
            ["Haiku (layer 2)", *(haiku_counts[k] for k in verdicts)],
            ["Jev (layer 3, 0.8)", *(jev_counts[k] for k in verdicts)],
        ],
    )
    both = sum(1 for _, v in verified if _haiku(v) == "pass" and _jev(v) == "pass")
    only_haiku = sum(1 for _, v in verified if _haiku(v) == "pass" and _jev(v) != "pass")
    only_jev = sum(1 for _, v in verified if _haiku(v) != "pass" and _jev(v) == "pass")
    neither = len(verified) - both - only_haiku - only_jev
    agreement = both + neither
    lines += [
        f"Agreement on pass / not pass: {pct(agreement, len(verified))}. Both pass {both}, only "
        f"Haiku passes {only_haiku}, only Jev passes {only_jev}, neither passes {neither}.",
        "",
        "Status of generated items under each rule (generated items are treated as correct, so "
        "anything not published is a possible false reject; the hand review checks this):",
        "",
    ]
    rule_rows = []
    statuses: dict[str, dict[str, int]] = {}
    for rule in GATE_RULES:
        counts = Counter(decide(v, rule) for _, v in verified)
        statuses[rule] = {str(status): count for status, count in counts.items()}
        rule_rows.append(
            [rule, pct(counts["published"], len(verified)), counts["review"], counts["discarded"]]
        )
    lines += table(["Rule", "Published", "Review", "Discarded"], rule_rows)

    reasons: Counter[str] = Counter()
    for _, v in verified:
        if v.haiku:
            reasons.update(f"Haiku: {_reason_kind(r)}" for r in v.haiku.reasons)
        if v.jev:
            reasons.update(f"Jev: {_reason_kind(r)}" for r in v.jev.reasons)
    if reasons:
        lines.append("Most common reasons for not passing:")
        lines += [f"- {reason}: {count}" for reason, count in reasons.most_common(10)]
        lines.append("")
    summary = {
        "verified": len(verified),
        "haiku": dict(haiku_counts),
        "jev": dict(jev_counts),
        "agreement": agreement,
        "status_by_rule": statuses,
    }
    return lines, summary


def _reason_kind(reason: str) -> str:
    """Group reasons by their kind, dropping the item-specific text after the first colon."""
    head = reason.split(":", 1)[0]
    return head.split(" (")[0].strip()


def _layer1_caught(result: SeededResult) -> bool:
    """A fake quote is caught when layer 1 drops it; other faults when the item fails layer 1."""
    code = result.verification.code
    if result.seeded.fault == "fake_quote":
        return bool(code.citations.misquoted)
    return not code.passed


def fault_handled(result: SeededResult, rule: GateRule) -> bool:
    """The fault cannot reach a player: the item is not published, or (for a fake quote) the bad
    citation is dropped by layer 1 and the item is published on its remaining valid citations."""
    if result.seeded.fault == "fake_quote" and result.verification.code.citations.misquoted:
        return True
    return decide(result.verification, rule) != "published"


def seeded_section(results: Sequence[SeededResult]) -> tuple[list[str], dict[str, object]]:
    lines = ["## 3. Planted errors: which layers catch which faults", ""]
    if not results:
        return [
            *lines,
            "No planted-error results yet (run `python -m evals seed` and `verify-seeded`).",
            "",
        ], {}
    rows = []
    summary: dict[str, object] = {}
    for fault in FAULT_TYPES:
        group = [r for r in results if r.seeded.fault == fault]
        if not group:
            continue
        n = len(group)
        layer1 = sum(1 for r in group if _layer1_caught(r))
        haiku = sum(1 for r in group if _haiku(r.verification) != "pass")
        jev = sum(1 for r in group if _jev(r.verification) != "pass")
        by_rule = {rule: sum(1 for r in group if fault_handled(r, rule)) for rule in GATE_RULES}
        rows.append(
            [
                fault,
                n,
                pct(layer1, n),
                pct(haiku, n),
                pct(jev, n),
                *(pct(by_rule[r], n) for r in GATE_RULES),
            ]
        )
        summary[fault] = {"n": n, "layer1": layer1, "haiku": haiku, "jev": jev, "by_rule": by_rule}
    lines += table(
        ["Fault", "Items", "Layer 1", "Haiku", "Jev", *(f"Handled: {r}" for r in GATE_RULES)],
        rows,
    )
    lines += [
        "A layer 'catches' a fault when its verdict is anything but pass. Layers 2 and 3 run on "
        "every planted item, even ones layer 1 already rejects, so each layer is measured on its "
        "own. 'Handled' means the fault cannot reach a player: the item is not published, or for "
        "a fake quote, layer 1 drops that citation (the item may still publish on its other, "
        "valid citations).",
        "",
    ]
    missed = [r for r in results if not fault_handled(r, "all_must_pass")]
    if missed:
        lines.append("Planted faults that would still be published under all_must_pass:")
        lines += [f"- {r.seeded.id} ({r.seeded.topic}): {r.seeded.description}" for r in missed]
        lines.append("")
    return lines, summary


def threshold_section(
    items: Sequence[ItemRecord], results: Sequence[SeededResult]
) -> tuple[list[str], dict[str, object]]:
    verified = _verified(items)
    subtle = [r for r in results if r.seeded.fault in ("unsupported_claim", "true_distractor")]
    lines = [
        "## 4. Jev threshold sweep",
        "",
        "Generated items published, and subtle planted faults (unsupported claim, true "
        "distractor) caught, by Jev alone and by all_must_pass, at each threshold. 'Flag "
        "unsupported' also treats sentences Jev says the sources do not address as doubtful.",
        "",
    ]
    rows = []
    summary: dict[str, object] = {}
    for flag in (False, True):
        for threshold in THRESHOLDS:
            row: list[object] = [threshold, "yes" if flag else "no"]
            entry: dict[str, int] = {}
            for rule in ("jev_only", "all_must_pass"):
                published = sum(
                    1
                    for _, v in verified
                    if decide(v, rule, jev_threshold=threshold, flag_unsupported_sentences=flag)
                    == "published"
                )
                caught = sum(
                    1
                    for r in subtle
                    if decide(
                        r.verification,
                        rule,
                        jev_threshold=threshold,
                        flag_unsupported_sentences=flag,
                    )
                    != "published"
                )
                row += [pct(published, len(verified)), pct(caught, len(subtle))]
                entry[f"{rule}_published"] = published
                entry[f"{rule}_caught"] = caught
            rows.append(row)
            summary[f"{threshold}|flag={flag}"] = entry
    lines += table(
        [
            "Threshold",
            "Flag unsupported",
            "Jev only: published",
            "Jev only: caught",
            "All must pass: published",
            "All must pass: caught",
        ],
        rows,
    )
    return lines, summary


def calibration_section(items: Sequence[ItemRecord]) -> tuple[list[str], dict[str, object]]:
    """How often Jev's answer-level verdicts are right, grouped by its confidence.

    Truth on generated items: the correct answer should be supported and each distractor not.
    """
    checks: list[tuple[JevCheck, bool]] = []
    for _, v in _verified(items):
        if v.jev is None:
            continue
        for check in v.jev.checks:
            if check.kind == "correct_answer":
                checks.append((check, check.verdict == "supports"))
            elif check.kind == "distractor":
                checks.append((check, check.verdict != "supports"))
    lines = ["## 5. Jev calibration (answer and distractor claims)", ""]
    if not checks:
        return [*lines, "No Jev checks.", ""], {}
    rows = []
    summary: dict[str, object] = {}
    for low, high in CONFIDENCE_BANDS:
        band = [right for check, right in checks if low <= check.confidence < high]
        label = f"{low:.2f}-{min(high, 1.0):.2f}"
        rows.append([label, len(band), pct(sum(band), len(band))])
        summary[label] = {"n": len(band), "right": sum(band)}
    lines += table(["Jev confidence", "Claims", "Verdict right"], rows)
    lines += [
        "Well calibrated means the 'right' rate in each band roughly matches its confidence.",
        "",
    ]
    return lines, summary


def cost_section(
    items: Sequence[ItemRecord], results: Sequence[SeededResult]
) -> tuple[list[str], dict[str, object]]:
    verified = _verified(items)
    agent_cost = sum(r.run.cost_usd for r in items)
    haiku_cost = sum(v.haiku.cost_usd for _, v in verified if v.haiku)
    jev_cost = sum(v.jev.cost_usd for _, v in verified if v.jev)
    seeded_anthropic = sum(r.anthropic_cost_usd for r in results)
    seeded_typesafe = sum(r.typesafe_cost_usd for r in results)
    published = sum(1 for _, v in verified if decide(v) == "published")

    def seconds(get: Callable[[Verification], float | None]) -> str:
        values = [s for _, v in verified if (s := get(v)) is not None]
        return f"{mean(values):.1f}s" if values else "n/a"

    lines = [
        "## 6. Cost and speed",
        "",
        *table(
            ["Part", "Total", "Per item", "Average time"],
            [
                [
                    "Agent (Haiku research and writing)",
                    f"${agent_cost:.3f}",
                    f"${agent_cost / max(len(items), 1):.4f}",
                    f"{mean(r.run.seconds for r in items):.1f}s" if items else "n/a",
                ],
                [
                    "Layer 2 (Haiku verifier)",
                    f"${haiku_cost:.3f}",
                    f"${haiku_cost / max(len(verified), 1):.4f}",
                    seconds(lambda v: v.haiku.seconds if v.haiku else None),
                ],
                [
                    "Layer 3 (Jev)",
                    f"${jev_cost:.5f}",
                    f"${jev_cost / max(len(verified), 1):.6f}",
                    seconds(lambda v: v.jev.seconds if v.jev else None),
                ],
                [
                    "Planted-error verification (Anthropic / TypeSafe)",
                    f"${seeded_anthropic:.3f} / ${seeded_typesafe:.5f}",
                    "",
                    "",
                ],
            ],
        ),
        f"Anthropic total: ${agent_cost + haiku_cost + seeded_anthropic:.3f}. TypeSafe total: "
        f"${jev_cost + seeded_typesafe:.5f}.",
        "Cost per published item (all_must_pass): "
        + (f"${(agent_cost + haiku_cost + jev_cost) / published:.4f}." if published else "n/a."),
        "",
    ]
    return lines, {
        "agent_usd": agent_cost,
        "haiku_usd": haiku_cost,
        "jev_usd": jev_cost,
        "seeded_anthropic_usd": seeded_anthropic,
        "seeded_typesafe_usd": seeded_typesafe,
        "published_all_must_pass": published,
    }


# --- Outputs ----------------------------------------------------------------------------------


def write_report(
    out_dir: Path, items: Sequence[ItemRecord], results: Sequence[SeededResult]
) -> Path:
    sections: list[tuple[str, tuple[list[str], dict[str, object]]]] = [
        ("generation", generation_section(items)),
        ("verifiers", verifier_section(items)),
        ("seeded", seeded_section(results)),
        ("thresholds", threshold_section(items, results)),
        ("calibration", calibration_section(items)),
        ("cost", cost_section(items, results)),
    ]
    lines = [f"# Eval report: {out_dir.name}", ""]
    summary: dict[str, object] = {}
    for name, (section_lines, section_summary) in sections:
        lines += section_lines
        summary[name] = section_summary
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_hand_review(out_dir, items)
    return out_dir / "report.md"


def write_hand_review(out_dir: Path, items: Sequence[ItemRecord]) -> Path:
    """A stratified sample of generated items for Vedant to judge, with both verifiers' views."""
    rng = random.Random(HAND_REVIEW_SEED)
    sample: list[ItemRecord] = []
    for difficulty in DIFFICULTIES:
        group = [r for r, _ in _verified(items) if r.run.difficulty == difficulty]
        rng.shuffle(group)
        sample += group[: -(-HAND_REVIEW_SIZE // len(DIFFICULTIES))]
    sample = sample[:HAND_REVIEW_SIZE]

    lines = [
        "# Hand review",
        "",
        "For each item, tick what is true and add a note if not. Your judgement sets the quality "
        "bar and checks whether the verifiers agree with you.",
        "",
    ]
    for number, record in enumerate(sample, start=1):
        item = record.run.answer
        if not isinstance(item, QuizItem) or record.verification is None:
            continue
        v = record.verification
        lines += [f"## {number}. {record.run.topic} ({record.run.difficulty}): {record.status}", ""]
        lines += [f"**{item.question}**", ""]
        lines += [
            f"- {'ABCD'[i]}. {option}{'  (correct)' if i == item.correct_index else ''}"
            for i, option in enumerate(item.options)
        ]
        lines += ["", item.explanation, "", "Sources:"]
        lines += [f'- {c.url}: "{c.quote}"' for c in item.citations]
        haiku = v.haiku
        lines += ["", f"Haiku: {haiku.verdict if haiku else 'none'}"]
        if haiku:
            lines += [f"- {reason}" for reason in haiku.reasons]
        jev = v.jev
        lines.append(f"Jev: {jev.verdict if jev else 'none'}")
        if jev:
            lines += [
                f"- {c.kind}: {c.verdict} {c.confidence:.2f}"
                + (f" ({c.claim})" if c.kind == "sentence" else "")
                for c in jev.checks
            ]
        lines += [
            "",
            "- [ ] The marked answer is correct",
            "- [ ] All three other options are clearly wrong",
            "- [ ] The explanation is accurate and clear",
            "- [ ] I would publish this",
            "",
            "Notes:",
            "",
            "---",
            "",
        ]
    path = out_dir / "hand_review.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


__all__ = ["GateRule", "write_hand_review", "write_report"]
