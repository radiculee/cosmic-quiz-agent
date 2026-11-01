"""Live searches on the web page: the topic check, the plan, the guardrails and the streamed runs.

Most tests replace each agent run and the gate with a stored record; one plays a whole search
through the real loop and verifiers with the scripted fake model. Nothing touches the network or
a paid API.
"""

from __future__ import annotations

import functools
import json
import threading
import time
from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import anthropic
import httpx2
import pytest

import agent.limits as limits_module
import agent.ondemand as ondemand
from agent.bank import BankTopic, LearnItem, QuizQuestion, ShownStatus, SourceCheck
from agent.config import Settings
from agent.limits import (
    LAUNCH_LIMITS,
    LIMITS,
    LimitName,
    LimitSettings,
    OnDemandUsage,
    SearchSlots,
    limit_message,
)
from agent.llm import Completion, LLMError, Message, ToolSpec, Usage
from agent.loop import run_learn, run_quiz
from agent.ondemand import (
    EndEvent,
    FallbackEvent,
    LogEvent,
    MissedEvent,
    PlanEvent,
    PlannedItem,
    ProgressEvent,
    RejectedEvent,
    ResearchEvent,
    ResultEvent,
    RunTimes,
    SearchRequest,
    Services,
    StatsEvent,
    plan_search,
    research,
    step_event,
    step_progress,
    tool_detail,
)
from agent.rest import StoreError
from agent.schemas import Difficulty, ItemRecord, Mode, RunResult, Status, Step
from agent.store import ItemPayload, OnDemandOutcome, RecordedIds, RunEstimate, TopicKind
from agent.topic_check import (
    InvalidTopicError,
    TopicCheckError,
    TopicVerdict,
    clean_topic,
    keyword_judge,
    verdict,
)
from agent.topic_pick import TopicPick
from agent.web import ApiRequest, ApiResponse, StreamResponse
from api import research as research_api
from tests.conftest import CALL_USAGE, FakeLLM, FakeWeb, completion
from tests.test_loop import ARTICLE, FETCH, QUOTE
from tests.test_store import quiz_record
from tests.test_tools import WIKI_API, wiki_extract
from tests.test_verifiers import FakeJev, haiku_reply

# --- The topic check --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "cleaned"),
    [
        ("  black   holes ", "Black holes"),
        ("Ōumuamua", "Ōumuamua"),
        ("Comet C/2023 A3", "Comet C/2023 A3"),
        ("Sagittarius A*", "Sagittarius A*"),
        ("how do black holes form?", "How do black holes form?"),
    ],
)
def test_clean_topic_tidies_real_topic_names(text: str, cleaned: str) -> None:
    assert clean_topic(text) == cleaned


@pytest.mark.parametrize(
    "text",
    [
        "x",
        "a" * 81,
        "https://example.com/mars",
        "www.mars.org",
        "<script>",
        "{x}",
        "123 456",
        "a_b",
    ],
)
def test_clean_topic_rejects_what_cannot_be_a_topic(text: str) -> None:
    with pytest.raises(InvalidTopicError):
        clean_topic(text)


def test_a_topic_needs_both_questions_answered_yes() -> None:
    assert verdict(0.9, 0.9, "jev").accepted
    off_topic = verdict(0.1, 0.9, "jev")
    not_plain = verdict(0.9, 0.1, "jev")
    assert not off_topic.accepted and "astronomy" in off_topic.reason
    assert not not_plain.accepted and "just the name" in not_plain.reason


def test_keyword_judge_is_fooled_by_shared_words() -> None:
    assert keyword_judge("Mars bar").accepted  # why Jev does the real check
    assert not keyword_judge("Betelgeuse").accepted


# --- Log lines ---------------------------------------------------------------------------------


def test_tool_steps_show_the_url_or_the_query() -> None:
    assert tool_detail({"url": "https://en.wikipedia.org/wiki/Black_hole"}) == (
        "en.wikipedia.org/wiki/Black_hole"
    )
    assert tool_detail({"query": "black hole", "limit": 5}) == '"black hole"'
    assert tool_detail({}) == ""

    clock = ondemand._Clock().for_item("quiz-easy")
    fetch = Step(
        index=1,
        kind="tool",
        summary="fetch_page(...) -> error",
        seconds=0.2,
        tool="fetch_page",
        arguments={"url": "https://www.nasa.gov/x"},
        is_error=True,
    )
    line = step_event(fetch, clock, "question")
    assert (line.label, line.detail, line.tone) == ("fetch_page", "www.nasa.gov/x (failed)", "warn")
    assert line.key == "quiz-easy"

    submit = Step(index=2, kind="model", summary="submit_quiz (stop: tool_use)", seconds=2.0)
    assert step_event(submit, clock, "question").detail == "writes the question"
    plan = Step(
        index=0, kind="model", summary="search_wikipedia, fetch_page (stop: tool_use)", seconds=1
    )
    assert step_event(plan, clock, "question").detail == "next: search_wikipedia, fetch_page"


def test_progress_names_the_real_work_after_each_step() -> None:
    clock = ondemand._Clock().for_item("learn-hard")

    def after(step: Step) -> tuple[str, str] | None:
        progress = step_progress(step, clock, "explanation")
        return None if progress is None else (progress.stage, progress.status)

    def tool(name: str, arguments: dict[str, object], is_error: bool = False) -> Step:
        return Step(
            index=1,
            kind="tool",
            summary=f"{name}(...)",
            seconds=0.4,
            tool=name,
            arguments=arguments,
            is_error=is_error,
        )

    assert after(tool("search_wikipedia", {"query": "magnetar"})) == (
        "search",
        'Looking through Wikipedia results for "magnetar"',
    )
    assert after(tool("search_arxiv", {"query": "x" * 200})) == (
        "search",
        f'Looking through arXiv results for "{"x" * 60}"',
    )
    assert after(tool("fetch_page", {"url": "https://www.nasa.gov/missions/x"})) == (
        "read",
        "Reading nasa.gov",
    )
    assert after(tool("fetch_feed", {"feed": "esa_webb"})) == ("read", "Reading ESA/Webb news")
    assert after(tool("nasa_apod", {"date": "2026-10-01"})) == (
        "read",
        "Reading NASA's Astronomy Picture of the Day",
    )
    # A failed tool, or a model call that only asks for tools, changes nothing shown.
    assert after(tool("fetch_page", {"url": "https://esa.int/x"}, is_error=True)) is None
    asking = Step(index=0, kind="model", summary="fetch_page (stop: tool_use)", seconds=2.0)
    assert after(asking) is None
    submit = Step(index=2, kind="model", summary="submit_answer (stop: tool_use)", seconds=6.0)
    assert after(submit) == (
        "write",
        "Checking the explanation's quotes and numbers against its pages",
    )
    progress = step_progress(submit, clock, "explanation")
    assert progress is not None and progress.key == "learn-hard"


