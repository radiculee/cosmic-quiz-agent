"""Command line for the evals. Every paid command prints its cost estimate and asks first.

python -m evals run [--quick] [--workers N] [--yes]
python -m evals seed RUN_DIR [--yes]
python -m evals verify-seeded RUN_DIR [--workers N] [--yes]
python -m evals report RUN_DIR
python -m evals rejev RUN_DIR --criteria astro-1 [--workers N] [--yes]
python -m evals ontopic [--yes]
python -m evals export [--out src/data/evals.json]
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import get_args

from agent.config import JEV_COST_PER_ITEM, JevCriteria, Settings, load_settings
from agent.console import confirm, use_utf8_output
from agent.gate import rescore, rescore_record
from agent.llm import AnthropicProvider, LLMProvider
from agent.schemas import ItemRecord
from agent.topic_check import JevTopicJudge, keyword_judge
from agent.verifiers import JevClient, make_jev, verify
from agent.verify import code_check
from evals import export, ontopic, rejev
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
    items = [rescore_record(r) for r in read_lines(run_dir / ITEMS_FILE, ItemRecord)]
    results_path = run_dir / SEEDED_RESULTS_FILE
    results = (
        [rescore_seeded(r) for r in read_lines(results_path, SeededResult)]
        if results_path.exists()
        else []
    )
    print(f"Report: {write_report(run_dir, items, results)}")
    return 0


def command_rejev(args: argparse.Namespace, settings: Settings) -> int:
    run_dir = Path(args.run_dir)
    criteria: JevCriteria = args.criteria
    # Stored results are re-scored under the current rules, so only the criteria change differs.
    items = [rescore_record(r) for r in read_lines(run_dir / ITEMS_FILE, ItemRecord)]
    results_path = run_dir / SEEDED_RESULTS_FILE
    seeded = (
        [rescore_seeded(r) for r in read_lines(results_path, SeededResult)]
        if results_path.exists()
        else []
    )
    verified = [r for r in items if r.verification is not None]
    total = len(verified) + len(seeded)
    estimate = (
        f"{total} Jev requests: under ${total * JEV_COST_PER_ITEM:.3f} on TypeSafe, "
        "nothing on Anthropic"
    )
    if not confirm(estimate, args.yes):
        return 1
    recheck_settings = settings.model_copy(update={"jev_criteria": criteria})
    jev = make_jev(recheck_settings)
    if jev is None:
        print("TYPESAFE_API_KEY is not set; nothing to re-check.")
        return 1

    items_writer = JsonLinesWriter(run_dir / rejev.items_file(criteria))
    items_writer.path.unlink(missing_ok=True)
    seeded_writer = JsonLinesWriter(run_dir / rejev.seeded_file(criteria))
    seeded_writer.path.unlink(missing_ok=True)

    stored = {(r.run.topic, r.run.difficulty): r for r in verified}

    def item_done(record: ItemRecord) -> None:
        items_writer.write(record)
        old = stored[(record.run.topic, record.run.difficulty)]
        print(
            f"  {record.run.difficulty:<6} {record.run.topic[:40]:<40} "
            f"jev {_jev_verdict(old)} -> {_jev_verdict(record)}",
            flush=True,
        )

    def seeded_done(result: SeededResult) -> None:
        seeded_writer.write(result)
        jev_report = result.verification.jev
        print(f"  {result.seeded.id:<22} jev {jev_report.verdict if jev_report else '-'}")

    print(f"Re-checking {len(verified)} generated items with Jev ({criteria})...")
    new_items = rejev.recheck_all(
        verified, lambda r: rejev.recheck_item(r, jev, recheck_settings), args.workers, item_done
    )
    print(f"Re-checking {len(seeded)} planted-fault items...")
    new_seeded = rejev.recheck_all(
        seeded,
        lambda r: rejev.recheck_seeded(r, jev, recheck_settings),
        args.workers,
        seeded_done,
    )
    path = rejev.write_comparison(
        run_dir, criteria, rejev.stored_criteria(verified), verified, new_items, seeded, new_seeded
    )
    print(f"Comparison: {path}")
    return 0


def command_ontopic(args: argparse.Namespace, settings: Settings) -> int:
    cases = ontopic.CASES
    if not confirm(
        f"{len(cases)} Jev requests: under $0.002 on TypeSafe, nothing on Anthropic", args.yes
    ):
        return 1
    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        print("TYPESAFE_API_KEY is not set; nothing to check.")
        return 1
    jev = JevTopicJudge(
        settings.jev_model, settings.jev_timeout_seconds, settings.jev_input_per_mtok
    )
    results = {
        "keywords": ontopic.judge_all(cases, keyword_judge),
        "jev": ontopic.judge_all(cases, jev.judge),
    }
    print(f"{'input':<58} {'want':<7} {'keywords':<9} {'jev':<7} on_topic  plain")
    for kw, jv in zip(results["keywords"], results["jev"], strict=True):
        want = "accept" if kw.case.accept else "reject"
        scores = (
            f"{jv.verdict.on_topic:8.2f} {jv.verdict.plain:6.2f}" if jv.verdict else "   (cleaning)"
        )
        print(
            f"{kw.case.text[:57]:<58} {want:<7} {'ok' if kw.right else 'WRONG':<9} "
            f"{'ok' if jv.right else 'WRONG':<7} {scores}"
        )
    for name, outcomes in results.items():
        print(f"{name}: {ontopic.summary(outcomes)}")
    cost = sum(o.verdict.cost_usd for o in results["jev"] if o.verdict)
    seconds = [o.verdict.seconds for o in results["jev"] if o.verdict]
    print(f"Jev cost ${cost:.5f}, median {sorted(seconds)[len(seconds) // 2]:.2f} s per check")
    path = new_run_dir("ontopic") / "ontopic.json"
    ontopic.write_results(path, results)
    print(f"Saved {path}")
    return 0


def command_export(args: argparse.Namespace, settings: Settings) -> int:
    history = export.collect()
    path = export.write_history(history, Path(args.out))
    print(
        f"Wrote {len(history.generation)} eval run(s) and {len(history.ontopic)} on-topic "
        f"check(s) to {path}"
    )
    return 0


def rescore_seeded(result: SeededResult) -> SeededResult:
    return result.model_copy(update={"verification": rescore(result.verification)})


def _jev_verdict(record: ItemRecord) -> str:
    v = record.verification
    return v.jev.verdict if v is not None and v.jev is not None else "-"


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
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

    recheck = commands.add_parser(
        "rejev", help="Re-run only Jev on stored items with another criteria wording (TypeSafe)."
    )
    recheck.add_argument("run_dir")
    recheck.add_argument("--criteria", choices=get_args(JevCriteria), required=True)
    recheck.add_argument("--workers", type=int, default=4)
    recheck.add_argument("--yes", action="store_true")

    on_topic = commands.add_parser(
        "ontopic", help="Measure the custom-topic check: Jev against keywords (TypeSafe)."
    )
    on_topic.add_argument("--yes", action="store_true")

    history = commands.add_parser(
        "export", help="Write the eval history for the analytics page (free)."
    )
    history.add_argument("--out", default=str(export.DEFAULT_OUT))

    args = parser.parse_args(argv)
    settings = load_settings()
    handlers = {
        "run": command_run,
        "seed": command_seed,
        "verify-seeded": command_verify_seeded,
        "report": command_report,
        "rejev": command_rejev,
        "ontopic": command_ontopic,
        "export": command_export,
    }
    return handlers[args.command](args, settings)


if __name__ == "__main__":
    sys.exit(main())
