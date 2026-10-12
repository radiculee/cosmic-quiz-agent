"""Live searches on the web page: the topic check, the plan, the guardrails and the streamed runs.

Most tests replace each agent run and the gate with a stored record; one plays a whole search
through the real loop and verifiers with the scripted fake model. Nothing touches the network or
a paid API.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx2
import pytest

import agent.ondemand as ondemand
from agent.bank import BankTopic, LearnItem, QuizQuestion, ShownStatus, SourceCheck
from agent.config import Settings
from agent.limits import LIMIT_MESSAGES, LIMITS, LimitName, LimitSettings, OnDemandUsage, RunSlot
from agent.loop import run_learn, run_quiz
from agent.ondemand import (
    FallbackEvent,
    LogEvent,
    MissedEvent,
    PlanEvent,
    PlannedItem,
    RejectedEvent,
    ResearchEvent,
    ResultEvent,
    SearchRequest,
    Services,
    StatsEvent,
    plan_search,
    research,
    run_budget,
    step_event,
    tool_detail,
)
from agent.rest import StoreError
from agent.schemas import Difficulty, ItemRecord, Mode, RunResult, Status, Step
from agent.store import ItemPayload, OnDemandOutcome, RecordedIds
from agent.topic_check import (
    InvalidTopicError,
    TopicCheckError,
    TopicVerdict,
    clean_topic,
    keyword_judge,
    verdict,
)
from agent.web import ApiRequest, ApiResponse, StreamResponse
from api import research as research_api
from tests.conftest import FakeLLM, FakeWeb, completion
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


# --- The plan ----------------------------------------------------------------------------------


def keys(items: list[PlannedItem], source: str | None = None) -> list[str]:
    return [item.key for item in items if source is None or item.source == source]


def test_a_search_plans_the_questions_first_and_the_explanation_last() -> None:
    assert keys(plan_search("medium", None)) == [
        "quiz-medium",
        "quiz-easy",
        "quiz-hard",
        "learn-medium",
    ]
    assert keys(plan_search("hard", None)) == [
        "quiz-hard",
        "quiz-easy",
        "quiz-medium",
        "learn-hard",
    ]
    assert all(item.source == "live" for item in plan_search("easy", None))


def test_the_plan_takes_from_the_bank_what_it_already_has() -> None:
    # Like "Black holes": questions at two levels, no explanation.
    have = BankTopic(name="Black holes", kind="evergreen", learn=["easy"], quiz=["easy", "hard"])

    plan = plan_search("medium", have)

    assert keys(plan, "live") == ["quiz-medium", "learn-medium"]
    assert keys(plan, "bank") == ["quiz-easy", "quiz-hard"]


def test_a_late_run_gets_a_shorter_agent_budget_so_the_search_ends_in_time() -> None:
    settings = Settings()

    assert run_budget(settings, 0.0) == settings.max_seconds  # every typical run
    assert run_budget(settings, 100.0) == settings.max_seconds
    assert run_budget(settings, 150.0) == pytest.approx(90.0)
    # The last moment a run may start still leaves it time to finish under the limit.
    at_cutoff = run_budget(settings, ondemand.RUN_START_SECONDS)
    assert at_cutoff > 0
    assert ondemand.RUN_START_SECONDS + at_cutoff + ondemand.VERIFY_SECONDS <= (
        ondemand.SEARCH_SECONDS
    )
    assert ondemand.SEARCH_SECONDS < 300  # Vercel's limit


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
        self, known: str | None = None, have: BankTopic | None = None, down: bool = False
    ) -> None:
        self.known, self.have, self.down = known, have, down

    def topic_named(self, name: str) -> str | None:
        if self.down:
            raise StoreError("down")
        return self.known

    def coverage(self, topic: str) -> BankTopic | None:
        return self.have


@dataclass
class FakeStore:
    # Limits that refuse the n-th reservation (0 = the run that opens the search).
    refuse: dict[int, LimitName] = field(default_factory=dict)
    down: bool = False
    began: list[tuple[str, str, Mode, Difficulty, int | None]] = field(default_factory=list)
    finished: list[tuple[int, float, OnDemandOutcome, int | None]] = field(default_factory=list)
    payloads: list[ItemPayload] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    # What the limits have counted so far today and this month, read before the paid check.
    usage: OnDemandUsage = field(
        default_factory=lambda: OnDemandUsage(
            visitor_searches_today=0, searches_today=0, usd_today=0.0, usd_this_month=0.0
        )
    )

    def on_demand_usage(self, user_hash: str, now: datetime) -> OnDemandUsage:
        if self.down:
            raise StoreError("down")
        return self.usage

    def begin_on_demand_run(
        self,
        user_hash: str,
        topic: str,
        mode: Mode,
        difficulty: Difficulty,
        reserve_usd: float,
        limits: LimitSettings,
        search_id: int | None = None,
    ) -> RunSlot:
        number = len(self.began)
        self.began.append((user_hash, topic, mode, difficulty, search_id))
        self.calls.append("begin")
        assert reserve_usd == Settings().max_job_cost_usd
        if self.down:
            raise StoreError("down")
        if number in self.refuse:
            return RunSlot(ok=False, limit=self.refuse[number])
        return RunSlot(ok=True, id=100 + number)

    def finish_on_demand_run(
        self, slot_id: int, spent_usd: float, outcome: OnDemandOutcome, run_id: int | None
    ) -> None:
        self.finished.append((slot_id, spent_usd, outcome, run_id))
        self.calls.append("finish")

    def record_item(self, payload: ItemPayload) -> RecordedIds:
        self.payloads.append(payload)
        number = len(self.payloads)
        return RecordedIds(topic_id=1, run_id=200 + number, item_id=40 + number)


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
) -> tuple[Services, FakeStore]:
    store = store or FakeStore()
    built = Services(
        judge=judge or FakeJudge(ACCEPT),
        bank=bank or FakeBank(),
        results=FakeResults(store, status),
        store=store,
        llm=llm or object(),  # type: ignore[arg-type]
        jev=jev,  # type: ignore[arg-type]
        settings=Settings(),
        limits=LIMITS,
        sign=lambda purpose, value: f"signed:{purpose}:{value}",
    )
    return built, store


ACCEPT = verdict(0.98, 0.97, "jev-1.13.0")
SEARCH = SearchRequest(topic="Neutron stars", difficulty="medium", visitor="v1")
EVERY_ITEM = ["quiz-medium", "quiz-easy", "quiz-hard", "learn-medium"]


@dataclass
class Script:
    """What the replaced runs saw: each run's key and its agent time budget."""

    runs: list[tuple[str, float]] = field(default_factory=list)


