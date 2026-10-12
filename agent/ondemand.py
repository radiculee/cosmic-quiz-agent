"""Live searches on the web page: the guardrails, the runs, and the events streamed to the player.

A search makes a whole topic (docs/PLAN.md Session 8, decided 2026-10-08): a QUIZ question at
each level and the LEARN explanation at the chosen level, leaving out any the bank already has.
The questions come first and the explanation last (changed 2026-10-10 by Vedant), so the first
question is ready sooner and the explanation, which can give answers away, is read after them.
`research` yields events while it works:

1. The plan: which items the search makes live and which the bank already has (free). When the
   bank has them all, that is the whole search: free, and not counted.
2. The on-topic check (`agent/topic_check.py`) rejects anything that is not a plain astronomy
   or space topic. It runs once per search, and only after the visitor's limits and the global
   caps are read: it is paid, so a search they would refuse ends before it.
3. The first run is reserved, which opens the search and counts it against the visitor's daily
   limit and everyone's (`agent/limits.py`, migration 006). Over a limit, the player keeps what
   the bank has.
4. The runs go one at a time, each the Curator's evaluated pipeline: the agent researches the
   item and the same three-layer gate decides (`agent/publish.py`). Every step is streamed as a
   log line, including each Jev claim check. Each later run reserves its own slot in the search,
   so only one run's cost bound is ever reserved, and none starts once the search has run for
   three minutes.
5. Each run is stored in the bank whatever the outcome, its real cost settles its reservation,
   and a published or review item is sent to the player. A quiz item comes without its answer
   and with a signed token that lets /api/reveal answer it once the player has picked.
6. Each run that produced a record also sends what it measured (`agent/run_stats.py`), for the
   analytics panel: numbers only, so nothing in it can give a quiz answer away.

Every event after the plan that concerns one item names it (`key`, such as "quiz-easy").

From step 4 the work runs on its own thread, started before anything more is streamed: a run
that has started is paid for, so it is always finished, stored and settled, and the search's
later runs with it. If the player leaves, closing the stream waits for that thread, which keeps
the request (and a serverless instance) alive until the search is stored.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
import traceback
from collections.abc import Callable, Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

from agent.bank import DIFFICULTY_ORDER, BankTopic, LearnItem, QuizQuestion
from agent.config import Settings
from agent.limits import LIMIT_MESSAGES, LimitSettings, OnDemandUsage, RunSlot, search_limit
from agent.llm import LLMProvider
from agent.loop import run_learn, run_quiz
from agent.publish import verify_and_decide
from agent.rest import StoreError
from agent.run_stats import RunStats, run_stats
from agent.schemas import Difficulty, ItemRecord, JevVerdict, Mode, Step
from agent.store import ItemPayload, OnDemandOutcome, RecordedIds, TopicRef, build_payload
from agent.topic_check import TopicCheckError, TopicJudge
from agent.verifiers import JevClient

REVEAL_PURPOSE = "reveal"

# Vercel ends a function at 300 seconds, so a search must be stored and settled by this time.
SEARCH_SECONDS = 280.0
# No run starts once a search has run this long (decided 2026-10-08): a slow search leaves out
# its last questions instead of passing the limit.
RUN_START_SECONDS = 180.0
# Kept back from a run's agent time budget for the verifiers and the save. A run that starts in
# the first two minutes keeps the full budget; a later one gets what is left (decided
# 2026-10-08), so even the last run finishes inside SEARCH_SECONDS.
VERIFY_SECONDS = 40.0

# --- Events ------------------------------------------------------------------------------------

Tone = Literal["info", "ok", "warn"]
FallbackReason = Literal["limit", "unavailable"]
MissedReason = Literal["discarded", "failed", "skipped"]
ItemSource = Literal["live", "bank"]

NOUNS: dict[Mode, str] = {"learn": "explanation", "quiz": "question"}


def item_key(mode: Mode, difficulty: Difficulty) -> str:
    """How events name an item of a search: "learn-medium", "quiz-easy" and so on."""
    return f"{mode}-{difficulty}"


class PlannedItem(BaseModel):
    """One item a search shows: made live, or already in the bank (free)."""

    model_config = ConfigDict(frozen=True)

    key: str
    mode: Mode
    difficulty: Difficulty
    source: ItemSource

    @property
    def label(self) -> str:
        """For log lines and messages: "the EASY question"."""
        return f"the {self.difficulty.upper()} {NOUNS[self.mode]}"


class PlanEvent(BaseModel):
    """What the search will show, in order. `topic` is the bank's spelling when it has the topic;
    the page loads the bank's items itself."""

    model_config = ConfigDict(frozen=True)

    type: Literal["plan"] = "plan"
    topic: str
    items: list[PlannedItem]