def test_progress_is_always_about_an_item() -> None:
    with pytest.raises(ValueError):
        ondemand._Clock().progress("search", "Choosing where to look")


# --- The plan ----------------------------------------------------------------------------------


def keys(items: list[PlannedItem], source: str | None = None) -> list[str]:
    return [item.key for item in items if source is None or item.source == source]


def test_a_search_plans_every_question_first_then_every_explanation() -> None:
    plan = plan_search(None)

    assert keys(plan) == EVERY_ITEM
    assert all(item.source == "live" for item in plan)


def test_the_plan_takes_from_the_bank_what_it_already_has() -> None:
    have = BankTopic(name="Black holes", kind="evergreen", learn=["easy"], quiz=["easy", "hard"])

    plan = plan_search(have)

    assert keys(plan, "live") == ["quiz-medium", "learn-medium", "learn-hard"]
    assert keys(plan, "bank") == ["quiz-easy", "quiz-hard", "learn-easy"]


def test_every_run_has_the_agents_whole_budget_and_ends_inside_vercels_limit() -> None:
    # Every run of a search starts in its first seconds, so none needs a shorter budget.
    assert Settings().max_seconds < ondemand.SEARCH_SECONDS < 300  # Vercel's limit


def test_each_live_item_carries_its_usual_run_time_and_bank_items_none() -> None:
    have = BankTopic(name="Black holes", kind="evergreen", learn=["easy"], quiz=[])
    times = RunTimes(lambda: [estimate("quiz", "hard", 21.4, 9)])

    plan = ondemand.with_estimates(plan_search(have), times)

    assert [(item.key, item.estimate_seconds) for item in plan] == [
        ("quiz-easy", ondemand.ESTIMATE_FALLBACK_SECONDS),
        ("quiz-medium", ondemand.ESTIMATE_FALLBACK_SECONDS),
        ("quiz-hard", 21.4),
        ("learn-easy", None),  # in the bank: no run
        ("learn-medium", ondemand.ESTIMATE_FALLBACK_SECONDS),
        ("learn-hard", ondemand.ESTIMATE_FALLBACK_SECONDS),
    ]


def estimate(mode: Mode, difficulty: Difficulty, seconds: float, runs: int) -> RunEstimate:
    return RunEstimate(mode=mode, difficulty=difficulty, median_seconds=seconds, runs=runs)


def test_run_times_are_read_once_an_hour_and_need_enough_runs() -> None:
    reads: list[float] = []
    clock = [0.0]

    def read() -> list[RunEstimate]:
        reads.append(clock[0])
        return [estimate("learn", "easy", 31.0, 12), estimate("quiz", "easy", 9.0, 4)]

    times = RunTimes(read, now=lambda: clock[0])

    assert times.seconds("learn", "easy") == 31.0
    # Fewer runs than the minimum, or none at all: the fallback.
    assert times.seconds("quiz", "easy") == ondemand.ESTIMATE_FALLBACK_SECONDS
    assert times.seconds("quiz", "hard") == ondemand.ESTIMATE_FALLBACK_SECONDS
    clock[0] = ondemand.ESTIMATE_TTL_SECONDS - 1
    times.seconds("learn", "easy")
    assert reads == [0.0]  # still fresh
    clock[0] = ondemand.ESTIMATE_TTL_SECONDS
    times.seconds("learn", "easy")
    assert reads == [0.0, ondemand.ESTIMATE_TTL_SECONDS]


def test_run_times_that_cannot_be_read_never_stop_a_search_and_wait_to_retry() -> None:
    attempts: list[float] = []
    clock = [0.0]
    rows = [estimate("learn", "easy", 31.0, 12)]

    def read() -> list[RunEstimate]:
        attempts.append(clock[0])
        if len(attempts) == 1:
            raise StoreError("down")
        return rows

    times = RunTimes(read, now=lambda: clock[0])

    assert times.seconds("learn", "easy") == ondemand.ESTIMATE_FALLBACK_SECONDS
    # The searches after a failed read do not ask the database again until the retry time.
    clock[0] = ondemand.ESTIMATE_RETRY_SECONDS - 1
    assert times.seconds("learn", "easy") == ondemand.ESTIMATE_FALLBACK_SECONDS
    assert attempts == [0.0]
    clock[0] = ondemand.ESTIMATE_RETRY_SECONDS
    assert times.seconds("learn", "easy") == 31.0
    assert attempts == [0.0, ondemand.ESTIMATE_RETRY_SECONDS]
    assert ondemand.ESTIMATE_RETRY_SECONDS < ondemand.ESTIMATE_TTL_SECONDS


# --- Fakes -------------------------------------------------------------------------------------


class FakeJudge:
    def __init__(self, result: TopicVerdict | Exception) -> None:
        self.result = result
        self.topics: list[str] = []

    def judge(self, topic: str) -> TopicVerdict:
        self.topics.append(topic)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeBank:
    def __init__(
        self,
        known: str | None = None,
        have: BankTopic | None = None,
        down: bool = False,
        names: list[tuple[str, TopicKind]] | None = None,
    ) -> None:
        self.known, self.have, self.down = known, have, down
        self.names = names or []

    def topic_named(self, name: str) -> str | None:
        if self.down:
            raise StoreError("down")
        return self.known

    def coverage(self, topic: str) -> BankTopic | None:
        return self.have

    def topic_names(self) -> list[tuple[str, TopicKind]]:
        if self.down:
            raise StoreError("down")
        return self.names