def script(
    monkeypatch: pytest.MonkeyPatch,
    statuses: dict[str, Status | None] | None = None,
    crash: frozenset[str] = frozenset(),
) -> Script:
    """Replace each agent run and the gate with the stored quiz record, made for the run's mode
    and difficulty and decided as `statuses` says (published by default)."""
    record = quiz_record()
    seen = Script()

    def fake_run(mode: Mode) -> Callable[..., RunResult]:
        def run(
            topic: str,
            difficulty: Difficulty,
            llm: object,
            settings: Settings,
            on_step: Callable[[Step], None],
        ) -> RunResult:
            key = f"{mode}-{difficulty}"
            seen.runs.append((key, settings.max_seconds))
            if key in crash:
                raise RuntimeError("the agent fell over")
            for step in record.run.steps:
                on_step(step)
            return record.run.model_copy(update={"mode": mode, "difficulty": difficulty})

        return run

    def fake_decide(result: RunResult, *_: object) -> ItemRecord:
        status = (statuses or {}).get(f"{result.mode}-{result.difficulty}", "published")
        return record.model_copy(update={"run": result, "status": status})

    monkeypatch.setattr(ondemand, "run_learn", fake_run("learn"))
    monkeypatch.setattr(ondemand, "run_quiz", fake_run("quiz"))
    monkeypatch.setattr(ondemand, "verify_and_decide", fake_decide)
    return seen