class LogEvent(BaseModel):
    """One line of the agent log. `key` names the item it is about; None for the search."""

    model_config = ConfigDict(frozen=True)

    type: Literal["log"] = "log"
    key: str | None = None
    label: str
    detail: str = ""
    tone: Tone = "info"
    # Jev's verdict on a claim, when the line is a claim check (hidden for quiz options).
    verdict: JevVerdict | None = None
    confidence: float | None = None
    seconds: float = 0.0


class RejectedEvent(BaseModel):
    """The topic is not one the agent will research. Nothing was spent beyond the check."""

    model_config = ConfigDict(frozen=True)

    type: Literal["rejected"] = "rejected"
    message: str


class FallbackEvent(BaseModel):
    """No live research for this search (a limit, or the service is down). The bank's items in
    the plan are still shown, and the rest of the bank stays free to play."""

    model_config = ConfigDict(frozen=True)

    type: Literal["fallback"] = "fallback"
    reason: FallbackReason
    message: str


class ResultEvent(BaseModel):
    """A live item, published or in review. `reveal_token` unlocks a quiz item's answer."""

    model_config = ConfigDict(frozen=True)

    type: Literal["result"] = "result"
    key: str
    item: QuizQuestion | LearnItem
    reveal_token: str | None = None


class MissedEvent(BaseModel):
    """A live item the player will not get: the gate discarded it, its run failed, or it was
    not started (out of time, or a cap was reached)."""

    model_config = ConfigDict(frozen=True)

    type: Literal["missed"] = "missed"
    key: str
    reason: MissedReason
    message: str


class StatsEvent(BaseModel):
    """What one run measured, for the analytics panel. Sent for every run that produced a
    record, discarded ones included, so the search's totals hold everything it spent."""

    model_config = ConfigDict(frozen=True)

    type: Literal["stats"] = "stats"
    key: str
    stats: RunStats


ResearchEvent = (
    PlanEvent | LogEvent | RejectedEvent | FallbackEvent | ResultEvent | MissedEvent | StatsEvent
)


# --- What a search needs -----------------------------------------------------------------------


class LiveStore(Protocol):
    def on_demand_usage(self, user_hash: str, now: datetime) -> OnDemandUsage: ...

    def begin_on_demand_run(
        self,
        user_hash: str,
        topic: str,
        mode: Mode,
        difficulty: Difficulty,
        reserve_usd: float,
        limits: LimitSettings,
        search_id: int | None = None,
    ) -> RunSlot: ...

    def finish_on_demand_run(
        self, slot_id: int, spent_usd: float, outcome: OnDemandOutcome, run_id: int | None
    ) -> None: ...

    def record_item(self, payload: ItemPayload) -> RecordedIds: ...


class PublicBank(Protocol):
    def topic_named(self, name: str) -> str | None: ...

    def coverage(self, topic: str) -> BankTopic | None: ...


class StoredItems(Protocol):
    def item(self, item_id: int) -> QuizQuestion | LearnItem | None: ...


@dataclass(frozen=True)
class Services:
    """Everything `research` talks to, passed in so tests can replace each one. The clients are
    shared by every request a process serves (api/research.py), so nothing here closes them."""

    judge: TopicJudge
    bank: PublicBank  # the public bank (publishable key)
    results: StoredItems  # reads back a stored live item, review included (secret key)
    store: LiveStore
    llm: LLMProvider
    jev: JevClient | None
    settings: Settings
    limits: LimitSettings
    sign: Callable[[str, str], str]  # (purpose, value) -> token, see agent/web.py


