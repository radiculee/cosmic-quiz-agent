"""Command line entry point.

    python -m agent learn "Neutron stars" --difficulty medium

Streams each step as it happens, prints the explanation and run metrics, and saves the full run
as JSON under runs/.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from agent.config import load_settings
from agent.llm import AnthropicProvider
from agent.loop import run_learn
from agent.schemas import Difficulty, RunResult, Step


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


def _print_result(result: RunResult) -> None:
    print()
    print(f"Outcome: {result.outcome}" + (f" ({result.detail})" if result.detail else ""))
    if result.answer is not None:
        print()
        print(result.answer.explanation)
        print()
        print("Sources:")
        for citation in result.answer.citations:
            print(f"  {citation.url}")
            print(f'    "{citation.quote}"')
    check = result.citation_check
    if check is not None:
        print()
        print(
            f"Citations: {len(check.kept)} kept, {len(check.dropped)} dropped, "
            f"{check.quotes_found} of {len(check.kept)} quotes found verbatim"
        )
        for citation in check.dropped:
            print(f"  dropped (not fetched): {citation.url}")
    u = result.usage
    print(
        f"Model calls: {result.model_calls}  Time: {result.seconds:.1f}s  "
        f"Cost: ${result.cost_usd:.4f}"
    )
    print(
        f"Tokens: in {u.input_tokens}, cache write {u.cache_write_tokens}, "
        f"cache read {u.cache_read_tokens}, out {u.output_tokens}"
    )


def _save(result: RunResult, runs_dir: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", result.topic.lower()).strip("-")[:40] or "topic"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = Path(runs_dir) / f"{stamp}-learn-{result.difficulty}-{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    # Page text can contain characters the Windows console code page cannot encode.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="python -m agent", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    learn = commands.add_parser("learn", help="Research a topic and explain it with sources.")
    learn.add_argument("topic", help="An astronomy or space topic.")
    learn.add_argument("--difficulty", choices=get_args(Difficulty), default="easy")
    args = parser.parse_args(argv)

    settings = load_settings()
    llm = AnthropicProvider(settings.model)
    print(f"LEARN {args.topic!r} ({args.difficulty}) with {settings.model}", flush=True)
    result = run_learn(args.topic, args.difficulty, llm, settings, on_step=_print_step)
    _print_result(result)
    print(f"Saved run log: {_save(result, settings.runs_dir)}")
    return 0 if result.outcome == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
