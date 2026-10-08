"""The question bank in Supabase: what is stored for each run, and how it gets there.

`build_payload` turns one `ItemRecord` into the rows `record_item()` writes (see
supabase/schema.sql): the run with its metrics, the cited page text, and, when the run produced an
answer, the item with its sources and every layer's result per claim. It is pure, so the stored
shape is tested without a database.

`SupabaseStore` talks to Supabase's REST API with the secret key, which bypasses row-level
security. It is for the Curator and server functions only and must never reach the browser.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, Self
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx2
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from agent.limits import (
    LimitSettings,
    OnDemandUsage,
    RequestCount,
    RunSlot,
    day_start,
    month_start,
)
from agent.rest import RETRIES, RestClient, parse
from agent.rest import StoreError as StoreError
from agent.schemas import (
    CodeCheck,
    Difficulty,
    ItemRecord,
    JevReport,
    LayerVerdict,
    Mode,
    Outcome,
    QuizItem,
    Status,
    Step,
    Verification,
)

# Custom topics are typed by players and researched on demand (migration 004).
TopicKind = Literal["evergreen", "news", "custom"]
RunSource = Literal["curator", "on_demand"]
OnDemandOutcome = Literal["published", "review", "discarded", "failed"]
CuratorTrigger = Literal["build", "daily"]
CheckLayer = Literal["code", "haiku", "jev"]
CheckKind = Literal["citation", "number", "correct_answer", "distractor", "sentence", "explanation"]


# --- What is stored -----------------------------------------------------------------------------


class TopicRef(BaseModel):
    """A topic as the Curator plans it. News topics carry the article they came from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    kind: TopicKind
    lead_url: str | None = None
    retire_after: datetime | None = None


class RunRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Made once per run and kept in the payload, so re-sending a payload after an unclear failure
    # can never store the run twice (record_item() returns the existing rows instead).
    client_id: UUID
    curator_run_id: int | None
    source: RunSource
    mode: Mode
    difficulty: Difficulty
    model: str
    outcome: Outcome
    detail: str
    budget_reason: str | None
    model_calls: int
    nudges: int
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    agent_cost_usd: float
    seconds: float
    tool_calls: dict[str, int]
    tool_errors: int
    pages_by_domain: dict[str, int]
    fetched_urls: list[str]
    steps: list[dict[str, Any]]
    verifier_input_tokens: int
    verifier_output_tokens: int
    verifier_cost_usd: float
    verifier_seconds: float
    jev_input_tokens: int
    jev_cost_usd: float
    jev_seconds: float
    record: dict[str, Any]


class PageRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    page_text: str


class SourceRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ordinal: int
    url: str
    quote: str


class ClaimCheckRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    layer: CheckLayer
    kind: CheckKind
    claim: str
    verdict: str
    source_url: str | None = None
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    reason: str | None = None
    model: str | None = None


class ItemRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Mode
    difficulty: Difficulty
    status: Status
    question: str | None
    options: list[str] | None
    correct_index: int | None
    explanation: str
    gate_rule: str | None
    code_passed: bool
    code_problems: list[str]
    haiku_verdict: LayerVerdict | None
    haiku_reasons: list[str]
    jev_verdict: LayerVerdict | None
    jev_reasons: list[str]
    jev_model: str | None
    jev_criteria: str | None
    jev_threshold: float | None
    sources: list[SourceRow]
    claim_checks: list[ClaimCheckRow]