@dataclass(frozen=True)
class SearchRequest:
    topic: str  # cleaned (agent/topic_check.clean_topic)
    difficulty: Difficulty  # the explanation's level, and the question shown first
    visitor: str  # salted hash of the IP address


@dataclass(frozen=True)
class _Search:
    id: int  # the id of the run that opened it (migration 006)
    topic: str  # in the bank's spelling when the bank has it
    visitor: str
    live: tuple[PlannedItem, ...]


class _Clock:
    """Seconds since the search began, stamped on every log line. `for_item` gives a clock
    that also names the item its lines are about."""

    def __init__(self, started: float | None = None, key: str | None = None) -> None:
        self.started = time.monotonic() if started is None else started
        self.key = key

    def for_item(self, key: str) -> _Clock:
        return _Clock(self.started, key)

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def log(self, label: str, detail: str = "", tone: Tone = "info", **extra: object) -> LogEvent:
        return LogEvent.model_validate(
            {
                "key": self.key,
                "label": label,
                "detail": detail,
                "tone": tone,
                "seconds": round(self.elapsed(), 1),
                **extra,
            }
        )


def plan_search(difficulty: Difficulty, have: BankTopic | None) -> list[PlannedItem]:
    """What a search makes, in order: a question at the chosen level, then at the other two,
    easiest first, then the explanation at the chosen level. Live items run in this order, so
    when a cap or the time limit cuts a search short, the explanation is what is left out. An
    item the bank already has is served from it, free."""
    wanted: list[tuple[Mode, Difficulty]] = [("quiz", difficulty)]
    wanted += [("quiz", level) for level in DIFFICULTY_ORDER if level != difficulty]
    wanted.append(("learn", difficulty))

    def in_bank(mode: Mode, level: Difficulty) -> bool:
        if have is None:
            return False
        return level in (have.learn if mode == "learn" else have.quiz)

    return [
        PlannedItem(
            key=item_key(mode, level),
            mode=mode,
            difficulty=level,
            source="bank" if in_bank(mode, level) else "live",
        )
        for mode, level in wanted
    ]


def run_budget(settings: Settings, elapsed: float) -> float:
    """The agent's time budget for a run starting `elapsed` seconds into the search: the full
    budget, or less for a late run, so the search is stored before SEARCH_SECONDS."""
    return min(settings.max_seconds, SEARCH_SECONDS - VERIFY_SECONDS - elapsed)