class FakePicker:
    """Surprise me: answers with `topic`, and records the bank's names it was given."""

    def __init__(self, topic: str | None = "Pulsars") -> None:
        self.topic = topic
        self.seen: list[list[tuple[str, TopicKind]]] = []

    def pick(self, existing: Sequence[tuple[str, TopicKind]]) -> TopicPick:
        self.seen.append(list(existing))
        notes = [] if self.topic else ["skipped 'Black holes': already in the bank"]
        return TopicPick(
            topic=self.topic,
            usage=Usage(input_tokens=600, output_tokens=80),
            cost_usd=0.001,
            notes=notes,
        )


@dataclass
class FakeStore:
    """Behaves as begin_on_demand_search does (migration 010): the search limits refuse it
    whole, then its items are reserved in the order given while the dollar caps fit."""

    # The limit that refuses the search before anything is reserved.
    refuse: LimitName | None = None
    # How many items the dollar caps fit (None: all of them), and the cap that refuses the rest.
    fit: int | None = None
    fit_limit: LimitName = "day_usd"
    down: bool = False
    began: list[tuple[str, str, list[tuple[Mode, Difficulty]]]] = field(default_factory=list)
    finished: list[tuple[int, float, OnDemandOutcome, int | None]] = field(default_factory=list)
    payloads: list[ItemPayload] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    limits_seen: list[LimitSettings] = field(default_factory=list)
    estimates: list[RunEstimate] = field(default_factory=list)
    # What the limits have counted so far today and this month, read before the paid check.
    usage: OnDemandUsage = field(
        default_factory=lambda: OnDemandUsage(
            visitor_searches_today=0, searches_today=0, usd_today=0.0, usd_this_month=0.0
        )
    )
    # A search's runs record and settle from threads of their own.
    lock: threading.Lock = field(default_factory=threading.Lock)

    def on_demand_usage(self, user_hash: str, now: datetime) -> OnDemandUsage:
        if self.down:
            raise StoreError("down")
        return self.usage

    def begin_on_demand_search(
        self,
        user_hash: str,
        topic: str,
        items: Sequence[tuple[Mode, Difficulty]],
        reserve_usd: float,
        limits: LimitSettings,
    ) -> SearchSlots:
        self.began.append((user_hash, topic, list(items)))
        self.limits_seen.append(limits)
        self.calls.append("begin")
        assert reserve_usd == Settings().max_job_cost_usd
        assert 1 <= len(items) <= limits.runs_per_search  # the database raises otherwise
        if self.down:
            raise StoreError("down")
        if self.refuse is not None:
            return SearchSlots(ok=False, limit=self.refuse)
        count = len(items) if self.fit is None else min(self.fit, len(items))
        if count == 0:
            return SearchSlots(ok=False, limit=self.fit_limit)
        return SearchSlots(
            ok=True,
            ids=tuple(range(100, 100 + count)),
            limit=None if count == len(items) else self.fit_limit,
        )

    def live_run_estimates(self) -> list[RunEstimate]:
        return self.estimates

    def finish_on_demand_run(
        self, slot_id: int, spent_usd: float, outcome: OnDemandOutcome, run_id: int | None
    ) -> None:
        with self.lock:
            self.finished.append((slot_id, spent_usd, outcome, run_id))
            self.calls.append("finish")

    def record_item(self, payload: ItemPayload) -> RecordedIds:
        with self.lock:
            self.payloads.append(payload)
            number = len(self.payloads)
        return RecordedIds(topic_id=1, run_id=200 + number, item_id=40 + number)

    def settled(self) -> dict[int, tuple[float, OnDemandOutcome, int | None]]:
        """How each reservation ended, by its id: 100 is the plan's first live item."""
        return {slot: (spent, outcome, run) for slot, spent, outcome, run in self.finished}


NO_CHECK = SourceCheck(options=[], sentences=0, sentences_supported=0)


class FakeResults:
    """Reads back a stored live item: the run's mode and difficulty, in `status`."""

    def __init__(self, store: FakeStore, status: ShownStatus = "published") -> None:
        self.store, self.status = store, status

    def item(self, item_id: int) -> QuizQuestion | LearnItem | None:
        payload = self.store.payloads[item_id - 41]
        run, topic = payload.run, payload.topic.name
        if run.mode == "learn":
            return LearnItem(
                id=item_id,
                difficulty=run.difficulty,
                topic=topic,
                explanation="...",
                sources=[],
                source_check=NO_CHECK,
                status=self.status,
            )
        return QuizQuestion(
            id=item_id,
            difficulty=run.difficulty,
            topic=topic,
            question="Q?",
            options=["a", "b", "c", "d"],
            status=self.status,
        )


def services(
    judge: FakeJudge | None = None,
    bank: FakeBank | None = None,
    store: FakeStore | None = None,
    status: ShownStatus = "published",
    llm: object = None,
    jev: object = None,
    limits: LimitSettings = LIMITS,
    picker: FakePicker | None = None,
) -> tuple[Services, FakeStore]:
    store = store or FakeStore()
    built = Services(
        judge=judge or FakeJudge(ACCEPT),
        picker=picker or FakePicker(),
        bank=bank or FakeBank(),
        results=FakeResults(store, status),
        store=store,
        llm=llm or object(),  # type: ignore[arg-type]
        jev=jev,  # type: ignore[arg-type]
        settings=Settings(),
        run_times=RunTimes(store.live_run_estimates),
        limits=lambda now: limits,
        sign=lambda purpose, value: f"signed:{purpose}:{value}",
    )
    return built, store


ACCEPT = verdict(0.98, 0.97, "jev-1.13.0")
SEARCH = SearchRequest(topic="Neutron stars", visitor="v1")
SURPRISE = SearchRequest(topic=None, visitor="v1")
QUESTIONS = ["quiz-easy", "quiz-medium", "quiz-hard"]
EXPLANATIONS = ["learn-easy", "learn-medium", "learn-hard"]
EVERY_ITEM = QUESTIONS + EXPLANATIONS


@dataclass
class Script:
    """What the replaced runs saw: each run's key, its agent time budget and its thread's name."""

    runs: list[tuple[str, float, str]] = field(default_factory=list)