class ItemPayload(BaseModel):
    """Everything `record_item()` writes for one run, in one transaction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    topic: TopicRef
    run: RunRow
    cited_pages: list[PageRow]
    item: ItemRow | None


class RecordedIds(BaseModel):
    model_config = ConfigDict(frozen=True)

    topic_id: int
    run_id: int
    item_id: int | None
    duplicate: bool = False  # the run was already stored (a re-sent payload)


class CuratorSummary(BaseModel):
    """Totals for one Curator invocation, written to its `curator_runs` row when it finishes."""

    model_config = ConfigDict(frozen=True)

    jobs_planned: int = 0
    jobs_skipped: int = 0
    jobs_run: int = 0
    published: int = 0
    review: int = 0
    discarded: int = 0
    no_item: int = 0
    retired: int = 0
    anthropic_cost_usd: float = 0.0
    typesafe_cost_usd: float = 0.0
    stopped_reason: str | None = None
    log: tuple[str, ...] = ()


# --- Building the payload -----------------------------------------------------------------------


def domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def tool_counts(steps: Iterable[Step]) -> tuple[dict[str, int], int]:
    """Tool calls by tool name, and how many of them returned an error."""
    tool_steps = [step for step in steps if step.kind == "tool" and step.tool]
    counts = Counter(step.tool for step in tool_steps if step.tool)
    return dict(counts), sum(1 for step in tool_steps if step.is_error)


def code_check_rows(code: CodeCheck) -> list[ClaimCheckRow]:
    rows: list[ClaimCheckRow] = []
    citations = code.citations
    for verdict, group in (("kept", citations.kept), ("misquoted", citations.misquoted)):
        rows += [
            ClaimCheckRow(
                layer="code", kind="citation", claim=c.quote, source_url=c.url, verdict=verdict
            )
            for c in group
        ]
    # Citation rule: a URL that was not read in the run is never stored where a player could see
    # it. The run record (server-only) keeps it for audits.
    rows += [
        ClaimCheckRow(
            layer="code",
            kind="citation",
            claim=c.quote,
            verdict="unfetched",
            reason="the cited URL was not read in this run; it is kept only in the run record",
        )
        for c in citations.unfetched
    ]
    rows += [
        ClaimCheckRow(layer="code", kind="number", claim=number, verdict="unsupported")
        for number in code.unsupported_numbers
    ]
    return rows


def verifier_rows(verification: Verification, answer: QuizItem | None) -> list[ClaimCheckRow]:
    """Layer 2 and 3 results as one row per claim."""
    rows: list[ClaimCheckRow] = []
    haiku = verification.haiku
    if haiku is not None:
        if answer is not None and haiku.answer_verdict is not None:
            rows.append(
                ClaimCheckRow(
                    layer="haiku",
                    kind="correct_answer",
                    claim=answer.correct_option,
                    verdict=haiku.answer_verdict,
                    reason=haiku.answer_quote or None,
                )
            )
        rows += [
            ClaimCheckRow(
                layer="haiku",
                kind="distractor",
                claim=judged.option,
                verdict=judged.verdict,
                reason=judged.reason,
            )
            for judged in haiku.distractors
        ]
        rows += [
            ClaimCheckRow(layer="haiku", kind="explanation", claim=problem, verdict="problem")
            for problem in haiku.explanation_problems
        ]
    if verification.jev is not None:
        rows += jev_rows(verification.jev)
    return rows


def jev_rows(jev: JevReport) -> list[ClaimCheckRow]:
    """Layer 3 results as one row per claim."""
    return [
        ClaimCheckRow(
            layer="jev",
            kind=check.kind,
            claim=check.claim,
            verdict=check.verdict,
            confidence=check.confidence,
            probabilities=check.probabilities,
            model=jev.model,
        )
        for check in jev.checks
    ]


def build_item(record: ItemRecord) -> ItemRow | None:
    """The bank row for a run's answer, or None when the run produced no answer."""
    run = record.run
    answer = run.answer
    if answer is None:
        return None
    verification = record.verification
    code = verification.code if verification is not None else run.code_check
    if code is None:
        return None
    quiz = answer if isinstance(answer, QuizItem) else None
    haiku = verification.haiku if verification is not None else None
    jev = verification.jev if verification is not None else None
    checks = code_check_rows(code)
    if verification is not None:
        checks += verifier_rows(verification, quiz)
    return ItemRow(
        mode=run.mode,
        difficulty=run.difficulty,
        # A run whose answer failed layer 1 is never verified and never published.
        status=record.status or "discarded",
        question=quiz.question if quiz else None,
        options=list(quiz.options) if quiz else None,
        correct_index=quiz.correct_index if quiz else None,
        explanation=answer.explanation,
        gate_rule=record.rule,
        code_passed=code.passed,
        code_problems=list(code.describe(show_unread_urls=False)),
        haiku_verdict=haiku.verdict if haiku else None,
        haiku_reasons=list(haiku.reasons) if haiku else [],
        jev_verdict=jev.verdict if jev else None,
        jev_reasons=list(jev.reasons) if jev else [],
        jev_model=jev.model if jev else None,
        jev_criteria=jev.criteria if jev else None,
        jev_threshold=jev.threshold if jev else None,
        # Only citations that passed layer 1: fetched in this run and quoted word for word.
        sources=[
            SourceRow(ordinal=i, url=c.url, quote=c.quote)
            for i, c in enumerate(code.citations.kept)
        ],
        claim_checks=checks,
    )


