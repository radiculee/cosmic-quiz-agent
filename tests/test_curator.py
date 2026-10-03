"""The Curator's planning, dollar cap, storage and news discovery: an in-memory bank and scripted
models, no network and no paid calls."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agent.config import Settings
from agent.console import slugify
from agent.llm import LLMError, Usage
from agent.schemas import ItemRecord, Status
from agent.store import (
    CuratorSummary,
    CuratorTrigger,
    ItemPayload,
    JobKey,
    RecordedIds,
    StoreError,
    TopicRef,
    build_payload,
    job_key,
)
from agent.tools import ToolContext
from agent.tools.feeds import parse_rss
from curator import pipeline
from curator.__main__ import _positive_float, _positive_int, _unfinished_news_topic
from curator.discover import NewsPick, choose, discover, read_news
from curator.pipeline import (
    Budget,
    Curator,
    Job,
    estimate,
    job_cost_limit,
    plan_jobs,
    run_jobs,
)
from curator.topics import BUILD_TOPICS, NEWS_RETIRE_DAYS
from evals.topics import TOPICS as EVAL_TOPICS
from tests.conftest import FakeLLM, FakeWeb
from tests.test_store import quiz_record

QUASARS = TopicRef(name="Quasars", kind="evergreen")
MAGNETARS = TopicRef(name="Magnetars", kind="evergreen")


class MemoryStore:
    """The `Store` interface in memory, with switches to simulate failures."""

    def __init__(self, attempted: set[JobKey] | None = None) -> None:
        self.attempted = attempted or set()
        self.payloads: list[ItemPayload] = []
        self.curator_runs: dict[int, CuratorSummary | None] = {}
        self.existing: list[TopicRef] = []
        self.fail_writes = False
        self.fail_retire = False
        self.retired = 0

    def start_curator_run(
        self, trigger: CuratorTrigger, topics: Sequence[str], dollar_cap: float
    ) -> int:
        run_id = len(self.curator_runs) + 1
        self.curator_runs[run_id] = None
        return run_id

    def finish_curator_run(self, curator_run_id: int, summary: CuratorSummary) -> None:
        self.curator_runs[curator_run_id] = summary

    def record_item(self, payload: ItemPayload) -> RecordedIds:
        if self.fail_writes:
            raise StoreError("connection refused")
        known = [p.run.client_id for p in self.payloads]
        if payload.run.client_id in known:
            run_id = known.index(payload.run.client_id) + 1
            return RecordedIds(topic_id=1, run_id=run_id, item_id=None, duplicate=True)
        self.payloads.append(payload)
        return RecordedIds(topic_id=1, run_id=len(self.payloads), item_id=None)

    def attempted_jobs(self, topics: Sequence[str]) -> set[JobKey]:
        return self.attempted

    def topics(self) -> list[TopicRef]:
        return self.existing

    def retire_stale(self) -> int:
        if self.fail_retire:
            raise RuntimeError("database went away")
        return self.retired


def record_with(status: Status | None, cost: float = 0.03) -> ItemRecord:
    record = quiz_record()
    run = record.run.model_copy(update={"cost_usd": cost})
    if status is None:
        run = run.model_copy(update={"answer": None, "outcome": "no_answer"})
    return record.model_copy(update={"run": run, "status": status})


def test_build_topics_are_thirty_and_distinct_from_the_eval_set() -> None:
    assert len(BUILD_TOPICS) == 30
    assert len({t.casefold() for t in BUILD_TOPICS}) == 30
    assert not {t.casefold() for t in BUILD_TOPICS} & {t.casefold() for t in EVAL_TOPICS}


def test_plan_runs_every_mode_and_difficulty_and_skips_attempted_jobs() -> None:
    attempted = {job_key("QUASARS", "quiz", "easy")}

    jobs, skipped = plan_jobs([QUASARS, MAGNETARS], attempted)

    assert skipped == 1 and len(jobs) == 11
    assert [job.topic.name for job in jobs[:5]] == ["Quasars"] * 5  # topic by topic
    typical, worst = estimate(jobs, Settings())
    assert 0 < typical < worst
    assert worst == pytest.approx(11 * job_cost_limit(Settings()))


def test_budget_reserves_the_worst_case_and_settles_the_actual_cost() -> None:
    budget = Budget(0.12)

    assert budget.try_reserve(0.045) and budget.try_reserve(0.045)
    assert not budget.try_reserve(0.045)
    budget.settle(0.045, 0.02)
    assert budget.try_reserve(0.045)
    assert budget.spent_usd == pytest.approx(0.02)


def test_run_jobs_stops_at_the_cap_and_survives_a_crashing_job() -> None:
    jobs, _ = plan_jobs([QUASARS], set())
    done: list[tuple[Job, object]] = []

    def work(job: Job) -> ItemRecord:
        if job.difficulty == "medium" and job.mode == "learn":
            raise RuntimeError("bug")
        return record_with("published", cost=0.03)

    # Each job reserves its limit of $0.05: the crash counts at the limit, the others at their
    # cost ($0.03 agent plus $0.004 verifier).
    budget = Budget(0.15)
    ran, stopped = run_jobs(jobs, work, lambda j, o: done.append((j, o)), budget, 1, 0.05)

    assert ran == len(done) == 3 < len(jobs)
    assert stopped is not None and "dollar cap" in stopped
    assert any(isinstance(outcome, RuntimeError) for _, outcome in done)
    assert budget.spent_usd == pytest.approx(0.034 + 0.05 + 0.034)
    assert budget.spent_usd <= budget.cap_usd


def test_ctrl_c_stops_new_jobs_and_keeps_the_finished_ones() -> None:
    jobs, _ = plan_jobs([QUASARS], set())
    done: list[tuple[Job, object]] = []

    def work(job: Job) -> ItemRecord:
        if job == jobs[1]:
            raise KeyboardInterrupt
        return record_with("published")

    _, stopped = run_jobs(jobs, work, lambda j, o: done.append((j, o)), Budget(6.0), 1, 0.17)

    assert stopped is not None and stopped.startswith("interrupted")
    assert [job for job, _ in done] == [jobs[0]]
    assert "4 jobs not started" in stopped


def make_curator(store: MemoryStore, tmp_path: Path, settings: Settings) -> Curator:
    return Curator(store, FakeLLM(), None, settings, tmp_path / "pending", say=lambda _m: None)


def test_curator_stores_every_run_and_records_the_totals(
    tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    statuses: list[Status | None] = [
        "published",
        "review",
        "discarded",
        None,
        "published",
        "review",
    ]
    monkeypatch.setattr(pipeline, "produce", lambda *_args: record_with(statuses.pop(0)))
    store = MemoryStore()
    store.retired = 2
    curator = make_curator(store, tmp_path, settings)
    jobs, skipped = curator.plan([QUASARS])

    summary = curator.run("build", [QUASARS], jobs, skipped, Budget(6.0), workers=1)

    assert len(store.payloads) == 6
    assert sum(1 for p in store.payloads if p.item is None) == 1
    assert {p.run.curator_run_id for p in store.payloads} == {1}
    assert (summary.published, summary.review, summary.discarded, summary.no_item) == (2, 2, 1, 1)
    assert summary.retired == 2 and summary.jobs_run == 6 and summary.stopped_reason is None
    assert summary.anthropic_cost_usd > 0 and summary.typesafe_cost_usd > 0
    assert store.curator_runs[1] == summary
    assert list((tmp_path / "pending").glob("*.json")) == []


def test_unstored_runs_wait_on_disk_and_are_sent_by_the_next_run(
    tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "produce", lambda *_args: record_with("published"))
    store = MemoryStore()
    store.fail_writes = True
    curator = make_curator(store, tmp_path, settings)
    jobs, _ = curator.plan([QUASARS])

    curator.run("build", [QUASARS], jobs[:2], 0, Budget(6.0), workers=1)
    assert len(list((tmp_path / "pending").glob("*.json"))) == 2

    store.fail_writes = False
    assert curator.flush_pending() == 2
    assert len(store.payloads) == 2
    assert list((tmp_path / "pending").glob("*.json")) == []


# --- Discover ---------------------------------------------------------------------------------

NOW = datetime(2026, 10, 2, tzinfo=UTC)
LINK = "https://science.nasa.gov/missions/webb/cats-paw/"
RSS = f"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Webb sees the Cat's Paw Nebula</title><link>{LINK}</link>
<pubDate>Wed, 01 Oct 2026 12:00:00 GMT</pubDate><description>A new image.</description></item>
<item><title>Budget update</title><link>https://www.nasa.gov/budget/</link>
<pubDate>Wed, 01 Oct 2026 10:00:00 GMT</pubDate><description>Money.</description></item>
</channel></rss>"""


