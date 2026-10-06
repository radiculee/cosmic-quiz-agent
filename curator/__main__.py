"""The Curator: fills the question bank in Supabase.

python -m curator build [--topics N] [--cap USD] [--workers N] [--yes]
python -m curator daily [--cap USD] [--workers N] [--yes]
python -m curator review [--mode learn|quiz] [--difficulty easy|medium|hard]
python -m curator upkeep
python -m curator rejev [--yes]

Every paid run prints its cost estimate and asks before spending anything, unless --yes approves
it in advance (as the scheduled run will). The cap is hard: work starts only if the most it can
cost still fits under it.

build researches the approved evergreen topics (curator/topics.py) in LEARN and QUIZ at every
difficulty. It can be re-run: jobs already in the bank are skipped, so an interrupted or capped
build continues where it stopped. daily first finishes a recent news topic that an earlier run
left incomplete; otherwise it picks one new topic from the NASA and ESA news feeds. Either way it
runs the same pipeline and retires news items past their date. review shows each item the
gate sent to review, with its sources, and publishes or discards it on your decision (free).
upkeep does the free part of a daily run only: it stores runs an earlier run left on disk and
retires news items past their date, with no model calls. The scheduled workflow runs it on days
without a paid run, which also keeps the free database from pausing for inactivity.
rejev re-runs Jev on items the gate sent to review because their Jev check failed (an outage or
a wrong key), from the page text stored with each run, and applies the same gate rule again.
It costs a fraction of a cent on TypeSafe and nothing on Anthropic.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from agent.config import JEV_COST_PER_ITEM, Settings, load_settings
from agent.console import confirm, use_utf8_output
from agent.gate import decide
from agent.llm import AnthropicProvider
from agent.schemas import Difficulty, Mode
from agent.store import CuratorSummary, StoreError, SupabaseStore, TopicRef
from agent.tools import ToolContext, make_http_client
from agent.verifiers import make_jev
from agent.verifiers.jev import verify_with_jev
from curator.discover import MAX_COST_USD as DISCOVERY_MAX_COST_USD
from curator.discover import discover, read_news
from curator.pipeline import (
    DIFFICULTIES,
    JOB_COST_TYPICAL,
    MODES,
    Budget,
    Curator,
    Job,
    estimate,
    flush_pending,
    job_cost_limit,
)
from curator.review import review
from curator.topics import BUILD_TOPICS

# More retries than the CLI: a Curator run sends many requests and may meet rate limits.
CURATOR_MAX_RETRIES = 6
BUILD_CAP_USD = 6.00  # approved 2026-10-02 for the 30-topic build (estimate about $5)
DAILY_CAP_USD = 0.40  # approved 2026-10-02 for one news topic a day (estimate about $0.17)
DEFAULT_WORKERS = 3
DISCOVERY_COST_TYPICAL = 0.004  # one short Haiku call over the feed headlines
RESUME_LOOKBACK = 7  # recent news topics checked for jobs an earlier daily run left unfinished


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def _positive_float(text: str) -> float:
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be more than 0")
    return value


def _describe(jobs: list[Job], skipped: int, cap: float, settings: Settings) -> str:
    typical, worst = estimate(jobs, settings)
    return (
        f"{len(jobs)} jobs ({skipped} already in the bank): about ${typical:.2f} on Anthropic, "
        f"at most ${min(worst, cap):.2f} (hard cap ${cap:.2f}); under "
        f"${len(jobs) * JEV_COST_PER_ITEM:.3f} on TypeSafe (Jev)."
    )


def _describe_daily(cap: float, settings: Settings) -> str:
    jobs = len(MODES) * len(DIFFICULTIES)
    typical = DISCOVERY_COST_TYPICAL + len(DIFFICULTIES) * sum(JOB_COST_TYPICAL.values())
    worst = DISCOVERY_MAX_COST_USD + jobs * job_cost_limit(settings)
    return (
        f"one news topic (finishing an earlier one, or choosing a new one) and up to {jobs} jobs "
        f"on it: about ${typical:.2f} on Anthropic, at "
        f"most ${min(worst, cap):.2f} (hard cap ${cap:.2f}); under "
        f"${jobs * JEV_COST_PER_ITEM:.3f} on TypeSafe (Jev)."
    )


def _print_summary(summary: CuratorSummary) -> None:
    print(
        f"\nDone: {summary.jobs_run} jobs run, {summary.published} published, "
        f"{summary.review} for review, {summary.discarded} discarded, {summary.no_item} without "
        f"an item, {summary.retired} retired."
    )
    print(
        f"Spent: Anthropic ${summary.anthropic_cost_usd:.4f}, "
        f"TypeSafe ${summary.typesafe_cost_usd:.6f}"
    )


def _curator(store: SupabaseStore, settings: Settings) -> Curator | None:
    jev = make_jev(settings)
    if jev is None:
        # Without Jev every item would go to review and players would see no source check.
        print("TYPESAFE_API_KEY is not set: the Curator needs Jev (layer 3). Stopping.")
        return None
    llm = AnthropicProvider(settings.model, max_retries=CURATOR_MAX_RETRIES)
    pending_dir = Path(settings.runs_dir) / "curator" / "pending"
    return Curator(store, llm, jev, settings, pending_dir)


def command_build(args: argparse.Namespace, settings: Settings, store: SupabaseStore) -> int:
    curator = _curator(store, settings)
    if curator is None:
        return 1
    curator.flush_pending()
    names = BUILD_TOPICS[: args.topics] if args.topics else BUILD_TOPICS
    topics = [TopicRef(name=name, kind="evergreen") for name in names]
    jobs, skipped = curator.plan(topics)
    print(f"Build: {len(topics)} topics x 2 modes x 3 difficulties.")
    if not jobs:
        print("Every job is already in the bank; nothing to do.")
        return 0
    if not confirm(_describe(jobs, skipped, args.cap, settings), args.yes):
        return 1
    summary = curator.run("build", topics, jobs, skipped, Budget(args.cap), args.workers)
    _print_summary(summary)
    return 0


def _unfinished_news_topic(
    curator: Curator, existing: Sequence[TopicRef], now: datetime
) -> tuple[TopicRef, list[Job], int] | None:
    """The most recent live news topic that an earlier daily run left with jobs to do (for
    example because it reached its cap), with those jobs and how many were already done."""
    recent = [
        topic
        for topic in existing
        if topic.kind == "news" and (topic.retire_after is None or topic.retire_after > now)
    ][:RESUME_LOOKBACK]
    jobs, _ = curator.plan(recent)
    if not jobs:
        return None
    topic = jobs[0].topic
    left = [job for job in jobs if job.topic == topic]
    return topic, left, len(MODES) * len(DIFFICULTIES) - len(left)


def command_daily(args: argparse.Namespace, settings: Settings, store: SupabaseStore) -> int:
    curator = _curator(store, settings)
    if curator is None:
        return 1
    curator.flush_pending()
    # Everything a daily run can cost is known before the topic is chosen, so ask first.
    if not confirm(_describe_daily(args.cap, settings), args.yes):
        return 1
    budget = Budget(args.cap)
    now = datetime.now(UTC)
    existing = store.topics()
    unfinished = _unfinished_news_topic(curator, existing, now)
    if unfinished is not None:
        left_topic, left_jobs, done = unfinished
        curator.say(
            f"Finishing {len(left_jobs)} job(s) an earlier run left on {left_topic.name!r}."
        )
        summary = curator.run("daily", [left_topic], left_jobs, done, budget, args.workers)
        _print_summary(summary)
        return 0

    if not budget.try_reserve(DISCOVERY_MAX_COST_USD):
        print(f"The cap of ${args.cap:.2f} is too small to choose a topic.")
        return 1
    with make_http_client(settings) as http:
        ctx = ToolContext(settings=settings, http=http)
        items = read_news(ctx, curator.say)
        discovery = discover(items, existing, curator.llm, settings, ctx, now)
    budget.settle(DISCOVERY_MAX_COST_USD, discovery.cost_usd)
    usage = discovery.usage
    curator.say(
        f"Discover: topic choice used {usage.total_input_tokens} input and "
        f"{usage.output_tokens} output tokens (${discovery.cost_usd:.4f})"
    )
    for note in discovery.notes:
        curator.say(f"Discover: {note}")

    topics: list[TopicRef] = []
    jobs: list[Job] = []
    skipped = 0
    if discovery.topic is None:
        curator.say("No new topic today; retiring stale items only.")
    else:
        topic = discovery.topic
        curator.say(f"Discover: chose {topic.name!r} from {topic.lead_url}")
        topics = [topic]
        jobs, skipped = curator.plan(topics)
    summary = curator.run("daily", topics, jobs, skipped, budget, args.workers)
    _print_summary(summary)
    return 0


def command_upkeep(args: argparse.Namespace, settings: Settings, store: SupabaseStore) -> int:
    pending_dir = Path(settings.runs_dir) / "curator" / "pending"
    flush_pending(store, pending_dir, print)
    retired = store.retire_stale()
    print(f"Upkeep: retired {retired} stale item(s). No model calls; nothing spent.")
    return 0


def command_rejev(args: argparse.Namespace, settings: Settings, store: SupabaseStore) -> int:
    targets = store.jev_recheck_targets()
    if not targets:
        print("No item is waiting on a failed Jev check.")
        return 0
    estimate = (
        f"{len(targets)} Jev requests: under ${len(targets) * JEV_COST_PER_ITEM:.3f} on TypeSafe, "
        "nothing on Anthropic"
    )
    if not confirm(estimate, args.yes):
        return 1
    jev = make_jev(settings)
    if jev is None:
        print("TYPESAFE_API_KEY is not set; nothing to re-check.")
        return 1
    failed = 0
    spent = 0.0
    for target in targets:
        record = target.record
        answer = record.run.answer
        label = f"item {target.item_id} {record.run.mode} {record.run.difficulty} {target.topic}"
        if answer is None or record.verification is None or not target.pages:
            print(f"{label}: nothing to re-check (no answer, verification or stored pages)")
            failed += 1
            continue
        report = verify_with_jev(answer, target.pages, jev, settings)
        if report.verdict == "error":
            print(f"{label}: Jev failed again: {report.reasons[0] if report.reasons else ''}")
            failed += 1
            continue
        status = decide(record.verification.model_copy(update={"jev": report}))
        store.apply_jev_recheck(target.item_id, status, report)
        spent += report.cost_usd
        print(f"{label}: Jev {report.verdict} -> {status} (${report.cost_usd:.5f})")
    print(f"Re-checked {len(targets) - failed} of {len(targets)}. Spent: TypeSafe ${spent:.6f}.")
    return 1 if failed else 0


def command_review(args: argparse.Namespace, settings: Settings, store: SupabaseStore) -> int:
    items = [
        item
        for item in store.review_queue()
        if (args.mode is None or item.mode == args.mode)
        and (args.difficulty is None or item.difficulty == args.difficulty)
    ]
    if not items:
        print("Nothing to review.")
        return 0
    print(f"{len(items)} item(s) in review. Source URLs can be opened with Ctrl+click.")
    tally = review(store, items, input, print)
    print(
        f"\nPublished {tally.published}, discarded {tally.discarded}, skipped {tally.skipped}"
        + (f", {tally.changed_elsewhere} changed elsewhere" if tally.changed_elsewhere else "")
        + "."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
    parser = argparse.ArgumentParser(prog="python -m curator", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Research the approved evergreen topics.")
    build.add_argument(
        "--topics", type=_positive_int, help="Only the first N topics (default: all)."
    )
    build.add_argument(
        "--cap", type=_positive_float, default=BUILD_CAP_USD, help="Anthropic cap in USD."
    )

    daily = commands.add_parser("daily", help="Add one topic from the news and retire old items.")
    daily.add_argument(
        "--cap", type=_positive_float, default=DAILY_CAP_USD, help="Anthropic cap in USD."
    )

    for command in (build, daily):
        command.add_argument("--workers", type=_positive_int, default=DEFAULT_WORKERS)
        command.add_argument("--yes", action="store_true", help="Approve the cost in advance.")

    queue = commands.add_parser("review", help="Publish or discard the items in review (free).")
    queue.add_argument("--mode", choices=get_args(Mode))
    queue.add_argument("--difficulty", choices=get_args(Difficulty))
    commands.add_parser("upkeep", help="Store left-over runs and retire stale items (free).")
    rejev = commands.add_parser(
        "rejev", help="Re-run Jev on items whose Jev check failed (TypeSafe, under a cent)."
    )
    rejev.add_argument("--yes", action="store_true", help="Approve the cost in advance.")
    args = parser.parse_args(argv)

    settings = load_settings()
    handlers = {
        "build": command_build,
        "daily": command_daily,
        "review": command_review,
        "upkeep": command_upkeep,
        "rejev": command_rejev,
    }
    try:
        with SupabaseStore.from_env() as store:
            return handlers[args.command](args, settings, store)
    except StoreError as error:
        print(f"Bank error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
