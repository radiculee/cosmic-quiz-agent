"""The review queues: a person decides the items the publish gate was unsure about, and the
published items that players' reports have hidden.

Each item is shown with everything needed to judge it: the question and marked answer, the
explanation, why it is in review (or the reasons players gave in their reports), every cited
source with the quote the agent took from it, and Jev's source check. Decisions go straight to
the bank; the database records when each item left review (`items.reviewed_at`), so the
verifiers' doubts can later be compared with the decisions.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from agent.store import ReportDecision, ReviewDecision, ReviewItem, ReviewStore

WIDTH = 100
_INDENT = "    "
_CHOICES: dict[str, ReviewDecision | None] = {"p": "published", "d": "discarded", "s": None}
PROMPT = "Decision: [p]ublish, [d]iscard, [s]kip, [q]uit > "
_REPORT_CHOICES: dict[str, ReportDecision | None] = {"k": "kept", "d": "discarded", "s": None}
REPORT_PROMPT = "Decision: [k]eep (show it again), [d]iscard, [s]kip, [q]uit > "


def _wrap(text: str, indent: str = _INDENT) -> str:
    return textwrap.fill(
        " ".join(text.split()), WIDTH, initial_indent=indent, subsequent_indent=indent
    )


def _jev_lines(item: ReviewItem) -> list[str]:
    """Jev's verdict on the answer and each distractor; for an explanation, a sentence summary."""
    checks = item.claim_checks
    if not checks:
        return [f"{_INDENT}(no Jev result stored)"]
    lines: list[str] = []
    for check in checks:
        if check.kind in ("correct_answer", "distractor"):
            option = check.claim.rsplit(" is: ", 1)[-1]
            confidence = f"{check.confidence:.2f}" if check.confidence is not None else "-"
            label = "answer" if check.kind == "correct_answer" else "distractor"
            lines.append(f"{_INDENT}{label:<10} {check.verdict:<12} {confidence}  {option}")
    sentences = [c for c in checks if c.kind == "sentence"]
    if sentences:
        supported = sum(1 for c in sentences if c.verdict == "supports")
        lowest = min((c.confidence or 0.0) for c in sentences)
        lines.append(
            f"{_INDENT}explanation: {supported} of {len(sentences)} sentences supported "
            f"(lowest confidence {lowest:.2f})"
        )
    return lines


def format_item(item: ReviewItem, position: int, total: int) -> str:
    """The full text shown for one item."""
    header = (
        f"[{position}/{total}] item {item.id}  {item.mode.upper()} {item.difficulty}  "
        f"{item.topics.name} ({item.topics.kind}, added {item.created_at:%Y-%m-%d})"
    )
    lines = ["=" * WIDTH, header]
    reasons = (
        [f"code: {r}" for r in item.code_problems]
        + [f"Haiku: {r}" for r in item.haiku_reasons]
        + [f"Jev: {r}" for r in item.jev_reasons]
    )
    if item.report_count:
        lines += ["", f"Hidden by {item.report_count} reports. The reasons players gave:"]
        lines += [_wrap(f"- {report.reason or '(no reason given)'}") for report in item.reports]
        if reasons:
            lines += ["", "The publish gate's notes:"]
            lines += [_wrap(f"- {reason}") for reason in reasons]
    else:
        lines += ["", "Why it is in review:"]
        lines += [_wrap(f"- {reason}") for reason in reasons] or [f"{_INDENT}(no reason stored)"]

    if item.question is not None and item.options is not None:
        lines += ["", "Question:", _wrap(item.question)]
        for index, option in enumerate(item.options):
            marker = "   <- marked correct" if index == item.correct_index else ""
            lines.append(f"{_INDENT}{'ABCD'[index]}. {option}{marker}")
    lines += ["", "Explanation:", _wrap(item.explanation)]

    lines += ["", f"Sources ({len(item.sources)}, each read by the agent in this run):"]
    for source in item.sources:
        lines.append(f"{_INDENT}{source.ordinal + 1}. {source.url}")
        lines.append(_wrap(f'"{source.quote}"', _INDENT * 2))

    threshold = f", threshold {item.jev_threshold:g}" if item.jev_threshold is not None else ""
    lines += ["", f"Jev source check ({item.jev_criteria or 'unknown criteria'}{threshold}):"]
    lines += _jev_lines(item)
    return "\n".join(lines)


@dataclass
class ReviewTally:
    published: int = 0
    discarded: int = 0
    skipped: int = 0
    changed_elsewhere: int = 0
    kept: int = 0


def _ask_choice(
    ask: Callable[[str], str], say: Callable[[str], None], prompt: str, keys: Sequence[str]
) -> str:
    """One of `keys`, or "q" to stop (also when input ends). Asks again on anything else."""
    while True:
        try:
            answer = ask(prompt).strip().lower()
        except EOFError:
            return "q"
        if answer == "q" or answer in keys:
            return answer
        say(f"Please answer {', '.join(keys)} or q.")


def review(
    store: ReviewStore,
    items: Sequence[ReviewItem],
    ask: Callable[[str], str],
    say: Callable[[str], None],
) -> ReviewTally:
    """Show each item and apply the decision. Stops early on q or when input ends."""
    tally = ReviewTally()
    for position, item in enumerate(items, start=1):
        say(format_item(item, position, len(items)))
        answer = _ask_choice(ask, say, PROMPT, list(_CHOICES))
        if answer == "q":
            return tally
        decision = _CHOICES[answer]
        if decision is None:
            tally.skipped += 1
            continue
        if not store.decide_review(item.id, decision):
            tally.changed_elsewhere += 1
            say("This item was no longer in review (changed elsewhere); left as it is.")
        elif decision == "published":
            tally.published += 1
        else:
            tally.discarded += 1
    return tally


def review_reported(
    store: ReviewStore,
    items: Sequence[ReviewItem],
    ask: Callable[[str], str],
    say: Callable[[str], None],
) -> ReviewTally:
    """Show each item hidden by reports and apply the decision: keep shows it to players again,
    discard takes it out of the bank. Stops early on q or when input ends."""
    tally = ReviewTally()
    for position, item in enumerate(items, start=1):
        say(format_item(item, position, len(items)))
        answer = _ask_choice(ask, say, REPORT_PROMPT, list(_REPORT_CHOICES))
        if answer == "q":
            return tally
        decision = _REPORT_CHOICES[answer]
        if decision is None:
            tally.skipped += 1
            continue
        if not store.decide_reported(item.id, decision):
            tally.changed_elsewhere += 1
            say("This item was no longer hidden by reports (changed elsewhere); left as it is.")
        elif decision == "kept":
            tally.kept += 1
        else:
            tally.discarded += 1
    return tally
