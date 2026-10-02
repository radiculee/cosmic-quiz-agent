"""The eval run: one quiz item per topic and difficulty, each through all three layers."""

from __future__ import annotations

import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from agent.config import Settings
from agent.gate import DEFAULT_RULE, decide
from agent.llm import LLMProvider
from agent.loop import run_quiz
from agent.schemas import Difficulty, ItemRecord
from agent.verifiers import JevClient, verify
from evals.store import ITEMS_FILE, RESULTS_DIR, JsonLinesWriter

# Measured in Session 3 development: a QUIZ run averages about $0.024 and a Haiku verifier pass
# about $0.006. The upper bound allows for longer runs and one correction round.
ITEM_COST_LOW = 0.025
ITEM_COST_HIGH = 0.035
JEV_COST_PER_ITEM = 0.0003


def estimate(items: int) -> str:
    low, high = items * ITEM_COST_LOW, items * ITEM_COST_HIGH
    return (
        f"{items} quiz items: about ${low:.2f} to ${high:.2f} on Anthropic and under "
        f"${items * JEV_COST_PER_ITEM:.3f} on TypeSafe (Jev)."
    )


def new_run_dir(label: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return RESULTS_DIR / f"{stamp}-{label}"


def evaluate_one(
    topic: str,
    difficulty: Difficulty,
    llm: LLMProvider,
    jev: JevClient | None,
    settings: Settings,
) -> ItemRecord:
    """Generate one quiz item and run every layer on it. Items that fail layer 1 are recorded
    as generated, with no verification."""
    result = run_quiz(topic, difficulty, llm, settings)
    if result.answer is None or result.code_check is None or not result.code_check.passed:
        return ItemRecord(run=result, status="discarded", rule=DEFAULT_RULE)
    verification = verify(result.answer, result.code_check, result.cited_pages, llm, jev, settings)
    return ItemRecord(
        run=result,
        verification=verification,
        status=decide(verification, DEFAULT_RULE),
        rule=DEFAULT_RULE,
    )


def run_eval(
    topics: Sequence[str],
    difficulties: Sequence[Difficulty],
    llm: LLMProvider,
    jev: JevClient | None,
    settings: Settings,
    out_dir: Path,
    workers: int,
) -> Path:
    """Evaluate every topic at every difficulty, writing each record as it completes."""
    jobs = [(topic, difficulty) for topic in topics for difficulty in difficulties]
    writer = JsonLinesWriter(out_dir / ITEMS_FILE)
    started = time.monotonic()
    spent = 0.0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(evaluate_one, topic, difficulty, llm, jev, settings): (topic, difficulty)
            for topic, difficulty in jobs
        }
        for done, future in enumerate(as_completed(futures), start=1):
            topic, difficulty = futures[future]
            record = future.result()
            writer.write(record)
            spent += record.anthropic_cost_usd
            haiku = record.verification.haiku if record.verification else None
            jev_report = record.verification.jev if record.verification else None
            print(
                f"[{done:>2}/{len(jobs)}] {difficulty:<6} {topic[:40]:<40} "
                f"{record.run.outcome:<14} haiku={haiku.verdict if haiku else '-':<10} "
                f"jev={jev_report.verdict if jev_report else '-':<10} -> {record.status} "
                f"(${record.anthropic_cost_usd:.3f}, spent ${spent:.2f}, "
                f"{time.monotonic() - started:.0f}s)",
                flush=True,
            )
    return out_dir / ITEMS_FILE