def of_type[E](events: list[ResearchEvent], kind: type[E]) -> list[E]:
    return [event for event in events if isinstance(event, kind)]


# --- Searches ----------------------------------------------------------------------------------


def test_a_search_makes_every_item_one_run_at_a_time_and_counts_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch)
    live, store = services()

    events = list(research(SEARCH, live))

    plan = events[0]
    assert isinstance(plan, PlanEvent) and plan.topic == "Neutron stars"
    assert keys(plan.items, "live") == EVERY_ITEM
    results = of_type(events, ResultEvent)
    assert [result.key for result in results] == EVERY_ITEM
    assert results[-1].reveal_token is None  # the explanation needs no token
    assert [result.reveal_token for result in results[:-1]] == [
        f"signed:reveal:{result.item.id}" for result in results[:-1]
    ]
    assert "correct_index" not in json.dumps([r.model_dump(mode="json") for r in results])

    # The first run opens the search; the later runs join it, one at a time.
    assert [search_id for *_, search_id in store.began] == [None, 100, 100, 100]
    assert store.calls == ["begin", "finish"] * 4
    record = quiz_record()
    assert [(slot, outcome) for slot, _, outcome, _ in store.finished] == [
        (100, "published"),
        (101, "published"),
        (102, "published"),
        (103, "published"),
    ]
    assert all(
        spent == pytest.approx(record.anthropic_cost_usd) for _, spent, _, _ in store.finished
    )
    assert [(p.run.mode, p.run.difficulty, p.run.source) for p in store.payloads] == [
        ("quiz", "medium", "on_demand"),
        ("quiz", "easy", "on_demand"),
        ("quiz", "hard", "on_demand"),
        ("learn", "medium", "on_demand"),
    ]

    # Every line after the on-topic check names its item.
    lines = of_type(events, LogEvent)
    assert lines[0].label == "On-topic check (Jev)" and lines[0].key is None
    assert all(line.key in EVERY_ITEM for line in lines[1:])
    budgets = [line.detail for line in lines if line.label == "Budget"]
    assert budgets[0] == "up to $0.17 reserved for the MEDIUM question"
    assert budgets[1] == "up to $0.17 reserved for the EASY question"
    assert budgets[3] == "up to $0.17 reserved for the MEDIUM explanation"
    # Which option the sources support would give a quiz answer away.
    jev_lines = [line for line in lines if line.label.startswith("Jev")]
    assert jev_lines and all(line.verdict is None for line in jev_lines)


def test_a_topic_the_bank_has_at_every_level_is_free_and_not_counted() -> None:
    have = BankTopic(
        name="Neutron stars", kind="evergreen", learn=["medium"], quiz=["easy", "medium", "hard"]
    )
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
    request = SearchRequest(topic="Black Holes", difficulty="medium", visitor="v1")
    live, store = services(bank=FakeBank(known="Black holes", have=have))

    events = list(research(request, live))

    plan = events[0]
    assert isinstance(plan, PlanEvent) and plan.topic == "Black holes"  # the bank's spelling
    assert keys(plan.items, "bank") == ["quiz-easy", "quiz-hard"]
    assert [result.key for result in of_type(events, ResultEvent)] == [
        "quiz-medium",
        "learn-medium",
    ]
    assert [(topic, mode, level) for _, topic, mode, level, _ in store.began] == [
        ("Black holes", "quiz", "medium"),
        ("Black holes", "learn", "medium"),
    ]


