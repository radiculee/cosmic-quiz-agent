"""Check agent_stats() against an independent Python version of it, read-only.

    python -m dev.check_stats

Analytics for nerds publishes what `agent_stats()` (supabase/migrations/007_agent_stats.sql)
counts, so this checks the SQL the way a reader would: it reads the raw rows (runs, items,
claim_checks, on_demand_runs) with the secret key, works every figure out again in Python, calls
the live function with the publishable key as /api/stats does, and compares the two documents
field by field on seven filter sets. It also says whether /api/stats's models would accept each
reply. Run it after any migration that changes agent_stats().

Nothing is written and no paid API is called. Like the rest of dev/, it is never deployed
(vercel.json excludes dev/**). Exit status: 0 when every filter set matches, 1 when one differs,
2 when the database cannot be read.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TypeGuard

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from agent.console import use_utf8_output
from agent.rest import RETRIES, RestClient, StoreError, parse
from agent.stats import CONFIDENCE_BINS, AgentStats, StatsFilters

Json = dict[str, object]

# The values each count is broken down by, as the SQL lists them.
OUTCOMES = ("passed", "failed_checks", "no_answer", "budget_exceeded", "llm_error")
GATE = ("published", "review", "discarded")
BANK = ("published", "review", "discarded", "retired")
LAYER_VERDICTS = ("pass", "borderline", "fail", "error")
CITATIONS = ("kept", "misquoted", "unfetched")
DIFFICULTY_ORDER = ("easy", "medium", "hard")

# What the comparison covers: every filter, alone and together, and both ranges.
FILTER_SETS = (
    StatsFilters(),
    StatsFilters(mode="quiz"),
    StatsFilters(mode="learn", difficulty="hard"),
    StatsFilters(source="on_demand"),
    StatsFilters(source="curator", difficulty="easy"),
    StatsFilters(days=7),
    StatsFilters(days=30, mode="quiz", difficulty="medium"),
)

# Sums are compared to a millionth of a dollar or second; timestamps as instants.
TOLERANCE = 1e-6
TIMESTAMPS = ("_at", "month_start")


# --- The raw rows -------------------------------------------------------------------------------


class _Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class StepRow(_Row):
    """One entry of `runs.steps`: a model call or a tool call (agent.schemas.Step)."""

    kind: str
    summary: str | None = None
    seconds: float
    tool: str | None = None
    is_error: bool | None = None

    @property
    def called(self) -> str | None:
        """The tools a model call asked for: its summary up to " (stop:", as split_part does.
        "tool_a, tool_b (stop: tool_use)" is "tool_a, tool_b"."""
        return None if self.summary is None else self.summary.split(" (stop:", 1)[0]


class RunRow(_Row):
    """A `runs` row, with what agent_stats() takes from its stored record."""

    id: int
    source: str
    mode: str
    difficulty: str
    model: str
    outcome: str
    budget_reason: str | None
    model_calls: int
    nudges: int
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    agent_cost_usd: float
    seconds: float
    pages_by_domain: dict[str, int]
    steps: list[StepRow]
    verifier_input_tokens: int
    verifier_output_tokens: int
    verifier_cost_usd: float
    verifier_seconds: float
    jev_input_tokens: int
    jev_cost_usd: float
    jev_seconds: float
    created_at: datetime
    # From `record`: the gate's decision, the Haiku verifier's report and Jev's verdict.
    gate_status: str | None
    haiku: object = None
    jev_verdict: str | None

    @property
    def haiku_report(self) -> dict[str, object] | None:
        """The Haiku verifier's report when it is a JSON object (jsonb_typeof = 'object')."""
        return self.haiku if isinstance(self.haiku, dict) else None

    @property
    def haiku_verdict(self) -> str | None:
        report = self.haiku_report
        verdict = None if report is None else report.get("verdict")
        return verdict if isinstance(verdict, str) else None


class ItemRow(_Row):
    id: int
    run_id: int
    status: str


class CheckRow(_Row):
    item_id: int
    layer: str
    kind: str
    verdict: str
    confidence: float | None


class LiveRunRow(_Row):
    """An `on_demand_runs` row: what a live run reserved, and spent once it ended."""

    started_at: datetime
    reserved_usd: float
    spent_usd: float | None


@dataclass(frozen=True)
class Rows:
    runs: list[RunRow]
    items: list[ItemRow]
    checks: list[CheckRow]
    live_runs: list[LiveRunRow]


