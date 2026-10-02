"""Re-check stored eval items with Jev only, under a different criteria wording.

Layer 1 and Haiku results are reused exactly as stored, so a re-check costs only Jev tokens
(TypeSafe). The comparison report shows how the new wording changes Jev's verdicts, the publish
decision under the agreed rule, and how many planted faults are still handled.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from agent.config import JevCriteria, Settings
from agent.gate import DEFAULT_RULE, decide
from agent.schemas import ItemRecord, LayerVerdict, Status
from agent.verifiers import JevClient, verify_with_jev
from evals.report import fault_handled, pct, table
from evals.seeding import FAULT_TYPES, SeededResult

HAND_REVIEW_FILE = "hand_review.md"
_HAND_REVIEW_HEADING = re.compile(r"^## \d+\. (.+) \((easy|medium|hard)\): ", re.MULTILINE)


def items_file(criteria: JevCriteria) -> str:
    return f"rejev_{criteria}_items.jsonl"


def seeded_file(criteria: JevCriteria) -> str:
    return f"rejev_{criteria}_seeded.jsonl"


def report_file(criteria: JevCriteria) -> str:
    return f"rejev_{criteria}.md"


def stored_criteria(records: Iterable[ItemRecord]) -> str:
    """The criteria wording the stored Jev results were produced with."""
    for record in records:
        if record.verification is not None and record.verification.jev is not None:
            return record.verification.jev.criteria
    return "stored"


def recheck_item(record: ItemRecord, jev: JevClient, settings: Settings) -> ItemRecord:
    """The same item with layer 3 re-run and the publish status recomputed."""
    if record.verification is None or record.run.answer is None:
        return record
    report = verify_with_jev(record.run.answer, record.run.cited_pages, jev, settings)
    verification = record.verification.model_copy(update={"jev": report})
    return record.model_copy(
        update={"verification": verification, "status": decide(verification, DEFAULT_RULE)}
    )


def recheck_seeded(result: SeededResult, jev: JevClient, settings: Settings) -> SeededResult:
    report = verify_with_jev(result.seeded.item, result.seeded.pages, jev, settings)
    verification = result.verification.model_copy(update={"jev": report})
    return result.model_copy(
        update={"verification": verification, "typesafe_cost_usd": report.cost_usd}
    )


def recheck_all[T](
    records: Sequence[T],
    check: Callable[[T], T],
    workers: int,
    on_done: Callable[[T], None],
) -> list[T]:
    """Run `check` on every record in parallel, keeping the input order."""
    done: list[T] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(check, records):
            on_done(result)
            done.append(result)
    return done


# --- Comparison report ------------------------------------------------------------------------


def hand_reviewed(run_dir: Path) -> set[tuple[str, str]]:
    """(topic, difficulty) of every item in the run's hand review, if there is one."""
    path = run_dir / HAND_REVIEW_FILE
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8")
    return {(m.group(1), m.group(2)) for m in _HAND_REVIEW_HEADING.finditer(text)}


def _jev(record: ItemRecord) -> LayerVerdict:
    v = record.verification
    return v.jev.verdict if v is not None and v.jev is not None else "error"


def _haiku(record: ItemRecord) -> LayerVerdict:
    v = record.verification
    return v.haiku.verdict if v is not None and v.haiku is not None else "error"


def _count_rows[K: str](
    keys: Iterable[K], before: Counter[K], after: Counter[K]
) -> list[tuple[str, int, int]]:
    return [(key, before[key], after[key]) for key in keys]