def test_read_news_merges_feeds_and_skips_a_broken_one(web: FakeWeb, ctx: ToolContext) -> None:
    web.add_text("https://science.nasa.gov/feed/", RSS, content_type="application/rss+xml")
    web.add_text("https://www.nasa.gov/news-release/feed/", RSS, content_type="application/rss+xml")
    notes: list[str] = []

    items = read_news(ctx, notes.append)

    assert [item.link for item in items] == [LINK, "https://www.nasa.gov/budget/"]
    assert len(notes) == 3  # the three ESA feeds are not routed in the fake web


def test_choose_rejects_invented_links_other_domains_and_known_topics(ctx: ToolContext) -> None:
    web_items = parse_rss(RSS)
    picks = [
        NewsPick(topic="An invented story", link="https://science.nasa.gov/made-up/", why="x"),
        NewsPick(topic="Quasars", link=LINK, why="x"),
        NewsPick(topic="  Webb's image of   the Cat's Paw Nebula ", link=LINK, why="x"),
    ]

    topic, notes = choose(picks, web_items, [QUASARS], ctx, NOW)

    assert topic is not None
    assert topic.name == "Webb's image of the Cat's Paw Nebula"
    assert topic.kind == "news" and topic.lead_url == LINK
    assert topic.retire_after == NOW + timedelta(days=NEWS_RETIRE_DAYS)
    assert len(notes) == 2


