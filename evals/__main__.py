"""Command line for the evals. Every paid command prints its cost estimate and asks first.

python -m evals run [--quick] [--workers N] [--yes]
python -m evals seed RUN_DIR [--yes]
python -m evals verify-seeded RUN_DIR [--workers N] [--yes]
python -m evals report RUN_DIR
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from agent.__main__ import make_jev
from agent.config import Settings, load_settings
from agent.llm import AnthropicProvider, LLMProvider
from agent.schemas import ItemRecord
from agent.verifiers import JevClient, verify
from agent.verify import code_check
from evals.report import write_report
from evals.runner import estimate, new_run_dir, run_eval
from evals.seeding import FAULT_TYPES, PER_FAULT, SeededItem, SeededResult, build_seeded_set
from evals.store import ITEMS_FILE, SEEDED_FILE, SEEDED_RESULTS_FILE, JsonLinesWriter, read_lines
from evals.topics import DIFFICULTIES, QUICK_TOPICS, TOPICS

# More retries than the CLI: an eval sends many requests and may meet rate limits.
EVAL_MAX_RETRIES = 6
SEED_COST_ESTIMATE = "about $0.05 to $0.10 on Anthropic (20 short Haiku calls)"
VERIFY_SEEDED_ESTIMATE = (
    f"{len(FAULT_TYPES) * PER_FAULT} items: about $0.20 to $0.35 on Anthropic (Haiku verifier) "
    "and under $0.02 on TypeSafe (Jev)"
)


def confirm(message: str, assume_yes: bool) -> bool:
    print(f"Estimated cost: {message}")
    if assume_yes:
        return True
    try:
        return input("Continue? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:  # no terminal to answer from: treat as no
        print("\nNo answer; stopping. Pass --yes to approve the cost in advance.")
        return False


def _clients(settings: Settings) -> tuple[LLMProvider, JevClient | None]:
    llm = AnthropicProvider(settings.model, max_retries=EVAL_MAX_RETRIES)
    jev = make_jev(settings)
    if jev is None:
        print("TYPESAFE_API_KEY is not set: layer 3 (Jev) will be skipped.")
    return llm, jev


def command_run(args: argparse.Namespace, settings: Settings) -> int:
    topics = QUICK_TOPICS if args.quick else TOPICS
    if not confirm(estimate(len(topics) * len(DIFFICULTIES)), args.yes):
        return 1
    llm, jev = _clients(settings)
    out_dir = new_run_dir("quick" if args.quick else "full")
    print(f"Writing results to {out_dir}")
    items_path = run_eval(topics, DIFFICULTIES, llm, jev, settings, out_dir, args.workers)
    items = list(read_lines(items_path, ItemRecord))
    print(f"Report: {write_report(out_dir, items, [])}")
    return 0


def command_seed(args: argparse.Namespace, settings: Settings) -> int:
    run_dir = Path(args.run_dir)
    if not confirm(SEED_COST_ESTIMATE, args.yes):
        return 1
    llm, _ = _clients(settings)
    records = list(read_lines(run_dir / ITEMS_FILE, ItemRecord))
    seeded_path = run_dir / SEEDED_FILE
    seeded_path.unlink(missing_ok=True)
    writer = JsonLinesWriter(seeded_path)

    def report(item: SeededItem) -> None:
        writer.write(item)
        print(f"  {item.id}: {item.topic} ({item.difficulty}) - {item.description[:90]}")

    seeded, cost = build_seeded_set(records, llm, settings, on_item=report)
    counts = {fault: sum(1 for s in seeded if s.fault == fault) for fault in FAULT_TYPES}
    print(f"Planted {len(seeded)} faults {counts}, writing cost ${cost:.3f}. Saved {seeded_path}")
    return 0


def _verify_seeded(
    seeded: SeededItem, llm: LLMProvider, jev: JevClient | None, settings: Settings
) -> SeededResult:
    code = code_check(seeded.item, seeded.fetched)
    # Layers 2 and 3 always run, so each layer's catch rate is measured on its own.
    verification = verify(seeded.item, code, seeded.pages, llm, jev, settings)
    haiku_cost = verification.haiku.cost_usd if verification.haiku else 0.0
    jev_cost = verification.jev.cost_usd if verification.jev else 0.0
    return SeededResult(
        seeded=seeded,
        verification=verification,
        anthropic_cost_usd=haiku_cost,
        typesafe_cost_usd=jev_cost,
    )


def command_verify_seeded(args: argparse.Namespace, settings: Settings) -> int:
    run_dir = Path(args.run_dir)
    seeded = list(read_lines(run_dir / SEEDED_FILE, SeededItem))
    if not confirm(
        VERIFY_SEEDED_ESTIMATE.replace(
            f"{len(FAULT_TYPES) * PER_FAULT} items", f"{len(seeded)} items"
        ),
        args.yes,
    ):
        return 1
    llm, jev = _clients(settings)
    results_path = run_dir / SEEDED_RESULTS_FILE
    results_path.unlink(missing_ok=True)
    writer = JsonLinesWriter(results_path)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(lambda s: _verify_seeded(s, llm, jev, settings), seeded):
            writer.write(result)
            v = result.verification
            layer1 = "pass" if v.code.passed else "fail"
            haiku = v.haiku.verdict if v.haiku else "-"
            jev_verdict = v.jev.verdict if v.jev else "-"
            print(
                f"  {result.seeded.id:<22} layer1={layer1:<5} haiku={haiku:<10} jev={jev_verdict}",
                flush=True,
            )
    return command_report(args, settings)


def command_report(args: argparse.Namespace, settings: Settings) -> int:
    run_dir = Path(args.run_dir)
    items = list(read_lines(run_dir / ITEMS_FILE, ItemRecord))
    results_path = run_dir / SEEDED_RESULTS_FILE
    results = list(read_lines(results_path, SeededResult)) if results_path.exists() else []
    print(f"Report: {write_report(run_dir, items, results)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m evals", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="Generate and verify quiz items for the fixed topics.")
    run.add_argument("--quick", action="store_true", help=f"Only {len(QUICK_TOPICS)} topics.")
    run.add_argument("--workers", type=int, default=2)
    run.add_argument("--yes", action="store_true", help="Skip the cost confirmation.")

    seed = commands.add_parser("seed", help="Plant faults into items from a run.")
    seed.add_argument("run_dir")
    seed.add_argument("--yes", action="store_true")

    verify_seeded = commands.add_parser("verify-seeded", help="Run every layer on planted faults.")
    verify_seeded.add_argument("run_dir")
    verify_seeded.add_argument("--workers", type=int, default=2)
    verify_seeded.add_argument("--yes", action="store_true")

    report = commands.add_parser("report", help="Rebuild the report from stored results (free).")
    report.add_argument("run_dir")

    args = parser.parse_args(argv)
    settings = load_settings()
    handlers = {
        "run": command_run,
        "seed": command_seed,
        "verify-seeded": command_verify_seeded,
        "report": command_report,
    }
    return handlers[args.command](args, settings)


if __name__ == "__main__":
    sys.exit(main())