_RUN_COLUMNS = (
    "id,source,mode,difficulty,model,outcome,budget_reason,model_calls,nudges,input_tokens,"
    "output_tokens,cache_write_tokens,cache_read_tokens,agent_cost_usd,seconds,pages_by_domain,"
    "steps,verifier_input_tokens,verifier_output_tokens,verifier_cost_usd,verifier_seconds,"
    "jev_input_tokens,jev_cost_usd,jev_seconds,created_at,gate_status:record->>status,"
    "haiku:record->verification->haiku,jev_verdict:record->verification->jev->>verdict"
)


def read_rows(rest: RestClient) -> Rows:
    """Every row agent_stats() reads, with the secret key. Reads only."""
    return Rows(
        runs=parse(
            TypeAdapter(list[RunRow]),
            rest.read_all("/runs", {"select": _RUN_COLUMNS, "order": "id.asc"}),
            "reading runs",
        ),
        items=parse(
            TypeAdapter(list[ItemRow]),
            rest.read_all("/items", {"select": "id,run_id,status", "order": "id.asc"}),
            "reading items",
        ),
        checks=parse(
            TypeAdapter(list[CheckRow]),
            rest.read_all(
                "/claim_checks",
                {"select": "item_id,layer,kind,verdict,confidence", "order": "id.asc"},
            ),
            "reading claim_checks",
        ),
        live_runs=parse(
            TypeAdapter(list[LiveRunRow]),
            rest.read_all(
                "/on_demand_runs",
                {"select": "started_at,reserved_usd,spent_usd", "order": "id.asc"},
            ),
            "reading on_demand_runs",
        ),
    )


# --- agent_stats() in Python --------------------------------------------------------------------


def percentile(fraction: float, values: list[float]) -> float | None:
    """Postgres's percentile_cont: linear interpolation between the two nearest ranks."""
    if not values:
        return None
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def percentiles(values: list[float]) -> Json:
    return {"median": percentile(0.5, values), "p95": percentile(0.95, values)}


def confidence_bin(confidence: float) -> int | None:
    """The 0-based bin of width_bucket(confidence, 0, 1, 10), with 1.0 in the last bin as
    least(.., 10) puts it. None below 0, which the SQL's series of bins leaves out."""
    # numeric(5, 4) in the table, so the float's shortest form is the stored value exactly.
    exact = Decimal(str(confidence))
    if exact < 0:
        return None
    return min(int(exact * CONFIDENCE_BINS), CONFIDENCE_BINS - 1)


def count_by[T](rows: Iterable[T], key: Callable[[T], object], values: tuple[str, ...]) -> Json:
    counts = Counter(key(row) for row in rows)
    return {value: counts[value] for value in values}


def select_runs(
    rows: Rows, filters: StatsFilters, now: datetime
) -> tuple[list[RunRow], list[RunRow]]:
    """The runs in the period and source (`scope`, which the grid uses), and of those the runs
    in the mode and difficulty too (`picked`, which everything else uses)."""
    since = None if filters.days is None else now - timedelta(days=filters.days)
    scope = [
        run
        for run in rows.runs
        if (since is None or run.created_at >= since)
        and (filters.source is None or run.source == filters.source)
    ]
    picked = [
        run
        for run in scope
        if (filters.mode is None or run.mode == filters.mode)
        and (filters.difficulty is None or run.difficulty == filters.difficulty)
    ]
    return scope, picked


def reference_stats(rows: Rows, filters: StatsFilters, now: datetime) -> Json:
    """What agent_stats() should return for these filters at `now`. Each part follows the CTE
    of the same name in the migration."""
    scope, picked = select_runs(rows, filters, now)
    run_ids = {run.id for run in picked}
    steps = [step for run in picked for step in run.steps]
    answers = [item for item in rows.items if item.run_id in run_ids]
    answer_ids = {item.id for item in answers}
    checks = [check for check in rows.checks if check.item_id in answer_ids]
    month = now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "filters": filters.model_dump(mode="json"),
        "generated_at": now.isoformat(),
        "volume": _volume(picked),
        "bank": count_by(answers, lambda item: item.status, BANK),
        "tokens": _tokens(picked),
        "speed": _speed(picked, steps),
        "behaviour": _behaviour(picked, steps, answers, checks),
        "verifiers": _verifiers(picked, checks),
        "grid": _grid(scope),
        "budget": _budget(rows, month),
    }