def test_choose_rejects_an_article_already_used_under_another_name(ctx: ToolContext) -> None:
    used = TopicRef(name="Webb sees the Cat's Paw", kind="news", lead_url=LINK)
    picks = [NewsPick(topic="The Cat's Paw Nebula seen by Webb", link=LINK, why="x")]

    topic, notes = choose(picks, parse_rss(RSS), [used], ctx, NOW)

    assert topic is None and "already used" in notes[0]


def test_discover_uses_one_structured_call_and_logs_its_cost(
    ctx: ToolContext, settings: Settings
) -> None:
    items = parse_rss(RSS)
    llm = FakeLLM(
        json_replies=[{"picks": [{"topic": "The Cat's Paw Nebula", "link": LINK, "why": "x"}]}]
    )

    found = discover(items, [QUASARS], llm, settings, ctx, NOW)

    assert found.topic is not None and found.topic.name == "The Cat's Paw Nebula"
    assert found.cost_usd > 0
    assert "Quasars" in llm.json_prompts[0] and LINK in llm.json_prompts[0]
    assert discover([], [], llm, settings, ctx, NOW).topic is None


def test_the_run_row_is_finished_even_when_the_run_crashes(
    tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "produce", lambda *_args: record_with("published"))
    store = MemoryStore()
    store.fail_retire = True
    curator = make_curator(store, tmp_path, settings)
    jobs, _ = curator.plan([QUASARS])

    with pytest.raises(RuntimeError):
        curator.run("build", [QUASARS], jobs[:1], 0, Budget(6.0), workers=1)

    summary = store.curator_runs[1]
    assert summary is not None and summary.jobs_run == 1 and summary.published == 1
    assert summary.stopped_reason is not None and summary.stopped_reason.startswith("crashed")


