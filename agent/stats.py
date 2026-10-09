"""Analytics for nerds: the agent's measured statistics, as "The agent" tab shows them.

`agent_stats()` (migration 007) does the counting in the database and returns aggregates only;
it is the one thing the publishable key may run against the private tables, so salted IP
hashes, step logs and page text never leave the server. `StatsReader` calls it, and the models
here check the reply field by field, so a change on either side fails loudly in one place.

Prices stay in `agent/config.py`: the database returns token counts per model, and
`caching_savings` prices them here, so no price is ever written into SQL.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from agent.config import ANTHROPIC_MONTHLY_LIMIT_USD, PRICES
from agent.limits import LIMITS
from agent.llm import Usage
from agent.rest import RETRIES, RestClient, StoreError, parse
from agent.schemas import ClaimKind, Difficulty, JevVerdict, LayerVerdict, Mode, Outcome, Status
from agent.store import RunSource

# The ranges the page offers, in days; None is all time. agent_stats() accepts any number of
# days, but the API takes only these, so each filter set is one edge-cache entry.
PERIODS: tuple[int, ...] = (7, 30)
CONFIDENCE_BINS = 10

BankStatus = Literal["published", "review", "discarded", "retired"]


class StatsFilters(BaseModel):
    """Which runs the figures cover. None is "all"."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Mode | None = None
    difficulty: Difficulty | None = None
    source: RunSource | None = None
    days: int | None = None


# --- The reply of agent_stats() -------------------------------------------------------------------