def _volume(picked: list[RunRow]) -> Json:
    times = [run.created_at for run in picked]
    return {
        "runs": len(picked),
        "first_run_at": min(times).isoformat() if times else None,
        "last_run_at": max(times).isoformat() if times else None,
        "outcomes": count_by(picked, lambda run: run.outcome, OUTCOMES),
        "gate": count_by(picked, lambda run: run.gate_status, GATE),
        "cost": {
            "agent_usd": sum(run.agent_cost_usd for run in picked),
            "verifier_usd": sum(run.verifier_cost_usd for run in picked),
            "jev_usd": sum(run.jev_cost_usd for run in picked),
        },
    }


def _tokens(picked: list[RunRow]) -> Json:
    by_model: dict[str, list[RunRow]] = defaultdict(list)
    for run in picked:
        by_model[run.model].append(run)
    ordered = sorted(by_model.items(), key=lambda entry: (-len(entry[1]), entry[0]))
    return {
        "by_model": [
            {
                "model": model,
                "runs": len(runs),
                "input_tokens": sum(run.input_tokens for run in runs),
                "output_tokens": sum(run.output_tokens for run in runs),
                "cache_write_tokens": sum(run.cache_write_tokens for run in runs),
                "cache_read_tokens": sum(run.cache_read_tokens for run in runs),
                "agent_usd": sum(run.agent_cost_usd for run in runs),
            }
            for model, runs in ordered
        ],
        "verifier_input_tokens": sum(run.verifier_input_tokens for run in picked),
        "verifier_output_tokens": sum(run.verifier_output_tokens for run in picked),
        "jev_input_tokens": sum(run.jev_input_tokens for run in picked),
    }


def _speed(picked: list[RunRow], steps: list[StepRow]) -> Json:
    tools: dict[str, list[StepRow]] = defaultdict(list)
    for step in steps:
        if step.kind == "tool" and step.tool is not None:
            tools[step.tool].append(step)
    ordered = sorted(tools.items(), key=lambda entry: (-len(entry[1]), entry[0]))
    return {
        "run_seconds": percentiles([run.seconds for run in picked]),
        "total_seconds": percentiles(
            [run.seconds + run.verifier_seconds + run.jev_seconds for run in picked]
        ),
        "model_call_seconds": percentiles([step.seconds for step in steps if step.kind == "model"]),
        "verifier_seconds": percentiles(
            [run.verifier_seconds for run in picked if run.verifier_seconds > 0]
        ),
        "jev_seconds": percentiles([run.jev_seconds for run in picked if run.jev_seconds > 0]),
        "tools": [
            {
                "tool": tool,
                "calls": len(calls),
                "errors": sum(1 for call in calls if call.is_error),
                **percentiles([call.seconds for call in calls]),
            }
            for tool, calls in ordered
        ],
    }


def _behaviour(
    picked: list[RunRow], steps: list[StepRow], answers: list[ItemRow], checks: list[CheckRow]
) -> Json:
    model_steps = [step for step in steps if step.kind == "model"]
    calls_asked = [step.called for step in model_steps if step.called is not None]
    domains: Counter[str] = Counter()
    for run in picked:
        domains.update(run.pages_by_domain)
    budgets = Counter(
        run.budget_reason.split(" ", 1)[0]
        for run in picked
        if run.outcome == "budget_exceeded" and run.budget_reason is not None
    )
    code_checks = [check for check in checks if check.layer == "code"]
    return {
        "model_calls": [
            {"calls": calls, "runs": runs}
            for calls, runs in sorted(Counter(run.model_calls for run in picked).items())
        ],
        "model_steps": len(model_steps),
        "tool_steps": sum(1 for called in calls_asked if called != "no tool calls"),
        "parallel_steps": sum(1 for called in calls_asked if ", " in called),
        "pages_by_domain": [
            {"domain": domain, "pages": pages}
            for domain, pages in sorted(domains.items(), key=lambda entry: (-entry[1], entry[0]))
        ],
        "nudges": sum(run.nudges for run in picked),
        "nudged_runs": sum(1 for run in picked if run.nudges > 0),
        "budgets": [{"budget": budget, "runs": runs} for budget, runs in sorted(budgets.items())],
        "answers": len(answers),
        "citations": count_by(
            (check for check in code_checks if check.kind == "citation"),
            lambda check: check.verdict,
            CITATIONS,
        ),
        "unsupported_number_answers": len(
            {check.item_id for check in code_checks if check.kind == "number"}
        ),
    }


