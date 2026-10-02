"""The publish decision, computed from stored verification results.

Every function here is pure: given the same `Verification`, it always gives the same answer. That
lets the eval re-score stored items under each candidate rule and threshold without calling a
model again, and lets the rule chosen in Session 3 be changed later the same way.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from agent.schemas import HaikuReport, ItemRecord, JevCheck, LayerVerdict, Status, Verification

GateRule = Literal["all_must_pass", "jev_escalates", "haiku_only", "jev_only"]

GATE_RULES: tuple[GateRule, ...] = ("all_must_pass", "jev_escalates", "haiku_only", "jev_only")
# The rule is chosen with Vedant from the Session 3 eval results; until then the strictest applies.
DEFAULT_RULE: GateRule = "all_must_pass"
# A Jev probability at or above this (but under the threshold) is treated as doubt, not proof.
JEV_DOUBT = 0.5


def haiku_verdict(report: HaikuReport, *, is_quiz: bool) -> tuple[LayerVerdict, tuple[str, ...]]:
    """Layer 2 verdict from the structured report, never from the model's own opinion."""
    if report.verdict == "error":
        return "error", report.reasons
    fail: list[str] = []
    doubt: list[str] = []
    if is_quiz:
        if report.answer_verdict != "supported":
            fail.append(f"correct answer is {report.answer_verdict or 'not judged'}")
        elif not report.answer_quote_verbatim:
            # The verifier's own evidence is not word for word on a page. That is the verifier's
            # mistake, not proof the item is wrong, so a person decides (changed 2026-10-02: in
            # the Session 3 eval it caught no planted fault and discarded 5 items).
            doubt.append("verifier's supporting quote is not on a cited page")
        for judged in report.distractors:
            if judged.verdict == "also_correct":
                fail.append(f"distractor may also be correct: {judged.option}")
            elif judged.verdict == "unclear":
                doubt.append(f"distractor not settled by sources: {judged.option}")
    doubt += [f"explanation: {problem}" for problem in report.explanation_problems]
    if fail:
        return "fail", tuple(fail + doubt)
    if doubt:
        return "borderline", tuple(doubt)
    return "pass", ()


def jev_verdict(
    checks: Iterable[JevCheck], threshold: float, *, flag_unsupported_sentences: bool = False
) -> tuple[LayerVerdict, tuple[str, ...]]:
    """Layer 3 verdict at a confidence threshold, from Jev's per-claim probabilities.

    Fail: the correct answer is contradicted, a distractor is supported, or a sentence is
    contradicted, each at or above the threshold. Borderline: the correct answer's support is
    below the threshold, or any of those signals reaches the doubt level. Sentences Jev says
    nothing about are ignored unless `flag_unsupported_sentences`, because explanations
    legitimately paraphrase and connect facts.
    """
    fail: list[str] = []
    doubt: list[str] = []
    for check in checks:
        supports = check.probabilities.get("supports", 0.0)
        contradicts = check.probabilities.get("contradicts", 0.0)
        silent = check.probabilities.get("says_nothing", 0.0)
        label = f"{check.kind}: {check.claim}"
        if check.kind == "correct_answer":
            if contradicts >= threshold:
                fail.append(f"contradicted ({contradicts:.2f}) {label}")
            elif supports < threshold:
                doubt.append(f"weak support ({supports:.2f}) {label}")
        elif check.kind == "distractor":
            if supports >= threshold:
                fail.append(f"supported ({supports:.2f}) {label}")
            elif supports >= JEV_DOUBT:
                doubt.append(f"possibly supported ({supports:.2f}) {label}")
        else:
            if contradicts >= threshold:
                fail.append(f"contradicted ({contradicts:.2f}) {label}")
            elif contradicts >= JEV_DOUBT:
                doubt.append(f"possibly contradicted ({contradicts:.2f}) {label}")
            elif flag_unsupported_sentences and silent >= threshold:
                doubt.append(f"unsupported ({silent:.2f}) {label}")
    if fail:
        return "fail", tuple(fail + doubt)
    if doubt:
        return "borderline", tuple(doubt)
    return "pass", ()


def _combine(*verdicts: LayerVerdict) -> Status:
    if "fail" in verdicts:
        return "discarded"
    if "borderline" in verdicts or "error" in verdicts:
        return "review"
    return "published"


def decide(
    verification: Verification,
    rule: GateRule = DEFAULT_RULE,
    *,
    jev_threshold: float | None = None,
    flag_unsupported_sentences: bool = False,
) -> Status:
    """Publish status under a rule. Layer 1 failures are always discarded.

    - all_must_pass: any layer failing discards; any doubt, disagreement or error goes to review.
    - jev_escalates: Haiku decides; if Haiku passes but Jev does not, the item goes to review.
    - haiku_only / jev_only: single-verifier baselines, for comparison in the eval.

    `jev_threshold` re-scores Jev's stored probabilities at a different threshold.
    """
    if not verification.code.passed:
        return "discarded"
    haiku: LayerVerdict = verification.haiku.verdict if verification.haiku else "error"
    jev: LayerVerdict = "error"
    if verification.jev is not None:
        jev = verification.jev.verdict
        if verification.jev.verdict != "error" and (
            jev_threshold is not None or flag_unsupported_sentences
        ):
            threshold = jev_threshold if jev_threshold is not None else verification.jev.threshold
            jev, _ = jev_verdict(
                verification.jev.checks,
                threshold,
                flag_unsupported_sentences=flag_unsupported_sentences,
            )

    if rule == "all_must_pass":
        return _combine(haiku, jev)
    if rule == "jev_escalates":
        if haiku != "pass":
            return _combine(haiku)
        return "published" if jev == "pass" else "review"
    if rule == "haiku_only":
        return _combine(haiku)
    return _combine(jev)


def rescore(verification: Verification) -> Verification:
    """The same results with each layer's verdict recomputed under the current rules.

    Stored records keep the verdicts of the rules they were decided under. Re-scoring them makes
    old and new results comparable after a rule changes (for example the 2026-10-02 change that
    sends a verifier misquote to review). A Haiku report is a quiz report when it judged an
    answer; LEARN reports never do.
    """
    haiku = verification.haiku
    if haiku is not None and haiku.verdict != "error":
        verdict, reasons = haiku_verdict(haiku, is_quiz=haiku.answer_verdict is not None)
        haiku = haiku.model_copy(update={"verdict": verdict, "reasons": reasons})
    jev = verification.jev
    if jev is not None and jev.verdict != "error":
        jev_layer, jev_reasons = jev_verdict(jev.checks, jev.threshold)
        jev = jev.model_copy(update={"verdict": jev_layer, "reasons": jev_reasons})
    return verification.model_copy(update={"haiku": haiku, "jev": jev})


def rescore_record(record: ItemRecord, rule: GateRule = DEFAULT_RULE) -> ItemRecord:
    """A stored record with its verdicts and publish status under the current rules."""
    if record.verification is None:
        return record
    verification = rescore(record.verification)
    return record.model_copy(
        update={"verification": verification, "status": decide(verification, rule), "rule": rule}
    )