class _Reply(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Percentiles(_Reply):
    """None when there was nothing to measure."""

    median: float | None
    p95: float | None


class LayerCost(_Reply):
    agent_usd: float
    verifier_usd: float
    jev_usd: float


class Volume(_Reply):
    runs: int
    first_run_at: datetime | None
    last_run_at: datetime | None
    outcomes: dict[Outcome, int]
    # What the publish gate decided when each run was stored, before any review.
    gate: dict[Status, int]
    cost: LayerCost


class ModelTokens(_Reply):
    model: str
    runs: int
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    agent_usd: float


class Tokens(_Reply):
    by_model: list[ModelTokens]
    verifier_input_tokens: int
    verifier_output_tokens: int
    jev_input_tokens: int


class ToolSpeed(_Reply):
    tool: str
    calls: int
    errors: int
    median: float | None
    p95: float | None


class Speed(_Reply):
    run_seconds: Percentiles
    total_seconds: Percentiles
    model_call_seconds: Percentiles
    verifier_seconds: Percentiles
    jev_seconds: Percentiles
    tools: list[ToolSpeed]


class CallsBin(_Reply):
    calls: int
    runs: int


class DomainPages(_Reply):
    domain: str
    pages: int


class BudgetRuns(_Reply):
    budget: str  # "step", "time" or "token" (agent/loop.py)
    runs: int


class Citations(_Reply):
    kept: int
    misquoted: int
    unfetched: int


class Behaviour(_Reply):
    model_calls: list[CallsBin]
    model_steps: int
    tool_steps: int
    parallel_steps: int
    pages_by_domain: list[DomainPages]
    nudges: int
    nudged_runs: int
    budgets: list[BudgetRuns]
    answers: int
    citations: Citations
    unsupported_number_answers: int


class Agreement(_Reply):
    haiku: LayerVerdict
    jev: LayerVerdict
    items: int


class JevClaims(_Reply):
    kind: ClaimKind
    verdict: JevVerdict
    checks: int


class Confidence(_Reply):
    bins: list[int] = Field(min_length=CONFIDENCE_BINS, max_length=CONFIDENCE_BINS)
    exactly_one: int


class ReviewReasons(_Reply):
    """Why the gate sent items to review. An item can count under several reasons."""

    items: int
    haiku_doubt: int
    jev_doubt: int
    verifier_error: int
    explanation: int
    unsettled_option: int
    verifier_quote: int


class Verifiers(_Reply):
    haiku: dict[LayerVerdict, int]
    jev: dict[LayerVerdict, int]
    agreement: list[Agreement]
    jev_claims: list[JevClaims]
    jev_confidence: Confidence
    review: ReviewReasons


class GridCell(_Reply):
    mode: Mode
    difficulty: Difficulty
    runs: int
    published: int
    anthropic_usd: float
    jev_usd: float
    median_seconds: float | None


class MonthSpend(_Reply):
    """This month's recorded spend in UTC, whatever the filters."""

    month_start: datetime
    anthropic_usd: float
    typesafe_usd: float
    typesafe_all_time_usd: float
    live_usd: float


class AgentStats(_Reply):
    filters: StatsFilters
    generated_at: datetime
    volume: Volume
    bank: dict[BankStatus, int]
    tokens: Tokens
    speed: Speed
    behaviour: Behaviour
    verifiers: Verifiers
    grid: list[GridCell]
    budget: MonthSpend


_AGENT_STATS = TypeAdapter(AgentStats)


# --- What the API adds ----------------------------------------------------------------------------


class CachingSavings(BaseModel):
    """What prompt caching saved: the agent's tokens priced with and without it."""

    model_config = ConfigDict(frozen=True)

    uncached_usd: float
    cached_usd: float
    saved_usd: float  # negative when cache writes cost more than the reads saved
    unpriced_runs: int  # runs of a model with no price entry, left out of the sums


class Caps(BaseModel):
    """The monthly limits the spend is shown against."""

    model_config = ConfigDict(frozen=True)

    anthropic_month_usd: float
    live_month_usd: float


class StatsReply(BaseModel):
    """GET /api/stats."""

    model_config = ConfigDict(frozen=True)

    stats: AgentStats
    caching: CachingSavings
    caps: Caps


def caching_savings(tokens: Tokens) -> CachingSavings:
    """Price each model's tokens as sent (cache writes and reads at their own rates) and as if
    every prompt token had been sent uncached, from the price table in `agent/config.py`."""
    uncached = cached = 0.0
    unpriced = 0
    for entry in tokens.by_model:
        price = PRICES.get(entry.model)
        if price is None:
            unpriced += entry.runs
            continue
        usage = Usage(
            input_tokens=entry.input_tokens,
            output_tokens=entry.output_tokens,
            cache_write_tokens=entry.cache_write_tokens,
            cache_read_tokens=entry.cache_read_tokens,
        )
        cached += usage.cost_usd(price)
        plain = Usage(input_tokens=usage.total_input_tokens, output_tokens=usage.output_tokens)
        uncached += plain.cost_usd(price)
    return CachingSavings(
        uncached_usd=uncached,
        cached_usd=cached,
        saved_usd=uncached - cached,
        unpriced_runs=unpriced,
    )


def stats_reply(stats: AgentStats) -> StatsReply:
    return StatsReply(
        stats=stats,
        caching=caching_savings(stats.tokens),
        caps=Caps(
            anthropic_month_usd=ANTHROPIC_MONTHLY_LIMIT_USD, live_month_usd=LIMITS.usd_per_month
        ),
    )


# --- Reading --------------------------------------------------------------------------------------


class StatsReader:
    """Calls agent_stats() with the publishable key: aggregates are all that key can see of the
    agent's runs."""

    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    @classmethod
    def from_env(cls) -> Self:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
        if not url or not key:
            raise StoreError("SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be set")
        return cls(RestClient(url, key))

    def close(self) -> None:
        self._rest.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def agent_stats(self, filters: StatsFilters) -> AgentStats:
        # A read-only function, so a retry is safe.
        reply = self._rest.send(
            "POST",
            "/rpc/agent_stats",
            json={
                "p_mode": filters.mode,
                "p_difficulty": filters.difficulty,
                "p_source": filters.source,
                "p_days": filters.days,
            },
            retries=RETRIES,
        )
        return parse(_AGENT_STATS, reply, "reading the agent's statistics")