def script(
    monkeypatch: pytest.MonkeyPatch,
    statuses: dict[str, Status | None] | None = None,
    crash: frozenset[str] = frozenset(),
    together: int = 0,
    refused: frozenset[str] = frozenset(),
) -> Script:
    """Replace each agent run and the gate with the stored quiz record, made for the run's mode
    and difficulty and decided as `statuses` says (published by default). With `together`, each
    run waits until that many runs are going at once, and fails if they never are. A run in
    `refused` ends as a refused key leaves it: no answer, no verdict, nothing spent."""
    record = quiz_record()
    seen = Script()
    barrier = threading.Barrier(together) if together else None

    def fake_run(mode: Mode) -> Callable[..., RunResult]:
        def run(
            topic: str,
            difficulty: Difficulty,
            llm: object,
            settings: Settings,
            on_step: Callable[[Step], None],
        ) -> RunResult:
            key = f"{mode}-{difficulty}"
            seen.runs.append((key, settings.max_seconds, threading.current_thread().name))
            if barrier is not None:
                barrier.wait(timeout=5)
            if key in crash:
                raise RuntimeError("the agent fell over")
            for step in record.run.steps:
                on_step(step)
            return record.run.model_copy(update={"mode": mode, "difficulty": difficulty})

        return run

    def fake_decide(result: RunResult, *_: object) -> ItemRecord:
        key = f"{result.mode}-{result.difficulty}"
        if key in refused:
            nothing = result.model_copy(update={"cost_usd": 0.0, "answer": None})
            return record.model_copy(update={"run": nothing, "verification": None, "status": None})
        status = (statuses or {}).get(key, "published")
        return record.model_copy(update={"run": result, "status": status})

    monkeypatch.setattr(ondemand, "run_learn", fake_run("learn"))
    monkeypatch.setattr(ondemand, "run_quiz", fake_run("quiz"))
    monkeypatch.setattr(ondemand, "verify_and_decide", fake_decide)
    return seen


def of_type[E](events: list[ResearchEvent], kind: type[E]) -> list[E]:
    return [event for event in events if isinstance(event, kind)]


def result_keys(events: list[ResearchEvent]) -> list[str]:
    """The keys of the items sent, in plan order: runs at once finish in any order, and the
    page plays them in plan order."""
    sent = {result.key for result in of_type(events, ResultEvent)}
    return [key for key in EVERY_ITEM if key in sent]


# --- Searches ----------------------------------------------------------------------------------


def test_a_search_reserves_every_item_in_one_call_and_counts_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = script(monkeypatch)
    live, store = services()

    events = list(research(SEARCH, live))

    plan = events[0]
    assert isinstance(plan, PlanEvent) and plan.topic == "Neutron stars"
    assert keys(plan.items, "live") == EVERY_ITEM
    results = of_type(events, ResultEvent)
    assert result_keys(events) == EVERY_ITEM and len(results) == 6
    for result in results:
        if result.key in QUESTIONS:
            assert result.reveal_token == f"signed:reveal:{result.item.id}"
        else:
            assert result.reveal_token is None  # explanations need none
    assert "correct_index" not in json.dumps([r.model_dump(mode="json") for r in results])

    # One reservation for the whole search, in plan order; every run settles its own.
    assert store.began == [
        ("v1", "Neutron stars", [(k.split("-")[0], k.split("-")[1]) for k in EVERY_ITEM])
    ]
    assert store.calls == ["begin"] + ["finish"] * 6
    record = quiz_record()
    assert all(
        outcome == "published" and spent == pytest.approx(record.anthropic_cost_usd)
        for spent, outcome, _ in store.settled().values()
    )
    assert sorted(store.settled()) == list(range(100, 106))
    assert sorted((p.run.mode, p.run.difficulty, p.run.source) for p in store.payloads) == sorted(
        (mode, level, "on_demand")
        for mode in ("quiz", "learn")
        for level in ("easy", "medium", "hard")
    )
    # Every run has the agent's whole time budget, on a thread named by the search and item.
    assert sorted((key, budget, name) for key, budget, name in seen.runs) == sorted(
        (key, Settings().max_seconds, f"live-search-100-{key}") for key in EVERY_ITEM
    )

    # Every line after the on-topic check names its item.
    lines = of_type(events, LogEvent)
    assert lines[0].label == "On-topic check (Jev)" and lines[0].key is None
    assert all(line.key in EVERY_ITEM for line in lines[1:])
    budgets = {line.key: line.detail for line in lines if line.label == "Budget"}
    assert budgets["quiz-easy"] == "up to $0.17 reserved for the EASY question"
    assert budgets["learn-hard"] == "up to $0.17 reserved for the HARD explanation"
    assert not any(line.label == "Time" for line in lines)  # no shortened runs any more
    # Which option the sources support would give a quiz answer away.
    jev_lines = [line for line in lines if line.label.startswith("Jev")]
    assert jev_lines and all(line.verdict is None for line in jev_lines)


def test_every_run_of_a_search_goes_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    # Each run waits until all six are going: run one at a time, the first would time out.
    script(monkeypatch, together=6)
    live, store = services()

    events = list(research(SEARCH, live))

    assert result_keys(events) == EVERY_ITEM
    assert of_type(events, MissedEvent) == []
    assert len(store.finished) == 6


def test_runs_finishing_out_of_order_each_send_their_own_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch)
    # The HARD explanation's record is stored first, the EASY question's last.
    original = ondemand._produce

    def slower_for_easier(
        topic: str,
        planned: PlannedItem,
        services: Services,
        clock: ondemand._Clock,
        emit: Callable[[ResearchEvent | None], None],
    ) -> ItemRecord:
        time.sleep(0.05 * (len(EVERY_ITEM) - 1 - EVERY_ITEM.index(planned.key)))
        return original(topic, planned, services, clock, emit)

    monkeypatch.setattr(ondemand, "_produce", slower_for_easier)
    live, store = services()

    events = list(research(SEARCH, live))

    results = of_type(events, ResultEvent)
    assert results[0].key == "learn-hard"
    assert results[-1].key == "quiz-easy"
    for result in results:
        assert result.key == f"{result.item.mode}-{result.item.difficulty}"
    assert len(store.finished) == 6


