"""Custom topics researched live: the guardrails, the run, and the events streamed to the player.

`research` yields events while it works:

1. If the bank can already serve the topic at this mode and difficulty, it says so (free).
2. The on-topic check (`agent/topic_check.py`) rejects anything that is not a plain astronomy
   or space topic.
3. The visitor's daily limit and the global caps are checked and a slot is reserved
   (`agent/limits.py`, migration 004). Over a limit, the player is sent back to the bank.
4. The agent researches the topic and the same three-layer gate as the Curator decides
   (`agent/publish.py`). Every step is streamed as a log line, including each Jev claim check.
5. The run is stored in the bank whatever the outcome, its real cost settles the reservation,
   and a published or review item is sent to the player. A quiz item comes without its answer
   and with a signed token that lets /api/reveal answer it once the player has picked.

From step 4 the work runs on its own thread, started before anything more is streamed: a run
that has started is paid for, so it is always finished, stored and settled. If the player leaves,
closing the stream waits for that thread, which keeps the request (and a serverless instance)
alive until the run is stored.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
import traceback
from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

from agent.bank import LearnItem, QuizQuestion
from agent.config import Settings
from agent.limits import LIMIT_MESSAGES, LimitSettings, RunSlot
from agent.llm import LLMProvider
from agent.loop import run_learn, run_quiz
from agent.publish import verify_and_decide
from agent.rest import StoreError
from agent.schemas import Difficulty, ItemRecord, JevVerdict, Mode, Step
from agent.store import ItemPayload, OnDemandOutcome, RecordedIds, TopicRef, build_payload
from agent.topic_check import TopicCheckError, TopicJudge
from agent.verifiers import JevClient

REVEAL_PURPOSE = "reveal"

# --- Events ------------------------------------------------------------------------------------

Tone = Literal["info", "ok", "warn"]
FallbackReason = Literal["in_bank", "limit", "unavailable", "discarded"]


class LogEvent(BaseModel):
    """One line of the agent log."""

    model_config = ConfigDict(frozen=True)

    type: Literal["log"] = "log"
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
    """No live result: the player is served from the bank instead. `topic` is set when the bank
    already has this topic at this mode and difficulty."""

    model_config = ConfigDict(frozen=True)

    type: Literal["fallback"] = "fallback"
    reason: FallbackReason
    message: str
    topic: str | None = None


class ResultEvent(BaseModel):
    """The live item, published or in review. `reveal_token` unlocks a quiz item's answer."""

    model_config = ConfigDict(frozen=True)

    type: Literal["result"] = "result"
    item: QuizQuestion | LearnItem
    reveal_token: str | None = None


ResearchEvent = LogEvent | RejectedEvent | FallbackEvent | ResultEvent


# --- What a live run needs ---------------------------------------------------------------------


class LiveStore(Protocol):
    def begin_on_demand_run(
        self,
        user_hash: str,
        topic: str,
        mode: Mode,
        difficulty: Difficulty,
        reserve_usd: float,
        limits: LimitSettings,
    ) -> RunSlot: ...

    def finish_on_demand_run(
        self, slot_id: int, spent_usd: float, outcome: OnDemandOutcome, run_id: int | None
    ) -> None: ...

    def record_item(self, payload: ItemPayload) -> RecordedIds: ...


class PublicBank(Protocol):
    def topic_named(self, name: str) -> str | None: ...

    def has_item(self, topic: str, mode: Mode, difficulty: Difficulty) -> bool: ...


class StoredItems(Protocol):
    def item(self, item_id: int) -> QuizQuestion | LearnItem | None: ...


@dataclass(frozen=True)
class Services:
    """Everything `research` talks to, passed in so tests can replace each one. The clients are
    shared by every request a process serves (api/research.py), so nothing here closes them."""

    judge: TopicJudge
    bank: PublicBank  # the public bank (publishable key)
    results: StoredItems  # reads back the stored live item, review included (secret key)
    store: LiveStore
    llm: LLMProvider
    jev: JevClient | None
    settings: Settings
    limits: LimitSettings
    sign: Callable[[str, str], str]  # (purpose, value) -> token, see agent/web.py


@dataclass(frozen=True)
class LiveJob:
    topic: str  # cleaned (agent/topic_check.clean_topic) and, if known, in the bank's spelling
    mode: Mode
    difficulty: Difficulty
    visitor: str  # salted hash of the IP address


class _Clock:
    def __init__(self) -> None:
        self.started = time.monotonic()

    def log(self, label: str, detail: str = "", tone: Tone = "info", **extra: object) -> LogEvent:
        return LogEvent.model_validate(
            {
                "label": label,
                "detail": detail,
                "tone": tone,
                "seconds": round(time.monotonic() - self.started, 1),
                **extra,
            }
        )


# How long closing the stream waits for a started run to be stored: the agent's time budget, the
# verifiers and the save, under the 300-second limit of a Vercel function.
RUN_FINISH_SECONDS = 240.0


