"""Live searches on the web page: the guardrails, the runs, and the events streamed to the player.

A search makes a whole topic at every level (changed 2026-10-28 by Vedant; it was the
explanation at one chosen level): a QUIZ question at each level, then the LEARN explanation at
each level, easiest first, leaving out any the bank already has. The questions come first and
the explanations last (changed 2026-10-10 by Vedant), so the first question is ready sooner and
the explanations, which can give answers away, are read after them. What a search's caps leave
out, the daily Curator fills (`python -m curator daily`), and Learn and Quiz list the topic once
it has every level. `research` yields events while it works:

0. Surprise me (no topic sent): the visitor's limits and the global caps are read first, so a
   search they would refuse ends before the paid pick; then the agent picks a topic the bank
   does not have (`agent/topic_pick.py`) and the search goes on with it. A failed pick counts
   nothing.
1. The plan: which items the search makes live and which the bank already has (free), with how
   long each live item's run usually takes (`RunTimes`). When the bank has them all, that is the
   whole search: free, and not counted.
2. The on-topic check (`agent/topic_check.py`) rejects anything that is not a plain astronomy
   or space topic. It runs once per search, and only after the visitor's limits and the global
   caps are read: it is paid, so a search they would refuse ends before it. A topic the agent
   picked skips it.
3. Every run is reserved in one call (migration 010), which opens the search and counts it
   against the visitor's daily limit and everyone's (`agent/limits.py`). The runs are reserved
   in plan order while the dollar caps fit, so a cap leaves out the last items, which are
   reported as not started. Over a limit, the player keeps what the bank has.
4. The EASY question goes first, alone, when it is a live item; the other reserved runs start
   together when it ends (changed 2026-11-02 by Vedant; from 2026-10-30 every run started at once,
   and before that they went one at a time). With the EASY question in the bank, every live run
   starts together. If the EASY question failed with nothing spent, the model is out of reach, so
   the others never start: each is settled as failed with nothing spent and reported as missed.
   A run is the Curator's evaluated pipeline: the agent researches the item and the same
   three-layer gate decides (`agent/publish.py`). Every step is streamed as a log line, including
   each Jev claim check, tagged with its item, so the lines of runs at once interleave.
5. Each run is stored in the bank whatever the outcome, its real cost settles its reservation,
   and a published or review item is sent to the player. A quiz item comes without its answer
   and with a signed token that lets /api/reveal answer it once the player has picked.
6. Each run that produced a record also sends what it measured (`agent/run_stats.py`), for the
   analytics panel: numbers only, so nothing in it can give a quiz answer away.
7. When every reserved run has ended, a last event (`EndEvent`) says whether the model was out of
   reach: every run failed with nothing spent, as a refused key or an outage leaves it. Such a
   search does not count against the daily limits (migration 013).

Every event after the plan that concerns one item names it (`key`, such as "quiz-easy"). Beside
the log lines, each live run sends its progress (`ProgressEvent`): the stage of its work and a
status line that names it, for the page's progress rows.

From step 4 the work runs on a thread of its own, started before anything more is streamed,
which runs each reserved item on a thread named by the search and the item (so a rate-limit log
line in api/research.py says which item met it). A reserved run is paid for, so it is always
finished, stored and settled. If the player leaves, closing the stream waits for the search's
thread, which waits for every run, keeping the request (and a serverless instance) alive until
the search is stored.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

from agent.bank import DIFFICULTY_ORDER, BankTopic, LearnItem, QuizQuestion
from agent.config import Settings
from agent.limits import LimitSettings, OnDemandUsage, SearchSlots, limit_message, search_limit
from agent.llm import LLMProvider
from agent.loop import run_learn, run_quiz
from agent.publish import verify_and_decide
from agent.rest import StoreError
from agent.run_stats import RunStats, run_stats
from agent.schemas import Difficulty, ItemRecord, JevVerdict, Mode, Step
from agent.store import (
    ItemPayload,
    OnDemandOutcome,
    RecordedIds,
    RunEstimate,
    TopicKind,
    TopicRef,
    build_payload,
)
from agent.tools.feeds import FEEDS
from agent.topic_check import TopicCheckError, TopicJudge
from agent.topic_pick import TopicPick
from agent.verifiers import JevClient

REVEAL_PURPOSE = "reveal"

# Vercel ends a function at 300 seconds, so a search must be stored and settled by this time. A
# search has two batches at most, the EASY question and then the rest, and each run has the agent's
# 120 s budget, so they end inside it; this is how long a player leaving waits for them.
SEARCH_SECONDS = 280.0

# How long a live item's run usually takes, for the page's progress rows (migration 010): read at
# most once an hour per server. A level with fewer runs than this in the last 30 days, or a failed
# read, uses the Session 3 eval's median item time (agent loop and verifier).
ESTIMATE_TTL_SECONDS = 3600.0
# After a failed read, the next try waits this long, so a database that is down is not asked again
# by every search (the read holds the lock other searches wait on).
ESTIMATE_RETRY_SECONDS = 60.0
ESTIMATE_MIN_RUNS = 5
ESTIMATE_FALLBACK_SECONDS = 17.0

# How a reserved run ended: what it spent and its outcome.
_EndedRun = tuple[float, OnDemandOutcome]
# What a run that failed with nothing spent says: it never reached the model, as with a refused key
# or an outage, so its sources were not the problem.
MODEL_UNREACHED_MESSAGE = "The agent could not reach the model."

# --- Events ------------------------------------------------------------------------------------

Tone = Literal["info", "ok", "warn"]
FallbackReason = Literal["limit", "unavailable"]
MissedReason = Literal["discarded", "failed", "skipped"]
ItemSource = Literal["live", "bank"]
# The stages of a live run's work, in order, for the page's progress rows.
Stage = Literal["search", "read", "write", "verify"]

NOUNS: dict[Mode, str] = {"learn": "explanation", "quiz": "question"}


def item_key(mode: Mode, difficulty: Difficulty) -> str:
    """How events name an item of a search: "learn-medium", "quiz-easy" and so on."""
    return f"{mode}-{difficulty}"


# The run that goes first and alone when it is live. The plan puts it first (`plan_search`).
FIRST_RUN_KEY = item_key("quiz", "easy")


class PlannedItem(BaseModel):
    """One item a search shows: made live, or already in the bank (free)."""

    model_config = ConfigDict(frozen=True)

    key: str
    mode: Mode
    difficulty: Difficulty
    source: ItemSource
    # How long its run usually takes, in seconds, for the progress rows; None for a bank item.
    estimate_seconds: float | None = None

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


class ProgressEvent(BaseModel):
    """Where a live item's run stands, for the page's progress rows: the stage of its work and a
    status line that names the real work ("Reading nasa.gov"). Sent as each step ends, so it
    says what the run does next: after a page is fetched, the model's next call reads it. The
    call that writes the answer cannot be told from one that reads until it returns, so "write"
    comes when the answer arrives and its quotes and numbers are checked, and "verify" follows
    at once. The run's end is its `result` or `missed` event."""

    model_config = ConfigDict(frozen=True)

    type: Literal["progress"] = "progress"
    key: str
    stage: Stage
    status: str
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