def test_a_visitor_over_the_daily_limit_keeps_what_the_bank_has() -> None:
    have = BankTopic(name="Black holes", kind="evergreen", learn=[], quiz=["easy"])
    store = FakeStore(refuse={0: "user_day"})
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
        ({"usd_today": 0.34, "usd_this_month": 0.34}, "day_usd"),
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
    assert last.message == LIMIT_MESSAGES[limit]
    assert judge.topics == [] and store.began == []  # nothing paid, nothing reserved


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
    assert [result.key for result in of_type(events, ResultEvent)] == [
        "quiz-easy",
        "quiz-hard",
        "learn-medium",
    ]
    assert len(store.payloads) == 4  # the discarded run is still stored
    assert store.finished[0][2] == "discarded"


def test_every_run_that_made_a_record_sends_its_figures_before_its_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, {"quiz-medium": "discarded"}, crash=frozenset({"quiz-hard"}))
    live, _ = services()

    events = list(research(SEARCH, live))

    stats = of_type(events, StatsEvent)
    # The discarded run cost money too, so it counts towards the search; the crashed run made
    # no record, so it has no figures.
    assert [(s.key, s.stats.mode, s.stats.status) for s in stats] == [
        ("quiz-medium", "quiz", "discarded"),
        ("quiz-easy", "quiz", "published"),
        ("learn-medium", "learn", "published"),
    ]
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
    assert [result.key for result in of_type(events, ResultEvent)] == EVERY_ITEM
    assert [outcome for _, _, outcome, _ in store.finished] == ["published"] * 4


def test_a_crashed_run_keeps_its_reservation_and_the_search_goes_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, crash=frozenset({"quiz-medium"}))
    live, store = services()

    events = list(research(SEARCH, live))

    [missed] = of_type(events, MissedEvent)
    assert (missed.key, missed.reason) == ("quiz-medium", "failed")
    assert store.finished[0] == (100, Settings().max_job_cost_usd, "failed", None)
    assert [result.key for result in of_type(events, ResultEvent)] == EVERY_ITEM[1:]


def test_a_later_run_refused_by_a_cap_leaves_out_the_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch)
    store = FakeStore(refuse={2: "day_usd"})
    live, _ = services(store=store)

    events = list(research(SEARCH, live))

    assert [result.key for result in of_type(events, ResultEvent)] == EVERY_ITEM[:2]
    skipped = of_type(events, MissedEvent)
    # The explanation runs last, so a search cut short loses it before any question.
    assert [(m.key, m.reason) for m in skipped] == [
        ("quiz-hard", "skipped"),
        ("learn-medium", "skipped"),
    ]
    assert "today's budget" in skipped[0].message
    assert len(store.began) == 3 and len(store.finished) == 2


def test_no_run_starts_after_the_cutoff(monkeypatch: pytest.MonkeyPatch) -> None:
    script(monkeypatch)
    monkeypatch.setattr(ondemand, "RUN_START_SECONDS", -1.0)
    live, store = services()

    events = list(research(SEARCH, live))

    assert [result.key for result in of_type(events, ResultEvent)] == ["quiz-medium"]
    skipped = of_type(events, MissedEvent)
    assert [m.key for m in skipped] == EVERY_ITEM[1:]
    assert all("ran out of time" in m.message for m in skipped)
    assert len(store.began) == 1


def test_a_run_that_starts_late_is_given_only_the_time_left(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = script(monkeypatch)
    monkeypatch.setattr(ondemand, "SEARCH_SECONDS", 150.0)  # as if the search were late
    live, _ = services()

    events = list(research(SEARCH, live))

    assert all(seconds < Settings().max_seconds for _, seconds in seen.runs)
    assert any(line.label == "Time" for line in of_type(events, LogEvent))


def test_a_player_leaving_mid_search_still_gets_every_run_stored_and_settled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch)
    live, store = services()
    stream = research(SEARCH, live)

    assert isinstance(next(stream), PlanEvent)
    assert isinstance(next(stream), LogEvent)  # the on-topic check
    budget = next(stream)  # the first run is reserved and the search's thread has started
    stream.close()  # the player leaves: closing waits for the search to be stored

    assert isinstance(budget, LogEvent) and budget.label == "Budget"
    assert len(store.payloads) == 4
    assert [outcome for _, _, outcome, _ in store.finished] == ["published"] * 4