def build_payload(
    record: ItemRecord,
    topic: TopicRef,
    source: RunSource,
    curator_run_id: int | None = None,
    client_id: UUID | None = None,
) -> ItemPayload:
    run = record.run
    verification = record.verification
    haiku = verification.haiku if verification is not None else None
    jev = verification.jev if verification is not None else None
    tool_calls, tool_errors = tool_counts(run.steps)
    usage = run.usage
    return ItemPayload(
        topic=topic,
        run=RunRow(
            client_id=client_id or uuid4(),
            curator_run_id=curator_run_id,
            source=source,
            mode=run.mode,
            difficulty=run.difficulty,
            model=run.model,
            outcome=run.outcome,
            detail=run.detail,
            budget_reason=run.detail if run.outcome == "budget_exceeded" else None,
            model_calls=run.model_calls,
            nudges=run.nudges,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            agent_cost_usd=run.cost_usd,
            seconds=run.seconds,
            tool_calls=tool_calls,
            tool_errors=tool_errors,
            pages_by_domain=dict(Counter(domain(url) for url in run.pages_read)),
            fetched_urls=list(run.fetched_urls),
            steps=[step.model_dump(mode="json") for step in run.steps],
            verifier_input_tokens=haiku.usage.total_input_tokens if haiku else 0,
            verifier_output_tokens=haiku.usage.output_tokens if haiku else 0,
            verifier_cost_usd=haiku.cost_usd if haiku else 0.0,
            verifier_seconds=haiku.seconds if haiku else 0.0,
            jev_input_tokens=jev.input_tokens if jev else 0,
            jev_cost_usd=jev.cost_usd if jev else 0.0,
            jev_seconds=jev.seconds if jev else 0.0,
            # Page text is stored once, in cited_pages, not again inside the record.
            record=record.model_copy(
                update={"run": run.model_copy(update={"cited_pages": {}})}
            ).model_dump(mode="json"),
        ),
        cited_pages=[PageRow(url=url, page_text=text) for url, text in run.cited_pages.items()],
        item=build_item(record),
    )


# --- Store interface and the Supabase implementation ---------------------------------------------

JobKey = tuple[str, Mode, Difficulty]


def job_key(topic: str, mode: Mode, difficulty: Difficulty) -> JobKey:
    """Topics are matched case-insensitively, as the database's unique index does."""
    return (topic.strip().casefold(), mode, difficulty)


class Store(Protocol):
    def start_curator_run(
        self, trigger: CuratorTrigger, topics: Sequence[str], dollar_cap: float
    ) -> int: ...

    def finish_curator_run(self, curator_run_id: int, summary: CuratorSummary) -> None: ...

    def record_item(self, payload: ItemPayload) -> RecordedIds: ...

    def attempted_jobs(self, topics: Sequence[str]) -> set[JobKey]: ...

    def topics(self) -> list[TopicRef]: ...

    def retire_stale(self) -> int: ...


# --- The review queue -------------------------------------------------------------------------

ReviewDecision = Literal["published", "discarded"]


class ReviewSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    ordinal: int
    url: str
    quote: str


class ReviewCheck(BaseModel):
    """One Jev claim check, as shown to the reviewer."""

    model_config = ConfigDict(frozen=True)

    kind: CheckKind
    claim: str
    verdict: str
    confidence: float | None = None