def research(job: LiveJob, services: Services) -> Generator[ResearchEvent]:
    """Run one custom topic live, yielding events as it goes (see the module docstring)."""
    clock = _Clock()

    try:
        known = services.bank.topic_named(job.topic)
        if known is not None and services.bank.has_item(known, job.mode, job.difficulty):
            yield FallbackEvent(
                reason="in_bank", message="This topic is already in the bank.", topic=known
            )
            return
    except StoreError as error:
        print(f"live run: bank lookup failed: {error}", file=sys.stderr)
        yield _unavailable()
        return
    topic = known or job.topic

    try:
        verdict = services.judge.judge(topic)
    except TopicCheckError as error:
        print(f"live run: topic check failed: {error}", file=sys.stderr)
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

    reserve = services.settings.max_job_cost_usd
    try:
        slot = services.store.begin_on_demand_run(
            job.visitor, topic, job.mode, job.difficulty, reserve, services.limits
        )
    except StoreError as error:
        print(f"live run: could not reserve a slot: {error}", file=sys.stderr)
        yield _unavailable()
        return
    if not slot.ok or slot.id is None:
        message = LIMIT_MESSAGES[slot.limit] if slot.limit else "Custom topics are paused."
        yield FallbackEvent(reason="limit", message=message)
        return

    # From here the slot is reserved, so the run's thread starts before anything else is sent:
    # whatever happens to the stream, that thread settles the slot.
    events: queue.Queue[ResearchEvent | None] = queue.Queue()
    events.put(clock.log("Budget", f"up to ${reserve:.2f} reserved for this run", "ok"))
    worker = threading.Thread(
        target=_run_and_store,
        args=(LiveJob(topic, job.mode, job.difficulty, job.visitor), slot.id, services, clock),
        kwargs={"emit": events.put},
        name=f"live-run-{slot.id}",
    )
    try:
        worker.start()
    except RuntimeError as error:  # no thread could be started: nothing was spent
        print(f"live run {slot.id}: could not start: {error}", file=sys.stderr)
        _settle(services, slot.id, 0.0, "failed", None)
        yield _unavailable()
        return
    try:
        while (event := events.get()) is not None:
            yield event
    finally:
        # If the player left, the server is closing this stream early. Waiting here keeps the
        # request, and so a serverless instance, alive until the paid run is stored and settled.
        worker.join(timeout=RUN_FINISH_SECONDS)


def _unavailable() -> FallbackEvent:
    return FallbackEvent(
        reason="unavailable",
        message="Live research is not available right now. Here is a question from the bank.",
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


def _run_and_store(
    job: LiveJob,
    slot_id: int,
    services: Services,
    clock: _Clock,
    emit: Callable[[ResearchEvent | None], None],
) -> None:
    """The paid part of a live run, on its own thread. Always settles the slot and ends the
    stream (`emit(None)`), whatever happens."""
    spent = services.settings.max_job_cost_usd  # assumed until the real cost is known
    outcome: OnDemandOutcome = "failed"
    run_id: int | None = None
    try:
        record = _produce(job, services, clock, emit)
        spent = record.anthropic_cost_usd
        status = record.status
        outcome = status if status in ("published", "review", "discarded") else "failed"

        topic = TopicRef(name=job.topic, kind="custom")
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
            emit(ResultEvent(item=item, reveal_token=token))
        else:
            emit(
                FallbackEvent(
                    reason="discarded",
                    message=(
                        "The agent could not back an answer with its sources this time. "
                        "Here is a question from the bank instead."
                    ),
                )
            )
    except Exception:
        traceback.print_exc(file=sys.stderr)
        emit(_unavailable())
    finally:
        _settle(services, slot_id, spent, outcome, run_id)
        emit(None)


def _saved_detail(outcome: OnDemandOutcome) -> str:
    return {
        "published": "published for everyone",
        "review": "kept for review; shown only to you",
        "discarded": "kept in the run log only",
        "failed": "kept in the run log only",
    }[outcome]


def _produce(
    job: LiveJob, services: Services, clock: _Clock, emit: Callable[[ResearchEvent | None], None]
) -> ItemRecord:
    """The agent run and the publish gate, with every step sent to the log."""
    settings = services.settings
    answer_word = "question" if job.mode == "quiz" else "explanation"

    def on_step(step: Step) -> None:
        emit(step_event(step, clock, answer_word))

    # The first model call usually takes about 2 seconds but now and then 20, so say it started.
    emit(clock.log("Agent", f"researching with {settings.model}"))

    if job.mode == "learn":
        result = run_learn(job.topic, job.difficulty, services.llm, settings, on_step=on_step)
    else:
        result = run_quiz(job.topic, job.difficulty, services.llm, settings, on_step=on_step)

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
            if job.mode == "quiz" or not haiku.reasons:
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
    """A line of the agent log for one step of the run."""
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