def test_a_topic_the_bank_has_at_every_level_is_free_and_not_counted() -> None:
    every: list[Difficulty] = ["easy", "medium", "hard"]
    have = BankTopic(name="Neutron stars", kind="evergreen", learn=every, quiz=every)
    judge = FakeJudge(ACCEPT)
    live, store = services(judge, FakeBank(known="Neutron stars", have=have))

    events = list(research(SEARCH, live))

    assert len(events) == 1
    plan = events[0]
    assert isinstance(plan, PlanEvent) and keys(plan.items, "bank") == EVERY_ITEM
    assert judge.topics == [] and store.began == []


def test_a_bank_topic_with_gaps_makes_only_the_missing_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch)
    have = BankTopic(name="Black holes", kind="evergreen", learn=[], quiz=["easy", "hard"])
    request = SearchRequest(topic="Black Holes", visitor="v1")
    live, store = services(bank=FakeBank(known="Black holes", have=have))

    events = list(research(request, live))

    plan = events[0]
    assert isinstance(plan, PlanEvent) and plan.topic == "Black holes"  # the bank's spelling
    assert keys(plan.items, "bank") == ["quiz-easy", "quiz-hard"]
    assert result_keys(events) == ["quiz-medium", *EXPLANATIONS]
    assert store.began == [
        (
            "v1",
            "Black holes",
            [("quiz", "medium"), ("learn", "easy"), ("learn", "medium"), ("learn", "hard")],
        )
    ]


def test_a_visitor_over_the_daily_limit_keeps_what_the_bank_has() -> None:
    have = BankTopic(name="Black holes", kind="evergreen", learn=[], quiz=["easy"])
    store = FakeStore(refuse="user_day")
    live, _ = services(bank=FakeBank(known="Black holes", have=have), store=store)

    events = list(research(SEARCH, live))

    assert isinstance(events[0], PlanEvent) and keys(events[0].items, "bank") == ["quiz-easy"]
    last = events[-1]
    assert isinstance(last, FallbackEvent) and last.reason == "limit"
    assert "2 live searches today" in last.message
    assert store.finished == []


@pytest.mark.parametrize(
    ("counted", "limit"),
    [
        ({"visitor_searches_today": 2}, "user_day"),
        ({"searches_today": 4}, "day_searches"),
        ({"usd_today": 1.40, "usd_this_month": 1.40}, "day_usd"),  # 1.40 + 0.17 > 1.55
        ({"usd_this_month": 3.90}, "month_usd"),
    ],
)
def test_a_search_the_limits_would_refuse_never_pays_for_the_topic_check(
    counted: dict[str, float], limit: LimitName
) -> None:
    usage = OnDemandUsage.model_validate(
        {
            "visitor_searches_today": 0,
            "searches_today": 0,
            "usd_today": 0.0,
            "usd_this_month": 0.0,
            **counted,
        }
    )
    judge = FakeJudge(ACCEPT)
    live, store = services(judge, store=FakeStore(usage=usage))

    events = list(research(SEARCH, live))

    assert isinstance(events[0], PlanEvent)
    last = events[-1]
    assert isinstance(last, FallbackEvent) and last.reason == "limit"
    assert last.message == limit_message(limit, LIMITS)
    assert judge.topics == [] and store.began == []  # nothing paid, nothing reserved


def test_in_the_launch_week_a_visitor_gets_more_searches_and_every_run_keeps_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Two searches today and four for everyone would refuse a search on the usual limits.
    script(monkeypatch)
    busy = OnDemandUsage(
        visitor_searches_today=2, searches_today=4, usd_today=0.0, usd_this_month=0.0
    )
    live, store = services(store=FakeStore(usage=busy), limits=LAUNCH_LIMITS)

    events = list(research(SEARCH, live))

    assert of_type(events, FallbackEvent) == []
    assert result_keys(events) == EVERY_ITEM
    assert store.limits_seen == [LAUNCH_LIMITS]  # read once, for the one reservation


def test_surprise_me_picks_a_new_topic_and_skips_the_on_topic_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch)
    judge = FakeJudge(ACCEPT)
    picker = FakePicker("Pulsars")
    names: list[tuple[str, TopicKind]] = [("Black holes", "evergreen"), ("Wormholes", "custom")]
    live, store = services(judge, FakeBank(names=names), picker=picker)

    events = list(research(SURPRISE, live))

    picked, plan = events[0], events[1]
    assert isinstance(picked, LogEvent) and picked.label == "Agent picked a topic"
    assert picked.detail == "Pulsars" and picked.key is None
    assert isinstance(plan, PlanEvent) and plan.topic == "Pulsars"
    assert result_keys(events) == EVERY_ITEM
    assert picker.seen == [names]  # every bank topic, so the pick is new
    assert judge.topics == []  # the agent's own pick is not checked again
    # The limits, then the paid pick, then the one reservation that decides.
    assert [(visitor, topic, len(items)) for visitor, topic, items in store.began] == [
        ("v1", "Pulsars", 6)
    ]


def test_surprise_me_over_a_limit_never_pays_for_the_pick() -> None:
    usage = OnDemandUsage(
        visitor_searches_today=2, searches_today=0, usd_today=0.0, usd_this_month=0.0
    )
    picker = FakePicker()
    live, store = services(store=FakeStore(usage=usage), picker=picker)

    events = list(research(SURPRISE, live))

    assert len(events) == 1
    assert isinstance(events[0], FallbackEvent) and events[0].reason == "limit"
    assert events[0].message == limit_message("user_day", LIMITS)
    assert picker.seen == [] and store.began == []


@pytest.mark.parametrize("failure", ["pick", "bank", "store"])
def test_surprise_me_that_cannot_pick_counts_nothing(failure: str) -> None:
    picker = FakePicker(None if failure == "pick" else "Pulsars")
    store = FakeStore(down=failure == "store")
    live, _ = services(bank=FakeBank(down=failure == "bank"), store=store, picker=picker)

    events = list(research(SURPRISE, live))

    assert len(events) == 1
    assert isinstance(events[0], FallbackEvent) and events[0].reason == "unavailable"
    if failure == "pick":
        assert "nothing was counted" in events[0].message
    else:
        assert picker.seen == []  # nothing paid when the limits cannot be read
    assert store.began == []


def test_the_limit_message_names_the_number_in_force() -> None:
    assert "2 live searches today" in limit_message("user_day", LIMITS)
    assert "5 live searches today" in limit_message("user_day", LAUNCH_LIMITS)