def write_comparison(
    run_dir: Path,
    criteria: JevCriteria,
    baseline: str,
    old_items: Sequence[ItemRecord],
    new_items: Sequence[ItemRecord],
    old_seeded: Sequence[SeededResult],
    new_seeded: Sequence[SeededResult],
) -> Path:
    """Write `rejev_<criteria>.md` comparing the stored Jev results with the re-check."""
    old_verified = [r for r in old_items if r.verification is not None]
    new_verified = [r for r in new_items if r.verification is not None]
    lines = [
        f"# Jev re-check: {criteria} against {baseline}",
        "",
        f"Run `{run_dir.name}`. Layer 1 and Haiku results are the stored ones; only Jev was "
        f"re-run. Publish rule: {DEFAULT_RULE}.",
        "",
        f"## 1. Generated items ({len(new_verified)} that passed layer 1)",
        "",
    ]

    verdicts: tuple[LayerVerdict, ...] = ("pass", "borderline", "fail", "error")
    lines += table(
        ["Jev verdict", baseline, criteria],
        _count_rows(
            verdicts,
            Counter(_jev(r) for r in old_verified),
            Counter(_jev(r) for r in new_verified),
        ),
    )
    statuses: tuple[Status, ...] = ("published", "review", "discarded")
    old_status = [decide(r.verification, DEFAULT_RULE) for r in old_verified if r.verification]
    new_status = [decide(r.verification, DEFAULT_RULE) for r in new_verified if r.verification]
    lines += table(
        ["Publish decision", baseline, criteria],
        _count_rows(statuses, Counter(old_status), Counter(new_status)),
    )

    def agreement(records: Sequence[ItemRecord]) -> str:
        same = sum(1 for r in records if (_haiku(r) == "pass") == (_jev(r) == "pass"))
        return pct(same, len(records))

    lines += [
        f"Haiku and Jev agree on pass / not pass: {agreement(old_verified)} with {baseline}, "
        f"{agreement(new_verified)} with {criteria}.",
        "",
    ]

    lines += ["## 2. Planted faults handled", ""]
    if new_seeded:
        rows: list[tuple[str, str, str, str, str]] = []
        for fault in FAULT_TYPES:
            old_group = [r for r in old_seeded if r.seeded.fault == fault]
            new_group = [r for r in new_seeded if r.seeded.fault == fault]

            def jev_caught(group: Sequence[SeededResult]) -> str:
                caught = sum(
                    1 for r in group if r.verification.jev and r.verification.jev.verdict != "pass"
                )
                return f"{caught}/{len(group)}"

            def handled(group: Sequence[SeededResult]) -> str:
                return f"{sum(1 for r in group if fault_handled(r, DEFAULT_RULE))}/{len(group)}"

            rows.append(
                (
                    fault,
                    jev_caught(old_group),
                    jev_caught(new_group),
                    handled(old_group),
                    handled(new_group),
                )
            )
        lines += table(
            [
                "Fault",
                f"Jev flags ({baseline})",
                f"Jev flags ({criteria})",
                f"Handled ({baseline})",
                f"Handled ({criteria})",
            ],
            rows,
        )
    else:
        lines += ["No planted-fault results in this run.", ""]

    lines += ["## 3. Items whose Jev verdict changed", ""]
    reviewed = hand_reviewed(run_dir)
    changed_rows: list[tuple[str, str, str, str, str]] = []
    for old, new in zip(old_verified, new_verified, strict=True):
        if _jev(old) == _jev(new):
            continue
        key = (old.run.topic, old.run.difficulty)
        new_jev = new.verification.jev if new.verification else None
        reasons = "; ".join(new_jev.reasons) if new_jev else ""
        changed_rows.append(
            (
                f"{old.run.topic} ({old.run.difficulty})"
                + (" [hand-reviewed]" if key in reviewed else ""),
                f"{_jev(old)} -> {_jev(new)}",
                f"{old.status} -> {new.status}",
                f"haiku {_haiku(new)}",
                reasons.replace("|", "/")[:300] or "-",
            )
        )
    if changed_rows:
        lines += table(["Item", "Jev", "Status", "Haiku", "New Jev reasons"], changed_rows)
    else:
        lines += ["None.", ""]

    tokens = sum(
        r.verification.jev.input_tokens
        for r in new_verified
        if r.verification and r.verification.jev
    ) + sum(r.verification.jev.input_tokens for r in new_seeded if r.verification.jev)
    cost = sum(
        r.verification.jev.cost_usd for r in new_verified if r.verification and r.verification.jev
    ) + sum(r.typesafe_cost_usd for r in new_seeded)
    lines += [
        "## 4. Cost",
        "",
        f"Jev re-check: {tokens:,} input tokens, ${cost:.4f} on TypeSafe. No Anthropic spend.",
        "",
    ]

    path = run_dir / report_file(criteria)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