def test_a_payload_sent_twice_is_stored_once() -> None:
    store = MemoryStore()
    payload = build_payload(record_with("published"), QUASARS, "curator", 1)

    store.record_item(payload)

    assert store.record_item(payload).duplicate
    assert len(store.payloads) == 1


def test_an_unreadable_pending_file_is_set_aside(tmp_path: Path, settings: Settings) -> None:
    pending = tmp_path / "pending"
    pending.mkdir()
    (pending / "20261002T000000Z-quiz-easy-quasars.json").write_text("{truncated", encoding="utf-8")
    curator = make_curator(MemoryStore(), tmp_path, settings)

    assert curator.flush_pending() == 0
    assert list(pending.glob("*.json")) == []
    assert len(list((pending / "corrupt").glob("*.json"))) == 1


def test_slugify_makes_short_file_safe_names() -> None:
    assert (
        slugify("Webb's image of the Cat's Paw Nebula!") == "webb-s-image-of-the-cat-s-paw-nebula"
    )
    assert slugify("***") == "topic"


def test_a_billed_topic_choice_that_fails_still_logs_its_cost(
    ctx: ToolContext, settings: Settings
) -> None:
    cut_off = LLMError("structured output stopped early (max_tokens)", Usage(output_tokens=1024))
    llm = FakeLLM(json_replies=[cut_off])

    found = discover(parse_rss(RSS), [], llm, settings, ctx, NOW)

    assert found.topic is None
    assert found.cost_usd == pytest.approx(1024 * 5 / 1_000_000)


def test_a_result_that_cannot_be_saved_is_kept_on_disk(
    tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "produce", lambda *_args: record_with("published"))

    def broken(*_args: object) -> None:
        raise ValueError("cannot build the payload")

    monkeypatch.setattr(pipeline, "build_payload", broken)
    store = MemoryStore()
    curator = make_curator(store, tmp_path, settings)
    jobs, _ = curator.plan([QUASARS])

    summary = curator.run("build", [QUASARS], jobs[:2], 0, Budget(6.0), workers=2)

    assert summary.jobs_run == 2 and summary.published == 2
    assert len(list((tmp_path / "pending" / "unsaved").glob("*.json"))) == 2


def test_a_payload_the_bank_refuses_is_set_aside_not_resent(
    tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "produce", lambda *_args: record_with("published"))
    store = MemoryStore()

    def refuse(_payload: ItemPayload) -> RecordedIds:
        raise StoreError("HTTP 400 violates check constraint", 400)

    monkeypatch.setattr(store, "record_item", refuse)
    curator = make_curator(store, tmp_path, settings)
    jobs, _ = curator.plan([QUASARS])

    curator.run("build", [QUASARS], jobs[:1], 0, Budget(6.0), workers=1)

    pending = tmp_path / "pending"
    assert list(pending.glob("*.json")) == []
    assert len(list((pending / "rejected").glob("*.json"))) == 1
    assert len(list((pending / "rejected").glob("*.reason.txt"))) == 1


def test_a_broken_console_never_stops_a_run(tmp_path: Path, settings: Settings) -> None:
    def broken_pipe(_message: str) -> None:
        raise BrokenPipeError

    curator = Curator(MemoryStore(), FakeLLM(), None, settings, tmp_path, say=broken_pipe)

    curator.say("still running")


def test_daily_finishes_an_unfinished_news_topic_first(tmp_path: Path, settings: Settings) -> None:
    news = TopicRef(name="The Cat's Paw Nebula", kind="news", lead_url=LINK)
    old = TopicRef(name="An old story", kind="news", retire_after=NOW - timedelta(days=1))
    store = MemoryStore(attempted={job_key(news.name, "learn", "easy")})
    curator = make_curator(store, tmp_path, settings)

    found = _unfinished_news_topic(curator, [old, news, QUASARS], NOW)

    assert found is not None
    topic, jobs, done = found
    assert topic == news and len(jobs) == 5 and done == 1


def test_cli_numbers_must_be_positive() -> None:
    assert _positive_int("3") == 3
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_int("0")
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_float("-1")
