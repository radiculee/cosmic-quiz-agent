"""The Curator: fills the question bank in Supabase.

python -m curator build [--topics N] [--cap USD] [--workers N] [--yes]
python -m curator daily [--cap USD] [--workers N] [--yes]
python -m curator complete [--cap USD] [--workers N] [--yes]
python -m curator review [--mode learn|quiz] [--difficulty easy|medium|hard] [--reported]
python -m curator upkeep
python -m curator rejev [--yes]

Every paid run prints its cost estimate and asks before spending anything, unless --yes approves
it in advance (as the scheduled run will). The cap is hard: work starts only if the most it can
cost still fits under it.

build researches the approved evergreen topics (curator/topics.py) in LEARN and QUIZ at every
difficulty. It can be re-run: jobs already in the bank are skipped, so an interrupted or capped
build continues where it stopped. daily first fills up to six slots (a mode at a difficulty) that
listed topics still lack, oldest topic first: a live search's leftovers, or a news topic an
earlier run stopped on. Then it picks one new topic from the NASA and ESA news feeds, if the cap
still allows. Either way it runs the same pipeline and retires news items past their date.
complete fills every missing slot at once, under its cap, and reports what is still missing.
Learn and Quiz list a topic only once it has every slot (decided 2026-10-28); a slot is tried at
most three times, and one with an item in review waits for the review queue.
review shows each item the gate sent to review, with its sources, and publishes or discards it
on your decision (free); with --reported it shows the published items that players' reports
have hidden instead, to keep or discard. upkeep does the free part of a daily run only: it stores
runs an earlier run left on disk and retires news items past their date, with no model calls.
The scheduled workflow runs it on days without a paid run, which also keeps the free database
from pausing for inactivity. Both daily and upkeep clear visitor hashes past their time
(migration 008).
rejev re-runs Jev on items the gate sent to review because their Jev check failed (an outage or
a wrong key), from the page text stored with each run, and applies the same gate rule again.
It costs a fraction of a cent on TypeSafe and nothing on Anthropic.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from agent.config import JEV_COST_PER_ITEM, Settings, load_settings
from agent.console import confirm, use_utf8_output
from agent.gate import decide
from agent.llm import AnthropicProvider
from agent.schemas import Difficulty, Mode
from agent.store import CuratorSummary, MissingSlot, StoreError, SupabaseStore, TopicRef
from agent.tools import ToolContext, make_http_client
from agent.verifiers import make_jev
from agent.verifiers.jev import verify_with_jev
from curator.discover import MAX_COST_USD as DISCOVERY_MAX_COST_USD
from curator.discover import discover, read_news
from curator.pipeline import (
    DIFFICULTIES,
    JOB_COST_TYPICAL,
    MAX_SLOT_ATTEMPTS,
    MODES,
    Budget,
    Curator,
    Job,
    can_retry,
    estimate,
    flush_pending,
    job_cost_limit,
    open_jobs,
)
from curator.review import review, review_reported
from curator.topics import BUILD_TOPICS

# More retries than the CLI: a Curator run sends many requests and may meet rate limits.
CURATOR_MAX_RETRIES = 6
BUILD_CAP_USD = 6.00  # approved 2026-10-02 for the 30-topic build (estimate about $5)
DAILY_CAP_USD = 0.40  # approved 2026-10-02 for one news topic a day (estimate about $0.17)
COMPLETE_CAP_USD = 3.00  # approved 2026-10-28 for the 67 missing slots (estimate about $2)
DEFAULT_WORKERS = 3
DISCOVERY_COST_TYPICAL = 0.004  # one short Haiku call over the feed headlines
# Missing slots a daily run fills before its news topic: one topic's worth, about $0.17 typical
# (decided 2026-10-28). The rest of the cap goes to the news topic, and whatever the cap stops
# is filled the next day.
FINISH_JOBS_PER_DAY = 6


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


def _describe(jobs: list[Job], note: str, cap: float, settings: Settings) -> str:
    typical, worst = estimate(jobs, settings)
    return (
        f"{len(jobs)} jobs ({note}): about ${typical:.2f} on Anthropic, "
        f"at most ${min(worst, cap):.2f} (hard cap ${cap:.2f}); under "
        f"${len(jobs) * JEV_COST_PER_ITEM:.3f} on TypeSafe (Jev)."
    )


def _describe_daily(cap: float, settings: Settings) -> str:
    topic_jobs = len(MODES) * len(DIFFICULTIES)
    jobs = FINISH_JOBS_PER_DAY + topic_jobs
    typical = DISCOVERY_COST_TYPICAL + len(DIFFICULTIES) * sum(JOB_COST_TYPICAL.values())
    worst = DISCOVERY_MAX_COST_USD + jobs * job_cost_limit(settings)
    return (
        f"up to {FINISH_JOBS_PER_DAY} missing slots on listed topics, then one new news topic "
        f"and up to {topic_jobs} jobs on it, while the cap allows: about ${typical:.2f} on "
        f"Anthropic for a topic's worth, at most ${min(worst, cap):.2f} (hard cap ${cap:.2f}); "
        f"under ${jobs * JEV_COST_PER_ITEM:.3f} on TypeSafe (Jev)."
    )


def _topics_of(jobs: Sequence[Job]) -> list[TopicRef]:
    """The jobs' topics, each once, in the jobs' order."""
    return list({job.topic.name.casefold(): job.topic for job in jobs}.values())


def _slot_label(slot: MissingSlot) -> str:
    if slot.in_review:
        state = "in review"
    elif slot.attempts >= MAX_SLOT_ATTEMPTS:
        state = f"out of tries, {slot.attempts}"
    else:
        state = f"{slot.attempts} {'try' if slot.attempts == 1 else 'tries'}"
    return f"{slot.mode} {slot.difficulty} ({state})"


def report_missing(
    before: Sequence[MissingSlot], after: Sequence[MissingSlot], say: Callable[[str], None]
) -> None:
    """The topics a run completed, and every slot still missing, grouped by topic."""
    still = {slot.topic.name for slot in after}
    completed = sorted({slot.topic.name for slot in before} - still, key=str.casefold)
    say(f"Now on every level: {len(completed)} more topic(s).")
    for name in completed:
        say(f"  {name}")
    if not after:
        say("No slot is missing: every listed topic is on every level.")
        return
    retry = sum(1 for slot in after if can_retry(slot))
    review = sum(1 for slot in after if slot.in_review)
    out = len(after) - retry - review
    say(
        f"Still missing: {len(after)} slot(s) on {len(still)} topic(s), which stay off Learn and "
        f"Quiz until filled: {retry} to retry, {review} in review (python -m curator review), "
        f"{out} out of tries (for a person to look at)."
    )
    by_topic: dict[str, list[str]] = {}
    for slot in after:
        by_topic.setdefault(slot.topic.name, []).append(_slot_label(slot))
    for name, labels in by_topic.items():
        say(f"  {name}: {', '.join(labels)}")


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
    if not confirm(_describe(jobs, f"{skipped} already in the bank", args.cap, settings), args.yes):
        return 1
    summary = curator.run("build", topics, jobs, skipped, Budget(args.cap), args.workers)
    _print_summary(summary)
    return 0


def command_complete(args: argparse.Namespace, settings: Settings, store: SupabaseStore) -> int:
    curator = _curator(store, settings)
    if curator is None:
        return 1
    curator.flush_pending()
    before = store.missing_slots()
    jobs = open_jobs(before)
    held = len(before) - len(jobs)
    print(
        f"Complete: {len(before)} slot(s) missing on {len({s.topic.name for s in before})} "
        f"topic(s); {len(jobs)} can run, {held} held (in review, or tried "
        f"{MAX_SLOT_ATTEMPTS} times)."
    )
    if not jobs:
        report_missing(before, before, print)
        return 0
    if not confirm(_describe(jobs, f"{held} held", args.cap, settings), args.yes):
        return 1
    summary = curator.run("complete", _topics_of(jobs), jobs, held, Budget(args.cap), args.workers)
    _print_summary(summary)
    report_missing(before, store.missing_slots(), print)
    return 0


def purge_visitor_hashes(store: SupabaseStore) -> int:
    """Clear visitor hashes past their time, every day whatever else the run did, so the
    retention holds without traffic (docs/SECURITY_AUDIT.md S13). Free. Returns 1 if it failed,
    so the scheduled run shows the failure."""
    try:
        purged = store.purge_visitor_hashes()
    except StoreError as error:
        print(f"Visitor hashes were not cleared: {error}")
        return 1
    print(
        f"Privacy: cleared {purged.runs} live-run and {purged.reports} report visitor hash(es); "
        f"deleted {purged.rate_limit_windows} old request window(s)."
    )
    return 0


def command_daily(args: argparse.Namespace, settings: Settings, store: SupabaseStore) -> int:
    status = _daily(args, settings, store)
    return max(status, purge_visitor_hashes(store))


def _daily(args: argparse.Namespace, settings: Settings, store: SupabaseStore) -> int:
    curator = _curator(store, settings)
    if curator is None:
        return 1
    curator.flush_pending()
    # Everything a daily run can cost is known before the topic is chosen, so ask first.
    if not confirm(_describe_daily(args.cap, settings), args.yes):
        return 1
    budget = Budget(args.cap)
    now = datetime.now(UTC)
    # Listed topics' missing slots run before the news topic's jobs, so a live search's topic
    # reaches Learn and Quiz by the next day (decided 2026-10-28).
    jobs = open_jobs(store.missing_slots(), FINISH_JOBS_PER_DAY)
    topics = _topics_of(jobs)
    if jobs:
        curator.say(
            f"Finishing {len(jobs)} missing slot(s) on: {', '.join(t.name for t in topics)}."
        )

    if not budget.try_reserve(DISCOVERY_MAX_COST_USD):
        print(f"The cap of ${args.cap:.2f} is too small to choose a topic.")
        return 1
    existing = store.topics()
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

    skipped = 0
    if discovery.topic is None:
        curator.say("No new topic today.")
    else:
        topic = discovery.topic
        curator.say(f"Discover: chose {topic.name!r} from {topic.lead_url}")
        news_jobs, skipped = curator.plan([topic])
        topics.append(topic)
        jobs += news_jobs
    summary = curator.run("daily", topics, jobs, skipped, budget, args.workers)
    _print_summary(summary)
    return 0


def command_upkeep(args: argparse.Namespace, settings: Settings, store: SupabaseStore) -> int:
    pending_dir = Path(settings.runs_dir) / "curator" / "pending"
    flush_pending(store, pending_dir, print)
    retired = store.retire_stale()
    print(f"Upkeep: retired {retired} stale item(s). No model calls; nothing spent.")
    return purge_visitor_hashes(store)


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
    queue = store.reported_queue() if args.reported else store.review_queue()
    items = [
        item
        for item in queue
        if (args.mode is None or item.mode == args.mode)
        and (args.difficulty is None or item.difficulty == args.difficulty)
    ]
    if not items:
        print("No item is hidden by reports." if args.reported else "Nothing to review.")
        return 0
    where = "hidden by reports" if args.reported else "in review"
    print(f"{len(items)} item(s) {where}. Source URLs can be opened with Ctrl+click.")
    if args.reported:
        tally = review_reported(store, items, input, print)
        done = f"Kept {tally.kept}, discarded {tally.discarded}, skipped {tally.skipped}"
    else:
        tally = review(store, items, input, print)
        done = f"Published {tally.published}, discarded {tally.discarded}, skipped {tally.skipped}"
    print(
        f"\n{done}"
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

    complete = commands.add_parser(
        "complete", help="Fill every slot a listed topic lacks, so it is on every level."
    )
    complete.add_argument(
        "--cap", type=_positive_float, default=COMPLETE_CAP_USD, help="Anthropic cap in USD."
    )

    for command in (build, daily, complete):
        command.add_argument("--workers", type=_positive_int, default=DEFAULT_WORKERS)
        command.add_argument("--yes", action="store_true", help="Approve the cost in advance.")

    queue = commands.add_parser("review", help="Publish or discard the items in review (free).")
    queue.add_argument("--mode", choices=get_args(Mode))
    queue.add_argument("--difficulty", choices=get_args(Difficulty))
    queue.add_argument(
        "--reported",
        action="store_true",
        help="Keep or discard the published items that players' reports have hidden instead.",
    )
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
        "complete": command_complete,
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