def test_only_the_visitors_limit_message_is_formatted(monkeypatch: pytest.MonkeyPatch) -> None:
    # A brace in any other message is shown as written instead of raising when a player is
    # refused (the 2026-10-22 code review, finding 3).
    messages = {**limits_module._LIMIT_MESSAGES, "day_usd": "Today's budget {is} used."}
    monkeypatch.setattr(limits_module, "_LIMIT_MESSAGES", messages)

    assert limit_message("day_usd", LIMITS) == "Today's budget {is} used."
    assert "2 live searches today" in limit_message("user_day", LIMITS)


def test_an_off_topic_search_is_rejected_before_anything_is_reserved() -> None:
    live, store = services(FakeJudge(verdict(0.03, 0.97, "jev")))

    events = list(research(SEARCH, live))

    assert isinstance(events[0], PlanEvent)
    assert isinstance(events[1], LogEvent) and events[1].tone == "warn"
    assert isinstance(events[-1], RejectedEvent) and "astronomy" in events[-1].message
    assert store.began == []


@pytest.mark.parametrize("failure", ["bank", "judge", "store"])
def test_an_unreachable_check_falls_back_without_running(failure: str) -> None:
    judge = FakeJudge(TopicCheckError("down") if failure == "judge" else ACCEPT)
    store = FakeStore(down=failure == "store")
    live, _ = services(judge, FakeBank(down=failure == "bank"), store)

    events = list(research(SEARCH, live))

    assert isinstance(events[-1], FallbackEvent) and events[-1].reason == "unavailable"
    assert store.finished == []


def test_a_discarded_item_is_reported_and_the_search_goes_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, {"quiz-medium": "discarded"})
    live, store = services()

    events = list(research(SEARCH, live))

    [missed] = of_type(events, MissedEvent)
    assert (missed.key, missed.reason) == ("quiz-medium", "discarded")
    assert "the MEDIUM question" in missed.message
    assert result_keys(events) == ["quiz-easy", "quiz-hard", *EXPLANATIONS]
    assert len(store.payloads) == 6  # the discarded run is still stored
    assert store.settled()[101][1] == "discarded"


def test_every_run_that_made_a_record_sends_its_figures_before_its_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, {"quiz-medium": "discarded"}, crash=frozenset({"quiz-hard"}))
    live, _ = services()

    events = list(research(SEARCH, live))

    stats = of_type(events, StatsEvent)
    # The discarded run cost money too, so it counts towards the search; the crashed run made
    # no record, so it has no figures.
    assert sorted((s.key, s.stats.mode, s.stats.status) for s in stats) == sorted(
        [
            ("quiz-easy", "quiz", "published"),
            ("quiz-medium", "quiz", "discarded"),
            *[(key, "learn", "published") for key in EXPLANATIONS],
        ]
    )
    for result in of_type(events, ResultEvent):
        [figures] = [s for s in stats if s.key == result.key]
        assert events.index(figures) < events.index(result)
    answer = quiz_record().run.answer
    assert answer is not None and hasattr(answer, "options")
    sent = json.dumps([event.model_dump(mode="json") for event in stats])
    assert not any(option in sent for option in answer.options)


def test_figures_that_cannot_be_built_never_cost_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    script(monkeypatch)

    def broken(record: ItemRecord) -> object:
        raise ValueError("a bug in the figures")

    monkeypatch.setattr(ondemand, "run_stats", broken)
    live, store = services()

    events = list(research(SEARCH, live))

    assert of_type(events, StatsEvent) == []
    assert result_keys(events) == EVERY_ITEM
    assert [outcome for _, _, outcome, _ in store.finished] == ["published"] * 6


def test_a_run_failing_keeps_its_reservation_while_the_others_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, crash=frozenset({"quiz-medium"}))
    live, store = services()

    events = list(research(SEARCH, live))

    [missed] = of_type(events, MissedEvent)
    assert (missed.key, missed.reason) == ("quiz-medium", "failed")
    assert store.settled()[101] == (Settings().max_job_cost_usd, "failed", None)
    assert result_keys(events) == [key for key in EVERY_ITEM if key != "quiz-medium"]
    assert len(store.finished) == 6


def test_a_search_whose_every_run_failed_with_no_spend_says_the_model_was_out_of_reach(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, refused=frozenset(EVERY_ITEM))
    live, store = services()

    events = list(research(SEARCH, live))

    assert events[-1] == EndEvent(unavailable=True)
    assert len(of_type(events, EndEvent)) == 1
    assert {(spent, outcome) for spent, outcome, _ in store.settled().values()} == {(0.0, "failed")}
    assert len(store.finished) == 6


def test_a_refused_key_through_the_real_agent_loop_and_gate_is_unavailable() -> None:
    refused = LLMError("AuthenticationError: invalid x-api-key")
    live, store = services(llm=FakeLLM([refused] * 6))

    events = list(research(SEARCH, live))

    assert events[-1] == EndEvent(unavailable=True)
    assert {(spent, outcome) for spent, outcome, _ in store.settled().values()} == {(0.0, "failed")}
    assert len(store.finished) == 6 and not of_type(events, ResultEvent)


def test_a_search_with_any_run_that_reached_the_model_is_not_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, refused=frozenset(EVERY_ITEM) - {"learn-hard"})
    live, _ = services()

    events = list(research(SEARCH, live))

    assert events[-1] == EndEvent(unavailable=False)


def test_a_normal_search_ends_saying_the_model_was_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch)
    live, _ = services()

    assert list(research(SEARCH, live))[-1] == EndEvent(unavailable=False)


def test_runs_that_crashed_are_not_called_unavailable_because_their_spend_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, crash=frozenset(EVERY_ITEM))
    live, _ = services()

    assert list(research(SEARCH, live))[-1] == EndEvent(unavailable=False)


def test_a_failed_save_does_not_change_what_a_refused_search_says(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, refused=frozenset(EVERY_ITEM))
    store = FakeStore()
    live, _ = services(store=store)

    def refuse(_payload: ItemPayload) -> RecordedIds:
        raise StoreError("connection refused")

    monkeypatch.setattr(store, "record_item", refuse)

    events = list(research(SEARCH, live))

    assert events[-1] == EndEvent(unavailable=True)
    assert {(spent, outcome) for spent, outcome, _ in store.settled().values()} == {(0.0, "failed")}