def research(request: SearchRequest, services: Services) -> Generator[ResearchEvent]:
    """Run one live search, yielding events as it goes (see the module docstring)."""
    clock = _Clock()

    try:
        known = services.bank.topic_named(request.topic)
        have = services.bank.coverage(known) if known is not None else None
    except StoreError as error:
        print(f"live search: bank lookup failed: {error}", file=sys.stderr)
        yield _unavailable()
        return
    topic = known or request.topic
    plan = plan_search(request.difficulty, have)
    yield PlanEvent(topic=topic, items=plan)
    live = tuple(item for item in plan if item.source == "live")
    if not live:
        return  # the bank has the whole topic: free, and not counted

    # The on-topic check is paid, so a search the limits would refuse ends before it
    # (docs/SECURITY_AUDIT.md S3). The database still decides when the first run starts.
    try:
        usage = services.store.on_demand_usage(request.visitor, datetime.now(UTC))
    except StoreError as error:
        print(f"live search: could not read the limits: {error}", file=sys.stderr)
        yield _unavailable()
        return
    refused = search_limit(usage, services.limits, services.settings.max_job_cost_usd)
    if refused is not None:
        yield FallbackEvent(reason="limit", message=LIMIT_MESSAGES[refused])
        return

    try:
        verdict = services.judge.judge(topic)
    except TopicCheckError as error:
        print(f"live search: topic check failed: {error}", file=sys.stderr)
        yield _unavailable()
        return
    # Every paid call is logged with its tokens and cost (CLAUDE.md rule 1); a rejected topic
    # leaves no other record.
    print(
        f"topic check: accepted={verdict.accepted} on_topic={verdict.on_topic:.2f} "
        f"plain={verdict.plain:.2f} judge={verdict.judge} tokens={verdict.input_tokens} "
        f"cost=${verdict.cost_usd:.6f}",
        file=sys.stderr,
    )
    yield clock.log(
        "On-topic check (Jev)",
        f"astronomy {verdict.on_topic:.2f}, plain topic {verdict.plain:.2f}",
        "ok" if verdict.accepted else "warn",
    )
    if not verdict.accepted:
        yield RejectedEvent(message=verdict.reason)
        return

    first = live[0]
    try:
        slot = services.store.begin_on_demand_run(
            request.visitor,
            topic,
            first.mode,
            first.difficulty,
            services.settings.max_job_cost_usd,
            services.limits,
        )
    except StoreError as error:
        print(f"live search: could not reserve a slot: {error}", file=sys.stderr)
        yield _unavailable()
        return
    if not slot.ok or slot.id is None:
        message = LIMIT_MESSAGES[slot.limit] if slot.limit else "Live research is paused."
        yield FallbackEvent(reason="limit", message=message)
        return

    # From here the first run is reserved, so the search's thread starts before anything else is
    # sent: whatever happens to the stream, that thread settles every run it starts.
    search = _Search(id=slot.id, topic=topic, visitor=request.visitor, live=live)
    events: queue.Queue[ResearchEvent | None] = queue.Queue()
    worker = threading.Thread(
        target=_run_search,
        args=(search, services, clock),
        kwargs={"emit": events.put},
        name=f"live-search-{slot.id}",
    )
    try:
        worker.start()
    except RuntimeError as error:  # no thread could be started: nothing was spent
        print(f"live search {slot.id}: could not start: {error}", file=sys.stderr)
        _settle(services, slot.id, 0.0, "failed", None)
        yield _unavailable()
        return
    try:
        while (event := events.get()) is not None:
            yield event
    finally:
        # If the player left, the server is closing this stream early. Waiting here keeps the
        # request, and so a serverless instance, alive until the paid runs are stored and settled.
        worker.join(timeout=max(1.0, SEARCH_SECONDS - clock.elapsed()))


def _unavailable() -> FallbackEvent:
    return FallbackEvent(
        reason="unavailable",
        message=(
            "Live research is not available right now. Topics in the bank are still free to play."
        ),
    )


def _settle(
    services: Services,
    slot_id: int,
    spent: float,
    outcome: OnDemandOutcome,
    run_id: int | None,
) -> None:
    try:
        services.store.finish_on_demand_run(slot_id, spent, outcome, run_id)
    except StoreError as error:
        print(f"live run {slot_id}: could not settle its cost: {error}", file=sys.stderr)


def _run_search(
    search: _Search,
    services: Services,
    clock: _Clock,
    emit: Callable[[ResearchEvent | None], None],
) -> None:
    """The paid part of a search, on its own thread: its live items one at a time, the first on
    the slot the search opened with and each later one on a slot of its own. Every run it starts
    is settled, and the stream always ends (`emit(None)`), whatever happens."""
    try:
        for index, planned in enumerate(search.live):
            if index == 0:
                slot_id = search.id
            else:
                started = _later_slot(search, planned, services, clock)
                if isinstance(started, _NotStarted):
                    for left in search.live[index:]:
                        emit(
                            MissedEvent(
                                key=left.key,
                                reason="skipped",
                                message=f"Not started. {started.reason}",
                            )
                        )
                    return
                slot_id = started
            _run_item(search, planned, slot_id, services, clock.for_item(planned.key), emit)
    except Exception:  # each run settles itself; this only guards the loop
        traceback.print_exc(file=sys.stderr)
    finally:
        emit(None)


@dataclass(frozen=True)
class _NotStarted:
    """Why a later run of a search was not started, as a sentence for the player."""

    reason: str