def _verifiers(picked: list[RunRow], checks: list[CheckRow]) -> Json:
    judged = [run for run in picked if run.haiku_report is not None]
    jev_checks = [check for check in checks if check.layer == "jev"]
    confidences = [check.confidence for check in jev_checks if check.confidence is not None]
    bins = [0] * CONFIDENCE_BINS
    for confidence in confidences:
        index = confidence_bin(confidence)
        if index is not None:
            bins[index] += 1
    agreement = Counter(
        (run.haiku_verdict, run.jev_verdict) for run in judged if run.jev_verdict is not None
    )
    claims = Counter((check.kind, check.verdict) for check in jev_checks)
    review = [run for run in picked if run.gate_status == "review"]
    return {
        "haiku": count_by(judged, lambda run: run.haiku_verdict, LAYER_VERDICTS),
        "jev": count_by(
            (run for run in picked if run.jev_verdict is not None),
            lambda run: run.jev_verdict,
            LAYER_VERDICTS,
        ),
        "agreement": [
            {"haiku": haiku, "jev": jev, "items": items}
            for (haiku, jev), items in sorted(
                agreement.items(), key=lambda entry: _text_order(entry[0])
            )
        ],
        "jev_claims": [
            {"kind": kind, "verdict": verdict, "checks": count}
            for (kind, verdict), count in sorted(claims.items())
        ],
        "jev_confidence": {
            "bins": bins,
            "exactly_one": sum(1 for confidence in confidences if confidence == 1),
        },
        "review": {
            "items": len(review),
            "haiku_doubt": sum(1 for run in review if run.haiku_verdict == "borderline"),
            "jev_doubt": sum(1 for run in review if run.jev_verdict == "borderline"),
            "verifier_error": sum(
                1
                for run in review
                if run.haiku_verdict == "error" or run.jev_verdict in ("error", None)
            ),
            "explanation": sum(1 for run in review if _explanation_doubted(run)),
            "unsettled_option": sum(1 for run in review if _option_unsettled(run)),
            "verifier_quote": sum(1 for run in review if _verifier_misquoted(run)),
        },
    }


def _text_order(values: tuple[str | None, ...]) -> tuple[tuple[bool, str], ...]:
    """A sort key that orders text as `order by` does, with nulls last."""
    return tuple((value is None, value or "") for value in values)


def _explanation_doubted(run: RunRow) -> bool:
    problems = (run.haiku_report or {}).get("explanation_problems")
    return isinstance(problems, list) and len(problems) > 0


def _option_unsettled(run: RunRow) -> bool:
    options = (run.haiku_report or {}).get("distractors")
    return isinstance(options, list) and any(
        isinstance(option, dict) and option.get("verdict") == "unclear" for option in options
    )


def _verifier_misquoted(run: RunRow) -> bool:
    report = run.haiku_report or {}
    return (
        report.get("answer_verdict") == "supported" and report.get("answer_quote_verbatim") is False
    )


def _grid(scope: list[RunRow]) -> list[Json]:
    cells: dict[tuple[str, str], list[RunRow]] = defaultdict(list)
    for run in scope:
        cells[(run.mode, run.difficulty)].append(run)
    ordered = sorted(
        cells.items(), key=lambda entry: (entry[0][0], DIFFICULTY_ORDER.index(entry[0][1]))
    )
    return [
        {
            "mode": mode,
            "difficulty": difficulty,
            "runs": len(runs),
            "published": sum(1 for run in runs if run.gate_status == "published"),
            "anthropic_usd": sum(run.agent_cost_usd + run.verifier_cost_usd for run in runs),
            "jev_usd": sum(run.jev_cost_usd for run in runs),
            "median_seconds": percentile(0.5, [run.seconds for run in runs]),
        }
        for (mode, difficulty), runs in ordered
    ]