def test_the_verifier_s_reasons_are_kept_out_of_quiz_log_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script(monkeypatch, {key: "review" for key in EVERY_ITEM})
    live, _ = services(status="review")

    events = list(research(SEARCH, live))

    haiku = [e for e in of_type(events, LogEvent) if e.label == "Haiku verifier"]
    assert [line.detail for line in haiku if line.key != "learn-medium"] == ["borderline"] * 3
    assert all(r.item.status == "review" for r in of_type(events, ResultEvent))


# --- A whole search through the real loop and verifiers ---------------------------------------


def words(count: int) -> str:
    return " ".join(["word"] * count)


# Inside each level's word range (agent/loop.py WORD_LIMITS).
LENGTHS: dict[Difficulty, int] = {"easy": 100, "medium": 150, "hard": 190}


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


def test_a_whole_search_through_the_real_loop_and_verifiers(
    monkeypatch: pytest.MonkeyPatch, web: FakeWeb, http: httpx2.Client
) -> None:
    web.add(WIKI_API, wiki_extract)
    # Each run reads the article, then answers; then the Haiku verifier checks it.
    llm = FakeLLM(
        [
            completion(FETCH),
            completion(quiz_answer("medium")),
            completion(FETCH),
            completion(quiz_answer("easy")),
            completion(FETCH),
            completion(quiz_answer("hard")),
            completion(FETCH),
            completion(learn_answer("medium")),
        ],
        json_replies=[haiku_reply(), haiku_reply(), haiku_reply(), {"explanation_problems": []}],
    )
    # The real loops, reading the fake web instead of the network.
    monkeypatch.setattr(ondemand, "run_learn", functools.partial(run_learn, http_client=http))
    monkeypatch.setattr(ondemand, "run_quiz", functools.partial(run_quiz, http_client=http))
    live, store = services(llm=llm, jev=FakeJev())

    events = list(research(SEARCH, live))

    assert [result.key for result in of_type(events, ResultEvent)] == EVERY_ITEM
    assert of_type(events, MissedEvent) == []
    assert [outcome for _, _, outcome, _ in store.finished] == ["published"] * 4
    # Each run settles at its own measured cost, far below its reservation.
    assert all(0 < spent < Settings().max_job_cost_usd for _, spent, _, _ in store.finished)
    assert all(p.item is not None and p.item.status == "published" for p in store.payloads)
    fetched = [line.detail for line in of_type(events, LogEvent) if line.label == "fetch_page"]
    assert fetched == ["en.wikipedia.org/wiki/Neutron_star"] * 4


# --- The endpoint ------------------------------------------------------------------------------


def post(body: object, visitor: str = "v1") -> ApiRequest:
    return ApiRequest("POST", "/api/research", body=json.dumps(body).encode(), visitor=visitor)


def test_the_endpoint_checks_its_input_before_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    good = {"topic": "neutron stars", "difficulty": "medium"}

    assert research_api.handle(ApiRequest("GET", "/api/research")).status == 405  # type: ignore[union-attr]
    assert research_api.handle(post({"topic": "x"})).status == 400  # type: ignore[union-attr]
    # A search has no mode any more: it makes the explanation and the questions.
    assert research_api.handle(post({**good, "mode": "quiz"})).status == 400  # type: ignore[union-attr]
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
    assert seen == [SearchRequest(topic="Neutron stars", difficulty="medium", visitor="v1")]


def test_the_endpoint_answers_503_when_live_research_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(research_api, "_services", None)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    response = research_api.handle(post({"topic": "neutron stars", "difficulty": "medium"}))

    assert isinstance(response, ApiResponse) and response.status == 503
    assert research_api._services is None  # nothing half-built is kept
