"""Command line entry point.

    python -m agent learn "Neutron stars" --difficulty medium [--verify]
    python -m agent quiz "Neutron stars" --difficulty hard [--no-verify]

Streams each step as it happens, prints the answer, the three verification layers and the run
metrics, and saves the full record as JSON under runs/.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from agent.config import Settings, load_settings
from agent.gate import DEFAULT_RULE, decide
from agent.llm import AnthropicProvider
from agent.loop import run_learn, run_quiz
from agent.schemas import Difficulty, ItemRecord, QuizItem, RunResult, Step, Verification
from agent.verifiers import JevClient, TypeSafeJev, verify


def _print_step(step: Step) -> None:
    marker = "!" if step.is_error else "-"
    tokens = ""
    if step.usage is not None:
        u = step.usage
        tokens = (
            f"  [in {u.input_tokens}, cache write {u.cache_write_tokens}, "
            f"cache read {u.cache_read_tokens}, out {u.output_tokens}]"
        )
    print(f"  {marker} {step.kind:<5} {step.summary} ({step.seconds:.1f}s){tokens}", flush=True)


def _print_answer(result: RunResult) -> None:
    print()
    print(f"Outcome: {result.outcome}" + (f" ({result.detail})" if result.detail else ""))
    answer = result.answer
    if answer is None:
        return
    print()
    if isinstance(answer, QuizItem):
        print(answer.question)
        for i, option in enumerate(answer.options):
            print(f"  {'ABCD'[i]}. {option}{'   <- correct' if i == answer.correct_index else ''}")
        print()
    print(answer.explanation)
    print()
    print("Sources:")
    for citation in answer.citations:
        print(f"  {citation.url}")
        print(f'    "{citation.quote}"')
    check = result.code_check
    if check is not None:
        c = check.citations
        verdict = "pass" if check.passed else "fail"
        numbers = ", ".join(check.unsupported_numbers) or "none"
        print(
            f"\nLayer 1 (code): {verdict} | citations {len(c.kept)} kept, {len(c.unfetched)} "
            f"not read, {len(c.misquoted)} misquoted | unsupported numbers: {numbers}"
        )


def _print_verification(verification: Verification) -> None:
    haiku = verification.haiku
    if haiku is not None:
        print(f"Layer 2 (Haiku): {haiku.verdict} ({haiku.seconds:.1f}s, ${haiku.cost_usd:.4f})")
        for reason in haiku.reasons:
            print(f"    {reason}")
    jev = verification.jev
    if jev is None:
        print("Layer 3 (Jev): skipped (no TYPESAFE_API_KEY)")
        return
    print(
        f"Layer 3 (Jev {jev.model}, threshold {jev.threshold}): {jev.verdict} "
        f"({jev.seconds:.1f}s, {jev.input_tokens} tokens, ${jev.cost_usd:.6f})"
    )
    for reason in jev.reasons:
        print(f"    {reason}")
    for check in jev.checks:
        claim = check.claim
        if len(claim) > 90:
            # Answer and distractor claims end with the option, which is the part that matters.
            claim = "..." + claim[-87:] if check.kind != "sentence" else claim[:87] + "..."
        print(f"    {check.kind:<14} {check.verdict:<12} {check.confidence:.2f}  {claim}")


def _print_totals(record: ItemRecord) -> None:
    run = record.run
    u = run.usage
    anthropic_cost = f"${record.anthropic_cost_usd:.4f}"
    typesafe_cost = f"${record.typesafe_cost_usd:.6f}"
    print(
        f"\nModel calls: {run.model_calls}  Time: {run.seconds:.1f}s  "
        f"Cost: Anthropic {anthropic_cost}, TypeSafe {typesafe_cost}"
    )
    print(
        f"Agent tokens: in {u.input_tokens}, cache write {u.cache_write_tokens}, "
        f"cache read {u.cache_read_tokens}, out {u.output_tokens}"
    )
    if record.status is not None:
        print(f"Publish decision ({record.rule}): {record.status}")


def _save(record: ItemRecord, runs_dir: str) -> Path:
    run = record.run
    slug = re.sub(r"[^a-z0-9]+", "-", run.topic.lower()).strip("-")[:40] or "topic"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = Path(runs_dir) / f"{stamp}-{run.mode}-{run.difficulty}-{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


def make_jev(settings: Settings) -> JevClient | None:
    """A Jev client if a TypeSafe key is configured, otherwise None (layer 3 is skipped)."""
    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        return None
    return TypeSafeJev(settings.jev_model, settings.jev_timeout_seconds)


def main(argv: list[str] | None = None) -> int:
    # Page text can contain characters the Windows console code page cannot encode.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="python -m agent", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    learn = commands.add_parser("learn", help="Research a topic and explain it with sources.")
    learn.add_argument("--verify", action="store_true", help="Also run the Haiku and Jev checks.")
    quiz = commands.add_parser("quiz", help="Research a topic and write one checked quiz item.")
    quiz.add_argument("--no-verify", action="store_true", help="Skip the Haiku and Jev checks.")
    for command in (learn, quiz):
        command.add_argument("topic", help="An astronomy or space topic.")
        command.add_argument("--difficulty", choices=get_args(Difficulty), default="easy")
    args = parser.parse_args(argv)

    settings = load_settings()
    llm = AnthropicProvider(settings.model)
    print(f"{args.command.upper()} {args.topic!r} ({args.difficulty}) with {settings.model}")
    run = run_learn if args.command == "learn" else run_quiz
    result = run(args.topic, args.difficulty, llm, settings, on_step=_print_step)
    _print_answer(result)

    record = ItemRecord(run=result)
    should_verify = args.verify if args.command == "learn" else not args.no_verify
    if should_verify and result.answer is not None and result.code_check is not None:
        print("\nVerifying...", flush=True)
        jev = make_jev(settings)
        verification = verify(
            result.answer, result.code_check, result.cited_pages, llm, jev, settings
        )
        _print_verification(verification)
        record = ItemRecord(
            run=result,
            verification=verification,
            status=decide(verification, DEFAULT_RULE),
            rule=DEFAULT_RULE,
        )
    _print_totals(record)
    print(f"Saved run log: {_save(record, settings.runs_dir)}")
    return 0 if result.outcome == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