def _budget(rows: Rows, month: datetime) -> Json:
    this_month = [run for run in rows.runs if run.created_at >= month]
    return {
        "month_start": month.isoformat(),
        "anthropic_usd": sum(run.agent_cost_usd + run.verifier_cost_usd for run in this_month),
        "typesafe_usd": sum(run.jev_cost_usd for run in this_month),
        "typesafe_all_time_usd": sum(run.jev_cost_usd for run in rows.runs),
        # A live run still going counts what it reserved, as begin_on_demand_run counts it.
        "live_usd": sum(
            live.reserved_usd if live.spent_usd is None else live.spent_usd
            for live in rows.live_runs
            if live.started_at >= month
        ),
    }


# --- Comparing ----------------------------------------------------------------------------------


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool)


def differences(reference: object, live: object, path: str = "") -> list[str]:
    """Where two documents differ, as one line per field. Numbers within TOLERANCE are equal,
    timestamps are compared as instants, and `generated_at` is skipped (the reference is worked
    out at the live document's time)."""
    if isinstance(reference, dict) and isinstance(live, dict):
        found: list[str] = []
        for key in sorted(set(reference) | set(live)):
            where = f"{path}.{key}"
            if key == "generated_at":
                continue
            if key not in live:
                found.append(f"{where}: only in the reference")
            elif key not in reference:
                found.append(f"{where}: only in the live function")
            else:
                found += differences(reference[key], live[key], where)
        return found
    if isinstance(reference, list) and isinstance(live, list):
        found = []
        if len(reference) != len(live):
            found.append(f"{path}: {len(reference)} entries in the reference, {len(live)} live")
        for index, (expected, actual) in enumerate(zip(reference, live, strict=False)):
            found += differences(expected, actual, f"{path}[{index}]")
        return found
    mismatch = [f"{path}: reference {reference!r}, live {live!r}"]
    if _is_number(reference) and _is_number(live):
        return [] if abs(reference - live) <= TOLERANCE else mismatch
    if isinstance(reference, str) and isinstance(live, str) and path.endswith(TIMESTAMPS):
        same = datetime.fromisoformat(reference) == datetime.fromisoformat(live)
        return [] if same else mismatch
    return [] if reference == live else mismatch


def live_stats(rest: RestClient, filters: StatsFilters) -> Json:
    """agent_stats() as the publishable key gets it, before /api/stats's models read it, so a
    field they do not name yet still shows up in the comparison."""
    reply = rest.send(
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
    return parse(TypeAdapter(Json), reply, "calling agent_stats()")


def describe(filters: StatsFilters) -> str:
    chosen = filters.model_dump(exclude_none=True)
    return json.dumps(chosen) if chosen else "all runs"


def compare(rows: Rows, rest: RestClient, filter_sets: Iterable[StatsFilters]) -> int:
    """Print SAME or DIFFERENT for each filter set, with what differs; return how many differ."""
    failures = 0
    for filters in filter_sets:
        live = live_stats(rest, filters)
        generated = live.get("generated_at")
        if not isinstance(generated, str):
            raise StoreError("agent_stats() returned no generated_at")
        now = datetime.fromisoformat(generated)
        found = differences(reference_stats(rows, filters, now), live)
        try:
            AgentStats.model_validate(live)
        except ValidationError as error:
            first = error.errors()[0]
            found.append(f"/api/stats would refuse this reply: {first['loc']} {first['msg']}")
        _, picked = select_runs(rows, filters, now)
        print(
            f"{'SAME' if not found else 'DIFFERENT':<10} {describe(filters)} ({len(picked)} runs)"
        )
        for line in found[:20]:
            print(f"    {line}")
        if len(found) > 20:
            print(f"    and {len(found) - 20} more")
        failures += bool(found)
    return failures


def _setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise StoreError(f"{name} must be set (see .env.example)")
    return value


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
    parser = argparse.ArgumentParser(
        prog="python -m dev.check_stats",
        description="Compare the live agent_stats() with a Python version of it (read-only).",
    )
    parser.parse_args(argv)
    load_dotenv(".env")
    try:
        url = _setting("SUPABASE_URL")
        with RestClient(url, _setting("SUPABASE_SECRET_KEY")) as secret:
            rows = read_rows(secret)
        with RestClient(url, _setting("SUPABASE_PUBLISHABLE_KEY")) as publishable:
            failures = compare(rows, publishable, FILTER_SETS)
    except StoreError as error:
        print(f"Could not check the statistics: {error}", file=sys.stderr)
        return 2
    total = len(FILTER_SETS)
    print(f"{total - failures} of {total} filter sets match.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