class EndEvent(BaseModel):
    """The last event of a search that reserved runs, sent once every one has ended."""

    model_config = ConfigDict(frozen=True)

    type: Literal["end"] = "end"
    # Every reserved run failed with nothing spent: the model was out of reach, not the topic.
    unavailable: bool


ResearchEvent = (
    PlanEvent
    | LogEvent
    | ProgressEvent
    | RejectedEvent
    | FallbackEvent
    | ResultEvent
    | MissedEvent
    | StatsEvent
    | EndEvent
)


# --- What a search needs -----------------------------------------------------------------------


class LiveStore(Protocol):
    def on_demand_usage(self, user_hash: str, now: datetime) -> OnDemandUsage: ...

    def begin_on_demand_search(
        self,
        user_hash: str,
        topic: str,
        items: Sequence[tuple[Mode, Difficulty]],
        reserve_usd: float,
        limits: LimitSettings,
    ) -> SearchSlots: ...

    def finish_on_demand_run(
        self, slot_id: int, spent_usd: float, outcome: OnDemandOutcome, run_id: int | None
    ) -> None: ...

    def record_item(self, payload: ItemPayload) -> RecordedIds: ...


class RunTimes:
    """How long each mode and level's run usually takes (`live_run_estimates`, migration 010),
    read at most once every ESTIMATE_TTL_SECONDS. Shared by every request a process serves, so
    it is thread-safe. A failed read keeps what it had and is tried again after
    ESTIMATE_RETRY_SECONDS; a progress estimate never stops a search."""

    def __init__(
        self,
        read: Callable[[], Sequence[RunEstimate]],
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._read = read
        self._now = now
        self._lock = threading.Lock()
        self._seconds: dict[tuple[Mode, Difficulty], float] = {}
        self._next_read: float | None = None  # None: never read yet

    def seconds(self, mode: Mode, difficulty: Difficulty) -> float:
        with self._lock:
            now = self._now()
            if self._next_read is None or now >= self._next_read:
                self._refresh(now)
            return self._seconds.get((mode, difficulty), ESTIMATE_FALLBACK_SECONDS)

    def _refresh(self, now: float) -> None:
        try:
            rows = self._read()
        except StoreError as error:
            print(f"live run estimates not read: {error}", file=sys.stderr)
            self._next_read = now + ESTIMATE_RETRY_SECONDS
            return
        self._seconds = {
            (row.mode, row.difficulty): row.median_seconds
            for row in rows
            if row.runs >= ESTIMATE_MIN_RUNS
        }
        self._next_read = now + ESTIMATE_TTL_SECONDS


class PublicBank(Protocol):
    def topic_named(self, name: str) -> str | None: ...

    def coverage(self, topic: str) -> BankTopic | None: ...

    def topic_names(self) -> list[tuple[str, TopicKind]]: ...


class TopicPicker(Protocol):
    def pick(self, existing: Sequence[tuple[str, TopicKind]]) -> TopicPick: ...


class StoredItems(Protocol):
    def item(self, item_id: int) -> QuizQuestion | LearnItem | None: ...


@dataclass(frozen=True)
class Services:
    """Everything `research` talks to, passed in so tests can replace each one. The clients are
    shared by every request a process serves (api/research.py), so nothing here closes them."""

    judge: TopicJudge
    picker: TopicPicker  # Surprise me (agent/topic_pick.py)
    bank: PublicBank  # the public bank (publishable key)
    results: StoredItems  # reads back a stored live item, review included (secret key)
    store: LiveStore
    llm: LLMProvider
    jev: JevClient | None
    settings: Settings
    run_times: RunTimes  # for the progress rows' estimates
    # The limits in force at a moment (agent/limits.limits_at), read when a search starts; every
    # run of that search keeps them.
    limits: Callable[[datetime], LimitSettings]
    sign: Callable[[str, str], str]  # (purpose, value) -> token, see agent/web.py


@dataclass(frozen=True)
class SearchRequest:
    topic: str | None  # cleaned (agent/topic_check.clean_topic); None: the agent picks one
    visitor: str  # salted hash of the IP address


@dataclass(frozen=True)
class _Search:
    id: int  # the id of the run that opened it (migrations 006 and 010)
    topic: str  # in the bank's spelling when the bank has it
    visitor: str
    # Each reserved item with the id of its run's reservation, in plan order.
    runs: tuple[tuple[PlannedItem, int], ...]
    # The live items the caps left out, and why, as a sentence for the player.
    left_out: tuple[PlannedItem, ...]
    left_out_reason: str


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

    def progress(self, stage: Stage, status: str) -> ProgressEvent:
        if self.key is None:
            raise ValueError("progress is about an item: use for_item")
        return ProgressEvent(
            key=self.key, stage=stage, status=status, seconds=round(self.elapsed(), 1)
        )


def plan_search(have: BankTopic | None) -> list[PlannedItem]:
    """What a search makes, in order: a question at each level, then an explanation at each
    level, easiest first. Live items are reserved in this order, so when a cap cuts a search
    short, the harder explanations are what is left out (the daily Curator makes them). An item
    the bank already has is served from it, free."""
    wanted: list[tuple[Mode, Difficulty]] = [
        (mode, level) for mode in ("quiz", "learn") for level in DIFFICULTY_ORDER
    ]

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


def with_estimates(plan: Sequence[PlannedItem], run_times: RunTimes) -> list[PlannedItem]:
    """The plan with each live item's usual run time, for the progress rows."""
    return [
        item.model_copy(update={"estimate_seconds": run_times.seconds(item.mode, item.difficulty)})
        if item.source == "live"
        else item
        for item in plan
    ]


def research(request: SearchRequest, services: Services) -> Generator[ResearchEvent]:
    """Run one live search, yielding events as it goes (see the module docstring)."""
    clock = _Clock()

    picked = request.topic is None
    if request.topic is None:
        chosen = yield from _surprise(request.visitor, services, clock)
        if chosen is None:
            return
        requested = chosen
    else:
        requested = request.topic

    try:
        known = services.bank.topic_named(requested)
        have = services.bank.coverage(known) if known is not None else None
    except StoreError as error:
        print(f"live search: bank lookup failed: {error}", file=sys.stderr)
        yield _unavailable()
        return
    topic = known or requested
    plan = with_estimates(plan_search(have), services.run_times)
    yield PlanEvent(topic=topic, items=plan)
    live = tuple(item for item in plan if item.source == "live")
    if not live:
        return  # the bank has the whole topic: free, and not counted

    # The on-topic check is paid, so a search the limits would refuse ends before it
    # (docs/SECURITY_AUDIT.md S3). The database still decides when the first run starts.
    now = datetime.now(UTC)
    limits = services.limits(now)
    try:
        usage = services.store.on_demand_usage(request.visitor, now)
    except StoreError as error:
        print(f"live search: could not read the limits: {error}", file=sys.stderr)
        yield _unavailable()
        return
    refused = search_limit(usage, limits, services.settings.max_job_cost_usd)
    if refused is not None:
        yield FallbackEvent(reason="limit", message=limit_message(refused, limits))
        return

    if not picked:  # the agent's own pick is an astronomy topic by construction
        try:
            verdict = services.judge.judge(topic)
        except TopicCheckError as error:
            print(f"live search: topic check failed: {error}", file=sys.stderr)
            yield _unavailable()
            return
        # Every paid call is logged with its tokens and cost (CLAUDE.md rule 1); a rejected
        # topic leaves no other record.
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

    try:
        slots = services.store.begin_on_demand_search(
            request.visitor,
            topic,
            [(item.mode, item.difficulty) for item in live],
            services.settings.max_job_cost_usd,
            limits,
        )
    except StoreError as error:
        print(f"live search: could not reserve its runs: {error}", file=sys.stderr)
        yield _unavailable()
        return
    if not slots.ok or not slots.ids:
        yield FallbackEvent(reason="limit", message=_refusal(slots, limits))
        return
    reserved = tuple(zip(live, slots.ids, strict=False))
    for extra in slots.ids[len(live) :]:  # never sent by the database; settled all the same
        _settle(services, extra, 0.0, "failed", None)

    # From here runs are reserved, so the search's thread starts before anything else is sent:
    # whatever happens to the stream, that thread settles every run it reserved.
    search = _Search(
        id=slots.ids[0],
        topic=topic,
        visitor=request.visitor,
        runs=reserved,
        left_out=live[len(reserved) :],
        left_out_reason=_refusal(slots, limits),
    )
    events: queue.Queue[ResearchEvent | None] = queue.Queue()
    worker = threading.Thread(
        target=_run_search,
        args=(search, services, clock),
        kwargs={"emit": events.put},
        name=f"live-search-{search.id}",
    )
    try:
        worker.start()
    except RuntimeError as error:  # no thread could be started: nothing was spent
        print(f"live search {search.id}: could not start: {error}", file=sys.stderr)
        for _, slot_id in search.runs:
            _settle(services, slot_id, 0.0, "failed", None)
        yield _unavailable()
        return
    try:
        while (event := events.get()) is not None:
            yield event
    finally:
        # If the player left, the server is closing this stream early. Waiting here keeps the
        # request, and so a serverless instance, alive until the paid runs are stored and settled.
        worker.join(timeout=max(1.0, SEARCH_SECONDS - clock.elapsed()))


def _surprise(
    visitor: str, services: Services, clock: _Clock
) -> Generator[ResearchEvent, None, str | None]:
    """Surprise me: the topic the agent picks, or None once the reason has been sent. The limits
    are read first, so a search they would refuse ends before the paid pick; a failed pick
    reserves nothing, so it is not counted.

    The order is: the limits read, then the paid pick, then `begin_on_demand_search`, which
    decides. So two visitors at the last place under a cap can both pay for a pick, and then one
    is refused: about $0.003 for the refused pick. Accepted on 2026-10-30 (docs/SESSIONS.md),
    since reserving before the pick would count a search that may pick nothing."""
    now = datetime.now(UTC)
    limits = services.limits(now)
    try:
        usage = services.store.on_demand_usage(visitor, now)
        existing = services.bank.topic_names()
    except StoreError as error:
        print(f"live search: could not prepare a topic pick: {error}", file=sys.stderr)
        yield _unavailable()
        return None
    refused = search_limit(usage, limits, services.settings.max_job_cost_usd)
    if refused is not None:
        yield FallbackEvent(reason="limit", message=limit_message(refused, limits))
        return None

    pick = services.picker.pick(existing)
    # Every paid call is logged with its tokens and cost (CLAUDE.md rule 1).
    print(
        f"topic pick: topic={pick.topic!r} tokens={pick.usage.total_input_tokens}+"
        f"{pick.usage.output_tokens} cost=${pick.cost_usd:.6f} notes={pick.notes}",
        file=sys.stderr,
    )
    if pick.topic is None:
        yield FallbackEvent(
            reason="unavailable",
            message=(
                "The agent could not pick a topic just now, and nothing was counted. Try again, "
                "or type a topic."
            ),
        )
        return None
    yield clock.log("Agent picked a topic", pick.topic, "ok")
    return pick.topic


def _refusal(slots: SearchSlots, limits: LimitSettings) -> str:
    """Why runs were not reserved, as a sentence for the player."""
    return limit_message(slots.limit, limits) if slots.limit else "Live research is paused."


def _unavailable() -> FallbackEvent:
    return FallbackEvent(
        reason="unavailable",
        message=(
            "Live research is not available right now. Topics in the bank are still free to play."
        ),
    )


def _failed_unspent(spent: float, outcome: OnDemandOutcome) -> bool:
    """Whether a run failed with nothing spent. The cost is rounded as `finish_on_demand_run`
    stores it."""
    return outcome == "failed" and round(spent, 6) == 0


def _model_unreachable(search: _Search, ended: Sequence[_EndedRun]) -> bool:
    """Whether every reserved run failed with nothing spent: the same rule as
    `on_demand_search_counts` (migration 013), so such a search is the one not counted."""
    return len(ended) == len(search.runs) and all(
        _failed_unspent(spent, outcome) for spent, outcome in ended
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
    """The paid part of a search, on its own thread, so waiting here never holds up the stream.
    The EASY question goes first and alone when it is live; when it ends, the other reserved runs
    start together, unless it failed with nothing spent, when they are settled unstarted. Each run
    has a thread named by the search and the item. The items the caps left out are reported once
    the first run has started. It waits for every run it started and settles any it did not, so
    the stream always ends (`emit(None)`), whatever happens."""
    runs: list[threading.Thread] = []
    ended: list[_EndedRun] = []  # appended from each run's thread
    waiting = deque(search.runs)

    def start_next() -> threading.Thread | None:
        planned, slot_id = waiting[0]
        run = _start_run(search, planned, slot_id, services, clock, emit, ended)
        waiting.popleft()
        if run is not None:
            runs.append(run)
        return run

    def give_up_on_waiting(message: Callable[[PlannedItem], str]) -> None:
        while waiting:
            planned, slot_id = waiting.popleft()
            _give_up(planned, slot_id, message(planned), services, emit, ended)

    try:
        first = start_next() if waiting[0][0].key == FIRST_RUN_KEY else None
        for left in search.left_out:
            emit(
                MissedEvent(
                    key=left.key,
                    reason="skipped",
                    message=f"Not started. {search.left_out_reason}",
                )
            )
        if first is not None:
            first.join()
            if ended and _failed_unspent(*ended[0]):
                give_up_on_waiting(lambda _: MODEL_UNREACHED_MESSAGE)
        while waiting:
            start_next()
    except Exception:  # each run settles itself; this only guards the starts
        traceback.print_exc(file=sys.stderr)
    finally:
        try:
            for run in runs:
                run.join()
            give_up_on_waiting(_on_our_side)
        finally:
            emit(EndEvent(unavailable=_model_unreachable(search, ended)))
            emit(None)


def _start_run(
    search: _Search,
    planned: PlannedItem,
    slot_id: int,
    services: Services,
    clock: _Clock,
    emit: Callable[[ResearchEvent | None], None],
    ended: list[_EndedRun],
) -> threading.Thread | None:
    """Start one reserved run on its own thread. A thread that cannot start costs that run only:
    nothing was spent on it, and the search goes on without it."""
    run = threading.Thread(
        target=_run_item,
        args=(search, planned, slot_id, services, clock.for_item(planned.key), emit, ended),
        name=f"live-search-{search.id}-{planned.key}",
    )
    try:
        run.start()
    except RuntimeError as error:
        print(f"live search {search.id}: {planned.key} not started: {error}", file=sys.stderr)
        _give_up(planned, slot_id, _on_our_side(planned), services, emit, ended)
        return None
    return run


def _give_up(
    planned: PlannedItem,
    slot_id: int,
    message: str,
    services: Services,
    emit: Callable[[ResearchEvent | None], None],
    ended: list[_EndedRun],
) -> None:
    """End a reserved run that never started: nothing was spent on it."""
    _settle(services, slot_id, 0.0, "failed", None)
    ended.append((0.0, "failed"))
    emit(MissedEvent(key=planned.key, reason="failed", message=message))


def _on_our_side(planned: PlannedItem) -> str:
    return f"Something went wrong with {planned.label} on our side."


def _run_item(
    search: _Search,
    planned: PlannedItem,
    slot_id: int,
    services: Services,
    clock: _Clock,
    emit: Callable[[ResearchEvent | None], None],
    ended: list[_EndedRun],
) -> None:
    """One live run: research, the gate and storage, then the item or why there is none. Always
    settles the run's slot, and adds how it ended to `ended`."""
    spent = services.settings.max_job_cost_usd  # assumed until the real cost is known
    outcome: OnDemandOutcome = "failed"
    run_id: int | None = None
    try:
        emit(clock.log("Budget", f"up to ${spent:.2f} reserved for {planned.label}", "ok"))
        emit(clock.progress("search", "Choosing where to look"))
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
        elif _failed_unspent(spent, outcome):
            emit(MissedEvent(key=planned.key, reason="failed", message=MODEL_UNREACHED_MESSAGE))
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
                message=_on_our_side(planned),
            )
        )
    finally:
        _settle(services, slot_id, spent, outcome, run_id)
        ended.append((spent, outcome))


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
    answer_word = NOUNS[planned.mode]

    def on_step(step: Step) -> None:
        emit(step_event(step, clock, answer_word))
        progress = step_progress(step, clock, answer_word)
        if progress is not None:
            emit(progress)

    # The first model call usually takes about 2 seconds but now and then 20, so say it started.
    emit(clock.log("Agent", f"researching with {settings.model}"))

    run = run_learn if planned.mode == "learn" else run_quiz
    result = run(topic, planned.difficulty, services.llm, settings, on_step=on_step)

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

    if result.answer is not None:
        pages = len(result.cited_pages)
        emit(
            clock.progress(
                "verify",
                f"Checking the {answer_word} against {pages} page{'' if pages == 1 else 's'}",
            )
        )
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


