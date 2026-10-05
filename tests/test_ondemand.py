"""Custom topics on demand: the topic check, the guardrails and the streamed live run.

The agent run and the gate are replaced by a stored record, so nothing here touches the network
or a paid API.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Generator
from dataclasses import dataclass, field

import pytest

import agent.ondemand as ondemand
from agent.bank import LearnItem, QuizQuestion, SourceCheck
from agent.config import Settings
from agent.limits import LIMITS, LimitSettings, RunSlot
from agent.ondemand import (
    FallbackEvent,
    LiveJob,
    LogEvent,
    RejectedEvent,
    ResearchEvent,
    ResultEvent,
    Services,
    research,
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
from tests.test_store import quiz_record

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

    clock = ondemand._Clock()
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

    submit = Step(index=2, kind="model", summary="submit_quiz (stop: tool_use)", seconds=2.0)
    assert step_event(submit, clock, "question").detail == "writes the question"
    plan = Step(
        index=0, kind="model", summary="search_wikipedia, fetch_page (stop: tool_use)", seconds=1
    )
    assert step_event(plan, clock, "question").detail == "next: search_wikipedia, fetch_page"


# --- The live run ------------------------------------------------------------------------------


class FakeJudge:
    def __init__(self, result: TopicVerdict | Exception) -> None:
        self.result = result
        self.topics: list[str] = []

    def judge(self, topic: str) -> TopicVerdict:
        self.topics.append(topic)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


QUESTION = QuizQuestion(
    id=41, difficulty="medium", topic="Neutron stars", question="Q?", options=["a", "b", "c", "d"]
)


class FakeBank:
    def __init__(
        self, known: str | None = None, has: bool = False, item: QuizQuestion | LearnItem = QUESTION
    ) -> None:
        self.known, self.has, self.item = known, has, item

    def topic_named(self, name: str) -> str | None:
        return self.known

    def has_item(self, topic: str, mode: Mode, difficulty: Difficulty) -> bool:
        return self.has


class FakeResults:
    def __init__(self, item: QuizQuestion | LearnItem) -> None:
        self.stored = item

    def item(self, item_id: int) -> QuizQuestion | LearnItem | None:
        return self.stored


@dataclass
class FakeStore:
    slot: RunSlot | Exception = field(default_factory=lambda: RunSlot(ok=True, id=5))
    began: list[tuple[str, str, float]] = field(default_factory=list)
    finished: list[tuple[int, float, OnDemandOutcome, int | None]] = field(default_factory=list)
    payloads: list[ItemPayload] = field(default_factory=list)

    def begin_on_demand_run(
        self,
        user_hash: str,
        topic: str,
        mode: Mode,
        difficulty: Difficulty,
        reserve_usd: float,
        limits: LimitSettings,
    ) -> RunSlot:
        self.began.append((user_hash, topic, reserve_usd))
        if isinstance(self.slot, Exception):
            raise self.slot
        return self.slot

    def finish_on_demand_run(
        self, slot_id: int, spent_usd: float, outcome: OnDemandOutcome, run_id: int | None
    ) -> None:
        self.finished.append((slot_id, spent_usd, outcome, run_id))

    def record_item(self, payload: ItemPayload) -> RecordedIds:
        self.payloads.append(payload)
        return RecordedIds(topic_id=1, run_id=99, item_id=41)


def services(
    judge: FakeJudge, bank: FakeBank | None = None, store: FakeStore | None = None
) -> tuple[Services, FakeBank, FakeStore]:
    bank = bank or FakeBank()
    store = store or FakeStore()
    built = Services(
        judge=judge,
        bank=bank,
        results=FakeResults(bank.item),
        store=store,
        llm=object(),  # type: ignore[arg-type]
        jev=None,
        settings=Settings(),
        limits=LIMITS,
        sign=lambda purpose, value: f"signed:{purpose}:{value}",
    )
    return built, bank, store


ACCEPT = verdict(0.98, 0.97, "jev-1.13.0")
JOB = LiveJob(topic="Neutron stars", mode="quiz", difficulty="medium", visitor="v1")


def run_with(
    monkeypatch: pytest.MonkeyPatch,
    status: Status | None,
    *,
    crash: bool = False,
) -> Callable[[Services], list[ResearchEvent]]:
    """Replace the agent run and the gate with the stored quiz record, decided as `status`."""
    record = quiz_record()

    def fake_run(
        topic: str,
        difficulty: Difficulty,
        llm: object,
        settings: Settings,
        on_step: Callable[[Step], None],
    ) -> RunResult:
        if crash:
            raise RuntimeError("the agent fell over")
        for step in record.run.steps:
            on_step(step)
        return record.run

    def fake_decide(result: RunResult, *_: object) -> ItemRecord:
        return record.model_copy(update={"status": status})

    monkeypatch.setattr(ondemand, "run_quiz", fake_run)
    monkeypatch.setattr(ondemand, "verify_and_decide", fake_decide)
    return lambda live: list(research(JOB, live))


def test_a_topic_already_in_the_bank_is_served_from_it_for_free() -> None:
    judge = FakeJudge(ACCEPT)
    live, _, store = services(judge, FakeBank(known="Neutron stars", has=True))

    events = list(research(JOB, live))

    assert events == [
        FallbackEvent(
            reason="in_bank", message="This topic is already in the bank.", topic="Neutron stars"
        )
    ]
    assert judge.topics == [] and store.began == []


def test_an_off_topic_topic_is_rejected_before_any_run() -> None:
    live, _, store = services(FakeJudge(verdict(0.03, 0.97, "jev")))

    events = list(research(JOB, live))

    assert isinstance(events[0], LogEvent) and events[0].tone == "warn"
    assert isinstance(events[-1], RejectedEvent) and "astronomy" in events[-1].message
    assert store.began == []


def test_a_visitor_over_a_limit_is_sent_back_to_the_bank() -> None:
    store = FakeStore(slot=RunSlot(ok=False, limit="user_day"))
    live, _, _ = services(FakeJudge(ACCEPT), store=store)

    events = list(research(JOB, live))

    assert isinstance(events[-1], FallbackEvent) and events[-1].reason == "limit"
    assert "3 custom topics today" in events[-1].message
    assert store.finished == []


@pytest.mark.parametrize("failure", ["judge", "store"])
def test_an_unreachable_check_falls_back_without_running(failure: str) -> None:
    judge = FakeJudge(TopicCheckError("down") if failure == "judge" else ACCEPT)
    store = FakeStore(slot=StoreError("down") if failure == "store" else RunSlot(ok=True, id=5))
    live, _, _ = services(judge, store=store)

    events = list(research(JOB, live))

    assert isinstance(events[-1], FallbackEvent) and events[-1].reason == "unavailable"
    assert store.finished == []


def test_a_published_live_question_is_stored_settled_and_sent_without_its_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = run_with(monkeypatch, "published")
    live, _, store = services(FakeJudge(ACCEPT))

    events = run(live)

    labels = [e.label for e in events if isinstance(e, LogEvent)]
    assert labels[:3] == ["On-topic check (Jev)", "Budget", "Agent"]
    assert "fetch_page" in labels and "Code checks" in labels and "Haiku verifier" in labels
    jev_lines = [e for e in events if isinstance(e, LogEvent) and e.label.startswith("Jev")]
    assert jev_lines and all(line.verdict is None for line in jev_lines)  # no spoilers
    result = events[-1]
    assert isinstance(result, ResultEvent) and result.item == QUESTION
    assert result.reveal_token == "signed:reveal:41"
    assert "correct_index" not in json.dumps(result.model_dump(mode="json"))

    payload = store.payloads[0]
    assert payload.run.source == "on_demand" and payload.topic.kind == "custom"
    record = quiz_record()
    [(slot_id, spent, outcome, run_id)] = store.finished
    assert (slot_id, outcome, run_id) == (5, "published", 99)
    assert spent == pytest.approx(record.anthropic_cost_usd)
    assert store.began == [("v1", "Neutron stars", Settings().max_job_cost_usd)]


def test_a_discarded_live_run_is_kept_and_the_player_gets_the_bank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = run_with(monkeypatch, "discarded")
    live, _, store = services(FakeJudge(ACCEPT))

    events = run(live)

    assert isinstance(events[-1], FallbackEvent) and events[-1].reason == "discarded"
    assert len(store.payloads) == 1  # the paid run is still stored
    assert store.finished[0][2] == "discarded"


def test_a_crashed_run_keeps_its_reservation_and_still_ends_the_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = run_with(monkeypatch, None, crash=True)
    live, _, store = services(FakeJudge(ACCEPT))

    events = run(live)

    assert isinstance(events[-1], FallbackEvent) and events[-1].reason == "unavailable"
    assert store.finished == [(5, Settings().max_job_cost_usd, "failed", None)]
    assert store.payloads == []


def test_a_live_learn_item_needs_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    learn = LearnItem(
        id=42,
        difficulty="easy",
        topic="Neutron stars",
        explanation="...",
        sources=[],
        source_check=SourceCheck(options=[], sentences=0, sentences_supported=0),
        status="review",
        doubts=["explanation: a small doubt"],
    )
    run = run_with(monkeypatch, "review")
    live, _, _ = services(FakeJudge(ACCEPT), FakeBank(item=learn))

    result = run(live)[-1]

    assert isinstance(result, ResultEvent) and result.reveal_token is None
    assert isinstance(result.item, LearnItem) and result.item.status == "review"


# --- The endpoint ------------------------------------------------------------------------------


def post(body: object, visitor: str = "v1") -> ApiRequest:
    return ApiRequest("POST", "/api/research", body=json.dumps(body).encode(), visitor=visitor)


def test_the_endpoint_checks_its_input_before_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    good = {"topic": "neutron stars", "mode": "quiz", "difficulty": "medium"}

    assert research_api.handle(ApiRequest("GET", "/api/research")).status == 405  # type: ignore[union-attr]
    assert research_api.handle(post({"topic": "x"})).status == 400  # type: ignore[union-attr]
    bad_topic = research_api.handle(post({**good, "topic": "https://evil.example"}))
    assert bad_topic.status == 400 and "link" in bad_topic.body["error"]  # type: ignore[union-attr,index]
    assert research_api.handle(post(good, visitor="")).status == 503  # type: ignore[union-attr]

    seen: list[LiveJob] = []

    def fake_research(job: LiveJob, live: Services) -> Generator[ResearchEvent]:
        seen.append(job)
        yield RejectedEvent(message="no")

    monkeypatch.setattr(research_api, "services", lambda: services(FakeJudge(ACCEPT))[0])
    monkeypatch.setattr(research_api, "research", fake_research)
    response = research_api.handle(post(good))

    assert isinstance(response, StreamResponse)
    assert list(response.events) == [{"type": "rejected", "message": "no"}]
    assert seen == [LiveJob(topic="Neutron stars", mode="quiz", difficulty="medium", visitor="v1")]


def test_a_player_leaving_right_after_the_reservation_still_settles_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_with(monkeypatch, "published")
    live, _, store = services(FakeJudge(ACCEPT))
    stream = research(JOB, live)

    first = next(stream)  # the on-topic check
    budget = next(stream)  # the slot is reserved and the run has started
    stream.close()  # the player leaves: closing waits for the run to be stored

    assert isinstance(first, LogEvent) and isinstance(budget, LogEvent)
    assert budget.label == "Budget"
    assert len(store.payloads) == 1
    assert [(slot, outcome) for slot, _, outcome, _ in store.finished] == [(5, "published")]


def test_the_verifier_s_reasons_are_kept_out_of_a_quiz_log(monkeypatch: pytest.MonkeyPatch) -> None:
    run = run_with(monkeypatch, "review")
    live, _, _ = services(FakeJudge(ACCEPT))

    haiku = [e for e in run(live) if isinstance(e, LogEvent) and e.label == "Haiku verifier"]

    assert [line.detail for line in haiku] == ["borderline"]


def test_the_endpoint_answers_503_when_live_research_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(research_api, "_services", None)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    good = {"topic": "neutron stars", "mode": "quiz", "difficulty": "medium"}

    response = research_api.handle(post(good))

    assert isinstance(response, ApiResponse) and response.status == 503
    assert research_api._services is None  # nothing half-built is kept
