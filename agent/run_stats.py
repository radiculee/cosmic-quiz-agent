"""What one live run measured, as the analytics panel's "This search" tab shows it.

`run_stats` builds a `RunStats` from a run's record once the publish gate has decided it;
`agent/ondemand.py` sends one with each run of a search (docs/PLAN.md Session 9). It holds
numbers only: no claim text, no option a check was about, no verifier reasons, no URLs (domains
only) and no tool arguments, so a question still waiting for its answer cannot be given away by
the panel.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict

from agent.schemas import (
    Difficulty,
    ItemRecord,
    JevVerdict,
    LayerVerdict,
    Mode,
    Outcome,
    Status,
    Step,
)
from agent.store import domain, tool_counts

NO_TOOL_CALLS = "no tool calls"


class StepTiming(BaseModel):
    """One step of the run: a model call (with how many tools it asked for) or a tool call."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["model", "tool"]
    tool: str | None = None  # the tool's name; None for a model call
    seconds: float
    tools_asked: int = 0  # a model call that asks for two or more tools runs them in parallel
    is_error: bool = False


class RunTokens(BaseModel):
    model_config = ConfigDict(frozen=True)

    input: int
    output: int
    cache_write: int
    cache_read: int
    verifier_input: int
    verifier_output: int
    jev_input: int


class RunCost(BaseModel):
    """Anthropic (the agent and the Haiku verifier) and TypeSafe (Jev), in USD."""

    model_config = ConfigDict(frozen=True)

    agent_usd: float
    verifier_usd: float
    jev_usd: float


class RunSeconds(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent: float
    verifier: float
    jev: float


class JevCounts(BaseModel):
    """How many of Jev's claim checks came out each way. Counts only: which option a verdict
    was about would give a quiz answer away."""

    model_config = ConfigDict(frozen=True)

    supports: int = 0
    contradicts: int = 0
    says_nothing: int = 0


class RunStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: Mode
    difficulty: Difficulty
    model: str
    outcome: Outcome
    status: Status | None  # the publish gate's decision; None when the run gave no answer
    model_calls: int
    nudges: int
    tokens: RunTokens
    cost: RunCost
    seconds: RunSeconds
    tool_calls: dict[str, int]
    tool_errors: int
    pages_by_domain: dict[str, int]
    citations_kept: int
    citations_dropped: int  # not read in the run, or not word for word on the page
    haiku: LayerVerdict | None
    jev: LayerVerdict | None
    jev_checks: JevCounts
    steps: list[StepTiming]


def tools_asked(step: Step) -> int:
    """How many tools a model call asked for, from its logged summary ("a, b (stop: tool_use)",
    agent/loop.py). Tool names never contain a comma."""
    if step.kind != "model":
        return 0
    called = step.summary.split(" (stop:", 1)[0].strip()
    if not called or called == NO_TOOL_CALLS:
        return 0
    return len(called.split(", "))


def run_stats(record: ItemRecord) -> RunStats:
    """The figures for one run, from its record (the same numbers `build_payload` stores)."""
    run = record.run
    verification = record.verification
    haiku = verification.haiku if verification is not None else None
    jev = verification.jev if verification is not None else None
    code = verification.code if verification is not None else run.code_check
    tool_calls, tool_errors = tool_counts(run.steps)
    verdicts: Counter[JevVerdict] = Counter()
    if jev is not None:
        verdicts.update(check.verdict for check in jev.checks)
    return RunStats(
        mode=run.mode,
        difficulty=run.difficulty,
        model=run.model,
        outcome=run.outcome,
        status=record.status,
        model_calls=run.model_calls,
        nudges=run.nudges,
        tokens=RunTokens(
            input=run.usage.input_tokens,
            output=run.usage.output_tokens,
            cache_write=run.usage.cache_write_tokens,
            cache_read=run.usage.cache_read_tokens,
            verifier_input=haiku.usage.total_input_tokens if haiku else 0,
            verifier_output=haiku.usage.output_tokens if haiku else 0,
            jev_input=jev.input_tokens if jev else 0,
        ),
        cost=RunCost(
            agent_usd=run.cost_usd,
            verifier_usd=haiku.cost_usd if haiku else 0.0,
            jev_usd=jev.cost_usd if jev else 0.0,
        ),
        seconds=RunSeconds(
            agent=run.seconds,
            verifier=haiku.seconds if haiku else 0.0,
            jev=jev.seconds if jev else 0.0,
        ),
        tool_calls=tool_calls,
        tool_errors=tool_errors,
        pages_by_domain=dict(Counter(domain(url) for url in run.pages_read)),
        citations_kept=len(code.citations.kept) if code else 0,
        citations_dropped=(
            len(code.citations.unfetched) + len(code.citations.misquoted) if code else 0
        ),
        haiku=haiku.verdict if haiku else None,
        jev=jev.verdict if jev else None,
        jev_checks=JevCounts(
            supports=verdicts["supports"],
            contradicts=verdicts["contradicts"],
            says_nothing=verdicts["says_nothing"],
        ),
        steps=[
            StepTiming(
                kind=step.kind,
                tool=step.tool if step.kind == "tool" else None,
                seconds=step.seconds,
                tools_asked=tools_asked(step),
                is_error=step.is_error,
            )
            for step in run.steps
        ],
    )