# What the model does with each research tool's result, for the progress status line.
_SEARCHES: dict[str, str] = {
    "search_wikipedia": "Wikipedia",
    "search_arxiv": "arXiv",
    "search_nasa_images": "NASA images",
}


def step_progress(step: Step, clock: _Clock, answer_word: str) -> ProgressEvent | None:
    """The run's progress after one of its steps, or None when the step changes nothing a
    player would see (a model call that asks for tools, or a tool that failed)."""
    if step.kind == "tool" and step.tool and not step.is_error:
        arguments = step.arguments or {}
        if step.tool in _SEARCHES:
            query = arguments.get("query")
            about = f' for "{query[:60]}"' if isinstance(query, str) and query else ""
            where = _SEARCHES[step.tool]
            return clock.progress("search", f"Looking through {where} results{about}")
        if step.tool == "fetch_page":
            url = arguments.get("url")
            host = urlsplit(url).netloc.removeprefix("www.") if isinstance(url, str) else ""
            return clock.progress("read", f"Reading {host}" if host else "Reading a page")
        if step.tool == "fetch_feed":
            feed = arguments.get("feed")
            label = FEEDS[feed][0] if isinstance(feed, str) and feed in FEEDS else "a news feed"
            return clock.progress("read", f"Reading {label}")
        if step.tool == "nasa_apod":
            return clock.progress("read", "Reading NASA's Astronomy Picture of the Day")
        return clock.progress("read", "Reading its sources")
    if step.kind == "model" and step.summary.startswith("submit_"):
        return clock.progress(
            "write", f"Checking the {answer_word}'s quotes and numbers against its pages"
        )
    return None


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