def test_the_items_a_cap_left_out_do_not_stop_a_search_being_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, refused=frozenset(QUESTIONS))
    live, _ = services(store=FakeStore(fit=3))

    assert list(research(SEARCH, live))[-1] == EndEvent(unavailable=True)


def test_a_cap_that_fits_only_some_runs_leaves_out_the_last_in_plan_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch)
    store = FakeStore(fit=3)  # today's budget holds three more reservations
    live, _ = services(store=store)

    events = list(research(SEARCH, live))

    assert result_keys(events) == QUESTIONS
    skipped = of_type(events, MissedEvent)
    # The explanations come last, so a search cut short loses them before any question.
    assert [(m.key, m.reason) for m in skipped] == [(key, "skipped") for key in EXPLANATIONS]
    assert all(m.message == f"Not started. {limit_message('day_usd', LIMITS)}" for m in skipped)
    assert len(store.began) == 1 and sorted(store.settled()) == [100, 101, 102]


def test_a_cap_that_fits_no_run_keeps_what_the_bank_has() -> None:
    store = FakeStore(fit=0, fit_limit="month_usd")
    live, _ = services(store=store)

    events = list(research(SEARCH, live))

    last = events[-1]
    assert isinstance(last, FallbackEvent) and last.reason == "limit"
    assert last.message == limit_message("month_usd", LIMITS)
    assert store.finished == []


def test_a_reservation_the_search_cannot_use_is_settled_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch)

    class OneTooMany(FakeStore):
        def begin_on_demand_search(
            self,
            user_hash: str,
            topic: str,
            items: Sequence[tuple[Mode, Difficulty]],
            reserve_usd: float,
            limits: LimitSettings,
        ) -> SearchSlots:
            slots = super().begin_on_demand_search(user_hash, topic, items, reserve_usd, limits)
            return slots.model_copy(update={"ids": (*slots.ids, 999)})

    store = OneTooMany()
    live, _ = services(store=store)

    events = list(research(SEARCH, live))

    assert result_keys(events) == EVERY_ITEM
    assert store.settled()[999] == (0.0, "failed", None)


def test_a_player_leaving_mid_search_still_gets_every_run_stored_and_settled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch)
    live, store = services()
    stream = research(SEARCH, live)

    assert isinstance(next(stream), PlanEvent)
    assert isinstance(next(stream), LogEvent)  # the on-topic check
    budget = next(stream)  # the runs are reserved and the search's thread has started
    stream.close()  # the player leaves: closing waits for every run to be stored

    assert isinstance(budget, LogEvent) and budget.label == "Budget"
    assert len(store.payloads) == 6
    assert sorted(store.settled()) == list(range(100, 106))
    assert {outcome for _, outcome, _ in store.settled().values()} == {"published"}


def test_the_verifier_s_reasons_are_kept_out_of_quiz_log_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, {key: "review" for key in EVERY_ITEM})
    live, _ = services(status="review")

    events = list(research(SEARCH, live))

    haiku = [e for e in of_type(events, LogEvent) if e.label == "Haiku verifier"]
    assert sorted(line.key or "" for line in haiku if line.key in QUESTIONS) == sorted(QUESTIONS)
    assert all(line.detail == "borderline" for line in haiku if line.key in QUESTIONS)
    assert all(r.item.status == "review" for r in of_type(events, ResultEvent))


# --- A whole search through the real loop and verifiers ---------------------------------------


def words(count: int) -> str:
    return " ".join(["word"] * count)


# Inside each level's word range (agent/loop.py WORD_LIMITS).
LENGTHS: dict[Difficulty, int] = {"easy": 100, "medium": 150, "hard": 190}
LEVELS: tuple[Difficulty, ...] = ("easy", "medium", "hard")


def learn_answer(difficulty: Difficulty) -> tuple[str, dict[str, Any]]:
    return (
        "submit_answer",
        {
            "explanation": words(LENGTHS[difficulty]),
            "citations": [{"url": ARTICLE, "quote": QUOTE}],
        },
    )


def quiz_answer(difficulty: Difficulty) -> tuple[str, dict[str, Any]]:
    return (
        "submit_quiz",
        {
            "question": "What is a neutron star?",
            "options": ["A collapsed stellar core", "A young planet", "A comet", "A gas cloud"],
            "correct_index": 0,
            "explanation": words(LENGTHS[difficulty]),
            "citations": [{"url": ARTICLE, "quote": QUOTE}],
        },
    )


class PerItemLLM:
    """A scripted model for each item of a search, since its runs go at once: the agent's calls
    are routed by the run's thread name (live-search-<id>-<key>), and the Haiku verifier's by its
    schema, as it runs on a thread pool of its own (agent/verifiers)."""

    def __init__(self, scripts: dict[str, FakeLLM]) -> None:
        self.scripts = scripts
        self.verifier_threads: list[str] = []

    @property
    def model(self) -> str:
        return "claude-haiku-4-5"

    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        max_tokens: int,
    ) -> Completion:
        name = threading.current_thread().name
        [key] = [key for key in self.scripts if name.endswith(f"-{key}")]
        return self.scripts[key].complete(system, messages, tools, max_tokens)

    def complete_json(
        self, system: str, prompt: str, schema: dict[str, Any], max_tokens: int
    ) -> tuple[dict[str, Any], Usage]:
        self.verifier_threads.append(threading.current_thread().name)
        is_quiz = "answer" in schema.get("properties", {})
        return (haiku_reply() if is_quiz else {"explanation_problems": []}), CALL_USAGE

    def count_json_tokens(self, system: str, prompt: str, schema: dict[str, Any]) -> int:
        return (len(system) + len(prompt)) // 4