class ReviewTopic(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    kind: TopicKind


class ReviewItem(BaseModel):
    """An item waiting for a person, with everything needed to judge it."""

    model_config = ConfigDict(frozen=True)

    id: int
    mode: Mode
    difficulty: Difficulty
    question: str | None = None
    options: list[str] | None = None
    correct_index: int | None = None
    explanation: str
    code_problems: list[str] = Field(default_factory=list)
    haiku_reasons: list[str] = Field(default_factory=list)
    jev_reasons: list[str] = Field(default_factory=list)
    jev_criteria: str | None = None
    jev_threshold: float | None = None
    created_at: datetime
    topics: ReviewTopic
    sources: list[ReviewSource]
    claim_checks: list[ReviewCheck] = Field(default_factory=list)


class JevRecheck(BaseModel):
    """An item the gate sent to review because its Jev check failed, with what a re-check needs:
    the run's stored record (the answer and the other layers' results) and the page text it
    cited."""

    model_config = ConfigDict(frozen=True)

    item_id: int
    topic: str
    record: ItemRecord
    pages: dict[str, str]


class _TopicName(BaseModel):
    name: str


class _RunRecord(BaseModel):
    record: ItemRecord


class _RecheckRow(BaseModel):
    id: int
    run_id: int
    topics: _TopicName
    runs: _RunRecord


class _PageRow(BaseModel):
    run_id: int
    url: str
    page_text: str


_RECHECK_ROWS = TypeAdapter(list[_RecheckRow])
_PAGE_ROWS = TypeAdapter(list[_PageRow])


class ReviewStore(Protocol):
    def review_queue(self) -> list[ReviewItem]: ...

    def decide_review(self, item_id: int, decision: ReviewDecision) -> bool: ...


class _AttemptedJob(BaseModel):
    topic: str
    mode: Mode
    difficulty: Difficulty


class _IdRow(BaseModel):
    id: int


class _UsageRow(BaseModel):
    started_at: datetime
    reserved_usd: float
    spent_usd: float | None
    # Null on the run that opened a search (migration 006), the one the search limits count.
    search_id: int | None = None

    @property
    def opens_search(self) -> bool:
        return self.search_id is None

    @property
    def counted_usd(self) -> float:
        """What the caps count: the real cost once the run has ended, its reservation until then."""
        return self.reserved_usd if self.spent_usd is None else self.spent_usd


_ATTEMPTED = TypeAdapter(list[_AttemptedJob])
_ID_ROWS = TypeAdapter(list[_IdRow])
_TOPICS = TypeAdapter(list[TopicRef])
_COUNT = TypeAdapter(int)
_REVIEW_ITEMS = TypeAdapter(list[ReviewItem])
_REQUEST_COUNT = TypeAdapter(RequestCount)
_RUN_SLOT = TypeAdapter(RunSlot)
_USAGE_ROWS = TypeAdapter(list[_UsageRow])
_REVIEW_SELECT = (
    "id,mode,difficulty,question,options,correct_index,explanation,code_problems,haiku_reasons,"
    "jev_reasons,jev_criteria,jev_threshold,created_at,topics(name,kind),sources(ordinal,url,quote),"
    "claim_checks(kind,claim,verdict,confidence)"
)

_TOPICS_LIMIT = 1000
_NUL = chr(0)


def _without_nul(value: object) -> object:
    """Postgres text and jsonb cannot hold the NUL character, which fetched page text can."""
    if isinstance(value, str):
        return value.replace(_NUL, "")
    if isinstance(value, list):
        return [_without_nul(item) for item in value]
    if isinstance(value, dict):
        return {key: _without_nul(item) for key, item in value.items()}
    return value


class SupabaseStore:
    """The bank over Supabase's REST API (PostgREST), authenticated with the secret key.

    Requests that are safe to repeat (reads, record_item(), finishing a curator run) are
    retried with a growing wait (`agent/rest.py`). Creating a curator run and deciding a review
    item are sent once.
    """

    def __init__(
        self,
        url: str,
        secret_key: str,
        *,
        timeout_seconds: float = 30.0,
        retry_backoff_seconds: float = 1.0,
        client: httpx2.Client | None = None,
    ) -> None:
        self._rest = RestClient(
            url,
            secret_key,
            timeout_seconds=timeout_seconds,
            retry_backoff_seconds=retry_backoff_seconds,
            client=client,
        )

    @classmethod
    def from_env(cls) -> Self:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        if not url or not key:
            raise StoreError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set (see .env.example)")
        return cls(url, key)

    def close(self) -> None:
        self._rest.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def start_curator_run(
        self, trigger: CuratorTrigger, topics: Sequence[str], dollar_cap: float
    ) -> int:
        reply = self._rest.send(
            "POST",
            "/curator_runs",
            json={"trigger": trigger, "topics": list(topics), "dollar_cap": dollar_cap},
            params={"select": "id"},
            headers={"Prefer": "return=representation"},
        )
        rows = parse(_ID_ROWS, reply, "creating a curator run")
        if not rows:
            raise StoreError("creating a curator run returned no row")
        return rows[0].id

    def finish_curator_run(self, curator_run_id: int, summary: CuratorSummary) -> None:
        body = {**summary.model_dump(mode="json"), "finished_at": datetime.now(UTC).isoformat()}
        self._rest.send(
            "PATCH",
            "/curator_runs",
            json=body,
            params={"id": f"eq.{curator_run_id}"},
            retries=RETRIES,
        )

    def record_item(self, payload: ItemPayload) -> RecordedIds:
        body = _without_nul({"payload": payload.model_dump(mode="json")})
        reply = self._rest.send("POST", "/rpc/record_item", json=body, retries=RETRIES)
        return parse(TypeAdapter(RecordedIds), reply, "record_item")

    def attempted_jobs(self, topics: Sequence[str]) -> set[JobKey]:
        reply = self._rest.send(
            "POST", "/rpc/attempted_jobs", json={"topic_names": list(topics)}, retries=RETRIES
        )
        jobs = parse(_ATTEMPTED, reply, "attempted_jobs")
        return {job_key(job.topic, job.mode, job.difficulty) for job in jobs}

    def topics(self) -> list[TopicRef]:
        """Every topic, most recent first (the latest 1,000), with each news topic's article."""
        reply = self._rest.send(
            "GET",
            "/topics",
            params={
                "select": "name,kind,lead_url,retire_after",
                "order": "created_at.desc",
                "limit": str(_TOPICS_LIMIT),
            },
            retries=RETRIES,
        )
        return parse(_TOPICS, reply, "reading topics")

    def add_report(self, item_id: int, user_hash: str, reason: str | None) -> bool:
        """Record a player's report of an item. False if this player had already reported it.
        Two reports hide an item (a trigger in supabase/schema.sql)."""
        try:
            self._rest.send(
                "POST",
                "/reports",
                json={"item_id": item_id, "user_hash": user_hash, "reason": reason},
                headers={"Prefer": "return=minimal"},
            )
        except StoreError as error:
            if error.status == 409:  # unique (item_id, user_hash): already reported
                return False
            raise
        return True

    def hit_request_limit(self, user_hash: str, limit: int) -> RequestCount:
        """Count one API request for a visitor in the current hour. Sent once: a retry could
        count the same request twice."""
        reply = self._rest.send(
            "POST", "/rpc/hit_request_limit", json={"p_user_hash": user_hash, "p_limit": limit}
        )
        return parse(_REQUEST_COUNT, reply, "hit_request_limit")

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
        """Start a live run if the limits allow it, reserving `reserve_usd` against the dollar
        caps until `finish_on_demand_run` (migration 006). Without `search_id` the run opens a
        search, which counts against the daily search limits; with it, the run joins that search
        and is not counted again. Sent once."""
        reply = self._rest.send(
            "POST",
            "/rpc/begin_on_demand_run",
            json={
                "p_user_hash": user_hash,
                "p_topic": topic,
                "p_mode": mode,
                "p_difficulty": difficulty,
                "p_search_id": search_id,
                "p_reserve_usd": round(reserve_usd, 6),
                "p_user_day_searches": limits.user_searches_per_day,
                "p_day_searches": limits.searches_per_day,
                "p_search_runs": limits.runs_per_search,
                "p_day_usd": limits.usd_per_day,
                "p_month_usd": limits.usd_per_month,
            },
        )
        return parse(_RUN_SLOT, reply, "begin_on_demand_run")

    def on_demand_usage(self, user_hash: str, now: datetime) -> OnDemandUsage:
        """Live searches so far today (the visitor's and everyone's) and the money spent today
        and this month, for the quota. Two small reads: the visitor's own searches today (at
        most the daily limit), and every run this month. No visitor hash leaves the database in
        either."""
        day = day_start(now)
        mine = self._rest.send(
            "GET",
            "/on_demand_runs",
            params={
                "select": "id",
                "user_hash": f"eq.{user_hash}",
                "started_at": f"gte.{day.isoformat()}",
                "search_id": "is.null",
            },
            retries=RETRIES,
        )
        visitor_searches = parse(_ID_ROWS, mine, "reading the visitor's live searches")
        rows = parse(
            _USAGE_ROWS,
            self._rest.read_all(
                "/on_demand_runs",
                {
                    "select": "started_at,reserved_usd,spent_usd,search_id",
                    "started_at": f"gte.{month_start(now).isoformat()}",
                    "order": "id",
                },
            ),
            "reading this month's live runs",
        )
        today = [row for row in rows if row.started_at >= day]
        return OnDemandUsage(
            visitor_searches_today=len(visitor_searches),
            searches_today=sum(1 for row in today if row.opens_search),
            usd_today=sum(row.counted_usd for row in today),
            usd_this_month=sum(row.counted_usd for row in rows),
        )

    def finish_on_demand_run(
        self, slot_id: int, spent_usd: float, outcome: OnDemandOutcome, run_id: int | None
    ) -> None:
        """Record how a live run ended and what it cost. Only the first call counts, so it is
        safe to retry."""
        self._rest.send(
            "POST",
            "/rpc/finish_on_demand_run",
            json={
                "p_id": slot_id,
                "p_spent_usd": round(spent_usd, 6),
                "p_outcome": outcome,
                "p_run_id": run_id,
            },
            retries=RETRIES,
        )

    def jev_recheck_targets(self) -> list[JevRecheck]:
        """Items in review whose Jev check failed (an outage or a wrong key), oldest first."""
        reply = self._rest.send(
            "GET",
            "/items",
            params={
                "select": "id,run_id,topics(name),runs(record)",
                "status": "eq.review",
                "jev_verdict": "eq.error",
                "order": "id.asc",
            },
            retries=RETRIES,
        )
        rows = parse(_RECHECK_ROWS, reply, "reading items to re-check")
        if not rows:
            return []
        run_ids = ",".join(str(row.run_id) for row in rows)
        pages = parse(
            _PAGE_ROWS,
            self._rest.read_all(
                "/cited_pages",
                {
                    "select": "run_id,url,page_text",
                    "run_id": f"in.({run_ids})",
                    "order": "run_id,url",
                },
            ),
            "reading cited pages",
        )
        by_run: dict[int, dict[str, str]] = {}
        for page in pages:
            by_run.setdefault(page.run_id, {})[page.url] = page.page_text
        return [
            JevRecheck(
                item_id=row.id,
                topic=row.topics.name,
                record=row.runs.record,
                pages=by_run.get(row.run_id, {}),
            )
            for row in rows
        ]

    def apply_jev_recheck(self, item_id: int, status: Status, jev: JevReport) -> None:
        """Store a re-check's Jev results and the gate's new status in one transaction
        (migration 005). Sent once: it refuses an item that is no longer in review."""
        self._rest.send(
            "POST",
            "/rpc/apply_jev_recheck",
            json={
                "p_item_id": item_id,
                "p_status": status,
                "p_jev": {
                    "verdict": jev.verdict,
                    "reasons": list(jev.reasons),
                    "model": jev.model,
                    "criteria": jev.criteria,
                    "threshold": jev.threshold,
                    "input_tokens": jev.input_tokens,
                    "cost_usd": round(jev.cost_usd, 8),
                    "seconds": jev.seconds,
                    "checks": [row.model_dump(mode="json") for row in jev_rows(jev)],
                },
            },
        )

    def retire_stale(self) -> int:
        return parse(_COUNT, self._rest.send("POST", "/rpc/retire_stale", json={}), "retire_stale")

    def review_queue(self) -> list[ReviewItem]:
        """Every item in review, oldest first, with its sources and Jev's claim checks."""
        reply = self._rest.send(
            "GET",
            "/items",
            params={
                "select": _REVIEW_SELECT,
                "status": "eq.review",
                "order": "id.asc",
                "sources.order": "ordinal.asc",
                "claim_checks.layer": "eq.jev",
                "claim_checks.order": "id.asc",
            },
            retries=RETRIES,
        )
        return parse(_REVIEW_ITEMS, reply, "reading the review queue")

    def decide_review(self, item_id: int, decision: ReviewDecision) -> bool:
        """Move an item out of review. False if it was no longer in review (decided elsewhere)."""
        reply = self._rest.send(
            "PATCH",
            "/items",
            json={"status": decision},
            params={"id": f"eq.{item_id}", "status": "eq.review", "select": "id"},
            headers={"Prefer": "return=representation"},
        )
        return len(parse(_ID_ROWS, reply, "deciding a review item")) == 1
