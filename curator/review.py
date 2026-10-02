"""The review queue: a person decides the items the publish gate was unsure about.

Each item is shown with everything needed to judge it: the question and marked answer, the
explanation, why it is in review, every cited source with the quote the agent took from it, and
Jev's source check. Decisions go straight to the bank; the database records when each item left
review (`items.reviewed_at`), so the verifiers' doubts can later be compared with the decisions.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from agent.store import ReviewDecision, ReviewItem, ReviewStore

WIDTH = 100
_INDENT = "    "
_CHOICES: dict[str, ReviewDecision | None] = {"p": "published", "d": "discarded", "s": None}
PROMPT = "Decision: [p]ublish, [d]iscard, [s]kip, [q]uit > "


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
    lines = ["=" * WIDTH, header, "", "Why it is in review:"]
    reasons = (
        [f"code: {r}" for r in item.code_problems]
        + [f"Haiku: {r}" for r in item.haiku_reasons]
        + [f"Jev: {r}" for r in item.jev_reasons]
    )
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
        while True:
            try:
                answer = ask(PROMPT).strip().lower()
            except EOFError:
                answer = "q"
            if answer == "q":
                return tally
            if answer in _CHOICES:
                break
            say("Please answer p, d, s or q.")
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