def _later_slot(
    search: _Search, planned: PlannedItem, services: Services, clock: _Clock
) -> int | _NotStarted:
    """Reserve a later run of the search, or say why it cannot start. The database counts it
    against the dollar caps but not against the search limits (migration 006)."""
    if clock.elapsed() > RUN_START_SECONDS:
        return _NotStarted("The search ran out of time.")
    try:
        slot = services.store.begin_on_demand_run(
            search.visitor,
            search.topic,
            planned.mode,
            planned.difficulty,
            services.settings.max_job_cost_usd,
            services.limits,
            search_id=search.id,
        )
    except StoreError as error:
        print(f"live search {search.id}: could not reserve a run: {error}", file=sys.stderr)
        return _NotStarted("Live research is not available right now.")
    if not slot.ok or slot.id is None:
        return _NotStarted(LIMIT_MESSAGES[slot.limit] if slot.limit else "Live research is paused.")
    return slot.id


def _run_item(
    search: _Search,
    planned: PlannedItem,
    slot_id: int,
    services: Services,
    clock: _Clock,
    emit: Callable[[ResearchEvent | None], None],
) -> None:
    """One live run: research, the gate and storage, then the item or why there is none. Always
    settles the run's slot."""
    spent = services.settings.max_job_cost_usd  # assumed until the real cost is known
    outcome: OnDemandOutcome = "failed"
    run_id: int | None = None
    try:
        emit(clock.log("Budget", f"up to ${spent:.2f} reserved for {planned.label}", "ok"))
        record = _produce(search.topic, planned, services, clock, emit)
        spent = record.anthropic_cost_usd
        status = record.status
        outcome = status if status in ("published", "review", "discarded") else "failed"
        _emit_stats(planned, record, emit)

        # A topic the bank already has keeps its own kind (record_item matches it by name).
        topic = TopicRef(name=search.topic, kind="custom")
        ids = services.store.record_item(build_payload(record, topic, "on_demand"))
        run_id = ids.run_id
        emit(clock.log("Saved to the bank", _saved_detail(outcome), "ok"))

        item = services.results.item(ids.item_id) if ids.item_id is not None else None
        if outcome in ("published", "review") and item is not None:
            token = (
                services.sign(REVEAL_PURPOSE, str(item.id))
                if isinstance(item, QuizQuestion)
                else None
            )
            emit(ResultEvent(key=planned.key, item=item, reveal_token=token))
        else:
            emit(
                MissedEvent(
                    key=planned.key,
                    reason="discarded",
                    message=(
                        f"The agent could not back {planned.label} with its sources, so it "
                        "is left out."
                    ),
                )
            )
    except Exception:
        traceback.print_exc(file=sys.stderr)
        emit(
            MissedEvent(
                key=planned.key,
                reason="failed",
                message=f"Something went wrong with {planned.label} on our side.",
            )
        )
    finally:
        _settle(services, slot_id, spent, outcome, run_id)


def _emit_stats(
    planned: PlannedItem, record: ItemRecord, emit: Callable[[ResearchEvent | None], None]
) -> None:
    """Send what the run measured. Sent before the run is stored, so a run whose save fails
    still shows its cost; a failure here only loses the figures, never the paid run."""
    try:
        emit(StatsEvent(key=planned.key, stats=run_stats(record)))
    except Exception:
        traceback.print_exc(file=sys.stderr)


def _saved_detail(outcome: OnDemandOutcome) -> str:
    return {
        "published": "published for everyone",
        "review": "kept for review; shown only to you",
        "discarded": "kept in the run log only",
        "failed": "kept in the run log only",
    }[outcome]