def test_a_whole_search_through_the_real_loop_and_verifiers(
    monkeypatch: pytest.MonkeyPatch, web: FakeWeb, http: httpx2.Client
) -> None:
    web.add(WIKI_API, wiki_extract)
    # Each run reads the article, then answers; then the Haiku verifier checks it.
    llm = PerItemLLM(
        {
            f"quiz-{level}": FakeLLM([completion(FETCH), completion(quiz_answer(level))])
            for level in LEVELS
        }
        | {
            f"learn-{level}": FakeLLM([completion(FETCH), completion(learn_answer(level))])
            for level in LEVELS
        }
    )
    # The real loops, reading the fake web instead of the network.
    monkeypatch.setattr(ondemand, "run_learn", functools.partial(run_learn, http_client=http))
    monkeypatch.setattr(ondemand, "run_quiz", functools.partial(run_quiz, http_client=http))
    live, store = services(llm=llm, jev=FakeJev())

    events = list(research(SEARCH, live))

    assert result_keys(events) == EVERY_ITEM
    assert of_type(events, MissedEvent) == []
    # The verifier's own threads carry the item's name, so a 429 there says which item met it.
    assert sorted(name.rsplit("_", 1)[0] for name in llm.verifier_threads) == sorted(
        f"live-search-100-{key}" for key in EVERY_ITEM
    )
    assert {outcome for _, outcome, _ in store.settled().values()} == {"published"}
    assert len(store.finished) == 6
    # Each run settles at its own measured cost, far below its reservation.
    assert all(0 < spent < Settings().max_job_cost_usd for _, spent, _, _ in store.finished)
    assert all(p.item is not None and p.item.status == "published" for p in store.payloads)
    fetched = [line.detail for line in of_type(events, LogEvent) if line.label == "fetch_page"]
    assert fetched == ["en.wikipedia.org/wiki/Neutron_star"] * 6
    # Every run moves through every stage in order, each named by its real work, before its item.
    for key in EVERY_ITEM:
        noun = "question" if key.startswith("quiz") else "explanation"
        progress = [event for event in of_type(events, ProgressEvent) if event.key == key]
        assert [(event.stage, event.status) for event in progress] == [
            ("search", "Choosing where to look"),
            ("read", "Reading en.wikipedia.org"),
            ("write", f"Checking the {noun}'s quotes and numbers against its pages"),
            ("verify", f"Checking the {noun} against 1 page"),
        ]
        last = max(index for index, event in enumerate(events) if event in progress)
        result = next(
            index
            for index, event in enumerate(events)
            if isinstance(event, ResultEvent) and event.key == key
        )
        assert last < result


# --- The endpoint ------------------------------------------------------------------------------


def post(body: object, visitor: str = "v1") -> ApiRequest:
    return ApiRequest("POST", "/api/research", body=json.dumps(body).encode(), visitor=visitor)


def test_the_endpoint_checks_its_input_before_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    good = {"topic": "neutron stars"}

    assert research_api.handle(ApiRequest("GET", "/api/research")).status == 405  # type: ignore[union-attr]
    assert research_api.handle(post({"topic": "x"})).status == 400  # type: ignore[union-attr]
    # A topic or Surprise me, exactly one of them.
    assert research_api.handle(post({})).status == 400  # type: ignore[union-attr]
    assert research_api.handle(post({"surprise": False})).status == 400  # type: ignore[union-attr]
    assert research_api.handle(post({**good, "surprise": True})).status == 400  # type: ignore[union-attr]
    bad_topic = research_api.handle(post({**good, "topic": "https://evil.example"}))
    assert bad_topic.status == 400 and "link" in bad_topic.body["error"]  # type: ignore[union-attr,index]
    assert research_api.handle(post(good, visitor="")).status == 503  # type: ignore[union-attr]

    seen: list[SearchRequest] = []

    def fake_research(request: SearchRequest, live: Services) -> Generator[ResearchEvent]:
        seen.append(request)
        yield RejectedEvent(message="no")

    monkeypatch.setattr(research_api, "services", lambda: services()[0])
    monkeypatch.setattr(research_api, "research", fake_research)
    response = research_api.handle(post(good))

    assert isinstance(response, StreamResponse)
    assert list(response.events) == [{"type": "rejected", "message": "no"}]
    # A page loaded before every search made all three levels still sends a difficulty.
    for body in ({**good, "difficulty": "medium"}, {"surprise": True}):
        later = research_api.handle(post(body))
        assert isinstance(later, StreamResponse)
        list(later.events)
    assert seen == [
        SearchRequest(topic="Neutron stars", visitor="v1"),
        SearchRequest(topic="Neutron stars", visitor="v1"),
        SearchRequest(topic=None, visitor="v1"),
    ]


def test_the_endpoint_answers_503_when_live_research_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(research_api, "_services", None)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    response = research_api.handle(post({"topic": "neutron stars"}))

    assert isinstance(response, ApiResponse) and response.status == 503
    assert research_api._services is None  # nothing half-built is kept


def test_the_shared_anthropic_client_logs_rate_limits() -> None:
    client = research_api.anthropic_client()
    try:
        assert client.max_retries == research_api.ANTHROPIC_MAX_RETRIES
        assert client._client.event_hooks["response"] == [research_api.log_rate_limit]
    finally:
        client.close()


def test_every_429_and_its_retry_get_one_log_line_naming_the_thread(
    capsys: pytest.CaptureFixture[str],
) -> None:
    limited = httpx2.Response(
        429,
        headers={
            "retry-after-ms": "1",
            "retry-after": "1",
            "anthropic-ratelimit-requests-remaining": "0",
        },
        json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}},
    )
    http = anthropic.DefaultHttpxClient(
        transport=httpx2.MockTransport(lambda _: limited),
        event_hooks={"response": [research_api.log_rate_limit]},
    )
    client = anthropic.Anthropic(api_key="test", max_retries=1, http_client=http)

    def call() -> None:
        with pytest.raises(anthropic.RateLimitError):
            client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )

    worker = threading.Thread(target=call, name="live-search-7-quiz-easy")
    worker.start()
    worker.join()
    client.close()

    lines = [line for line in capsys.readouterr().err.splitlines() if "anthropic 429" in line]
    assert len(lines) == 2  # the first call and its one retry
    assert all("thread=live-search-7-quiz-easy" in line for line in lines)
    assert "path=/v1/messages" in lines[0] and "requests_left=0" in lines[0]


def test_other_responses_are_not_logged(capsys: pytest.CaptureFixture[str]) -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    research_api.log_rate_limit(httpx2.Response(200, request=request))
    research_api.log_rate_limit(httpx2.Response(529, request=request))

    assert capsys.readouterr().err == ""