def _produce(
    topic: str,
    planned: PlannedItem,
    services: Services,
    clock: _Clock,
    emit: Callable[[ResearchEvent | None], None],
) -> ItemRecord:
    """The agent run and the publish gate, with every step sent to the log."""
    settings = services.settings
    budget = run_budget(settings, clock.elapsed())
    run_settings = settings
    if budget < settings.max_seconds:
        run_settings = settings.model_copy(update={"max_seconds": budget})
        emit(clock.log("Time", f"{budget:.0f} s for the agent, so the search ends in time"))
    answer_word = NOUNS[planned.mode]

    def on_step(step: Step) -> None:
        emit(step_event(step, clock, answer_word))

    # The first model call usually takes about 2 seconds but now and then 20, so say it started.
    emit(clock.log("Agent", f"researching with {settings.model}"))

    run = run_learn if planned.mode == "learn" else run_quiz
    result = run(topic, planned.difficulty, services.llm, run_settings, on_step=on_step)

    if result.code_check is not None:
        problems = result.code_check.problems
        emit(
            clock.log(
                "Code checks",
                "URLs, quotes and numbers match the pages read"
                if result.code_check.passed
                else "; ".join(problems)[:160],
                "ok" if result.code_check.passed else "warn",
            )
        )
    elif result.answer is None:
        emit(clock.log("Agent", f"no answer: {result.detail}"[:160], "warn"))

    record = verify_and_decide(result, services.llm, services.jev, settings)
    verification = record.verification
    if verification is not None:
        haiku = verification.haiku
        if haiku is not None:
            # A reason can name the answer ("the passage supports Jupiter"), so a quiz shows only
            # the verdict here; its reasons come with the answer, as the doubts.
            if planned.mode == "quiz" or not haiku.reasons:
                detail = str(haiku.verdict)
            else:
                detail = f"{haiku.verdict}: {haiku.reasons[0]}"
            emit(
                clock.log(
                    "Haiku verifier", detail[:160], "ok" if haiku.verdict == "pass" else "warn"
                )
            )
        jev = verification.jev
        if jev is not None:
            options = sum(1 for c in jev.checks if c.kind in ("correct_answer", "distractor"))
            option_number = sentence_number = 0
            for check in jev.checks:
                if check.kind in ("correct_answer", "distractor"):
                    # Which option the sources support would give the answer away, so quiz
                    # options show only how sure Jev was. The full check comes with the answer.
                    option_number += 1
                    emit(
                        clock.log(
                            f"Jev  option check {option_number} of {options}",
                            f"confidence {check.confidence:.2f}",
                            confidence=check.confidence,
                        )
                    )
                elif check.kind == "sentence":
                    sentence_number += 1
                    emit(
                        clock.log(
                            f"Jev  sentence {sentence_number}",
                            f"{VERDICT_WORDS[check.verdict]} {check.confidence:.2f}",
                            "ok" if check.verdict == "supports" else "warn",
                            verdict=check.verdict,
                            confidence=check.confidence,
                        )
                    )
    emit(
        clock.log(
            "Publish gate",
            {"published": "passed", "review": "held for review", "discarded": "failed"}.get(
                record.status or "", "no answer to check"
            ),
            "ok" if record.status == "published" else "warn",
        )
    )
    return record


VERDICT_WORDS: dict[JevVerdict, str] = {
    "supports": "supported",
    "contradicts": "contradicted",
    "says_nothing": "not addressed",
}


def step_event(step: Step, clock: _Clock, answer_word: str) -> LogEvent:
    """A line of the agent log for one step of a run."""
    if step.kind == "tool" and step.tool:
        detail = tool_detail(step.arguments or {})
        if step.is_error:
            return clock.log(step.tool, f"{detail} (failed)".strip(), "warn")
        return clock.log(step.tool, detail)
    called = step.summary.split(" (stop:", 1)[0]
    if called.startswith("submit_"):
        return clock.log("Agent", f"writes the {answer_word}")
    if called == "no tool calls":
        return clock.log("Agent", "thinking")
    return clock.log("Agent", f"next: {called}")


def tool_detail(arguments: dict[str, object]) -> str:
    """The part of a tool call worth showing: the URL without its scheme, or the query."""
    url = arguments.get("url")
    if isinstance(url, str):
        parts = urlsplit(url)
        return f"{parts.netloc}{parts.path}"[:90]
    for value in arguments.values():
        if isinstance(value, str) and value:
            return f'"{value}"'[:90]
    return ""
