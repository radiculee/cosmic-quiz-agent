"""The read-only check of agent_stats() (dev/check_stats.py): its Python version of the function,
worked out by hand on a few rows, and the comparison. Nothing touches the network."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest

from agent.rest import RestClient
from agent.stats import StatsFilters
from dev.check_stats import (
    CheckRow,
    ItemRow,
    LiveRunRow,
    Rows,
    RunRow,
    compare,
    confidence_bin,
    differences,
    percentile,
    reference_stats,
)
from tests.test_stats import SAMPLE
from tests.test_store import BASE

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def step(kind: str, seconds: float, summary: str = "", **fields: object) -> dict[str, object]:
    return {"index": 0, "kind": kind, "summary": summary, "seconds": seconds, **fields}


def run_row(run_id: int, **fields: object) -> RunRow:
    row: dict[str, object] = {
        "id": run_id,
        "source": "curator",
        "mode": "learn",
        "difficulty": "easy",
        "model": "claude-haiku-4-5",
        "outcome": "passed",
        "budget_reason": None,
        "model_calls": 3,
        "nudges": 0,
        "input_tokens": 1000,
        "output_tokens": 100,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
        "agent_cost_usd": 0.02,
        "seconds": 10.0,
        "pages_by_domain": {"en.wikipedia.org": 2},
        "steps": [],
        "verifier_input_tokens": 500,
        "verifier_output_tokens": 50,
        "verifier_cost_usd": 0.005,
        "verifier_seconds": 2.0,
        "jev_input_tokens": 400,
        "jev_cost_usd": 0.0001,
        "jev_seconds": 0.3,
        "created_at": "2026-10-08T10:00:00+00:00",
        "gate_status": "published",
        "haiku": {"verdict": "pass"},
        "jev_verdict": "pass",
    }
    return RunRow.model_validate({**row, **fields})


def sample_rows() -> Rows:
    """Three runs: a published Curator explanation this week, a live question in review this
    week, and a Curator question last month that ran out of time."""
    return Rows(
        runs=[
            run_row(
                1,
                steps=[
                    step("model", 2.0, "search_wikipedia, fetch_page (stop: tool_use)"),
                    step("tool", 0.5, tool="search_wikipedia"),
                    step("tool", 1.0, tool="fetch_page", is_error=True),
                    step("model", 3.0, "submit_answer (stop: tool_use)"),
                    step("model", 1.0, "no tool calls (stop: end_turn)"),
                ],
            ),
            run_row(
                2,
                source="on_demand",
                mode="quiz",
                difficulty="medium",
                nudges=1,
                agent_cost_usd=0.03,
                seconds=20.0,
                pages_by_domain={"en.wikipedia.org": 1, "science.nasa.gov": 3},
                verifier_cost_usd=0.0,
                verifier_seconds=0.0,
                jev_cost_usd=0.0,
                jev_seconds=0.0,
                created_at="2026-10-09T08:00:00+00:00",
                gate_status="review",
                haiku={
                    "verdict": "borderline",
                    "distractors": [{"verdict": "wrong"}, {"verdict": "unclear"}],
                    "explanation_problems": [],
                },
                jev_verdict=None,  # Jev did not run
            ),
            run_row(
                3,
                mode="quiz",
                difficulty="hard",
                outcome="budget_exceeded",
                budget_reason="time budget of 120 s used",
                model_calls=6,
                agent_cost_usd=0.04,
                seconds=120.0,
                pages_by_domain={},
                verifier_cost_usd=0.0,
                verifier_seconds=0.0,
                jev_cost_usd=0.0,
                jev_seconds=0.0,
                created_at="2026-09-20T10:00:00+00:00",
                gate_status="discarded",
                haiku=None,
                jev_verdict=None,
            ),
        ],
        items=[
            ItemRow(id=11, run_id=1, status="published"),
            ItemRow(id=12, run_id=2, status="review"),
        ],
        checks=[
            CheckRow(item_id=11, layer="code", kind="citation", verdict="kept", confidence=None),
            CheckRow(
                item_id=11, layer="code", kind="citation", verdict="misquoted", confidence=None
            ),
            CheckRow(item_id=11, layer="jev", kind="sentence", verdict="supports", confidence=1.0),
            CheckRow(
                item_id=12, layer="jev", kind="distractor", verdict="contradicts", confidence=0.85
            ),
            CheckRow(
                item_id=12, layer="code", kind="number", verdict="unsupported", confidence=None
            ),
        ],
        live_runs=[
            LiveRunRow(
                started_at=datetime(2026, 10, 8, tzinfo=UTC), reserved_usd=0.17, spent_usd=0.03
            ),
            LiveRunRow(
                started_at=datetime(2026, 10, 9, tzinfo=UTC), reserved_usd=0.17, spent_usd=None
            ),
            LiveRunRow(
                started_at=datetime(2026, 9, 30, tzinfo=UTC), reserved_usd=0.17, spent_usd=0.05
            ),
        ],
    )


def test_percentiles_interpolate_as_postgres_does() -> None:
    assert percentile(0.5, [4.0, 1.0, 3.0, 2.0]) == 2.5
    assert percentile(0.95, [1.0, 2.0, 3.0, 4.0]) == pytest.approx(3.85)
    assert percentile(0.5, [7.0]) == 7.0
    assert percentile(0.5, []) is None


def test_confidence_bins_put_one_in_the_last_bin() -> None:
    assert [confidence_bin(value) for value in (0.0, 0.0999, 0.3, 0.7, 0.85, 1.0)] == [
        0,
        0,
        3,
        7,
        8,
        9,
    ]
    assert confidence_bin(-0.1) is None


def keys(document: object) -> object:
    """A document's field names, nested; a list stands for its first entry's."""
    if isinstance(document, dict):
        return {key: keys(value) for key, value in document.items()}
    if isinstance(document, list):
        return [keys(document[0])] if document else []
    return None


def test_the_reference_has_every_field_of_the_function_s_reply() -> None:
    # The last 7 days leave out the run that ran out of time, so `budgets` is empty as in SAMPLE.
    reference = reference_stats(sample_rows(), StatsFilters(days=7), NOW)

    assert keys(reference) == keys(SAMPLE)


def test_the_reference_counts_as_the_migration_says() -> None:
    doc: Any = json.loads(json.dumps(reference_stats(sample_rows(), StatsFilters(), NOW)))

    volume = doc["volume"]
    assert volume["runs"] == 3
    assert volume["outcomes"]["passed"] == 2 and volume["outcomes"]["budget_exceeded"] == 1
    assert volume["gate"] == {"published": 1, "review": 1, "discarded": 1}
    assert volume["cost"]["agent_usd"] == pytest.approx(0.09)
    assert doc["bank"] == {"published": 1, "review": 1, "discarded": 0, "retired": 0}

    speed = doc["speed"]
    assert speed["run_seconds"] == {"median": 20.0, "p95": pytest.approx(110.0)}
    assert speed["verifier_seconds"] == {"median": 2.0, "p95": 2.0}  # only runs that verified
    assert [(tool["tool"], tool["calls"], tool["errors"]) for tool in speed["tools"]] == [
        ("fetch_page", 1, 1),
        ("search_wikipedia", 1, 0),
    ]

    behaviour = doc["behaviour"]
    assert (behaviour["model_steps"], behaviour["tool_steps"], behaviour["parallel_steps"]) == (
        3,
        2,
        1,
    )
    assert behaviour["pages_by_domain"] == [
        {"domain": "en.wikipedia.org", "pages": 3},
        {"domain": "science.nasa.gov", "pages": 3},
    ]
    assert behaviour["budgets"] == [{"budget": "time", "runs": 1}]
    assert (behaviour["nudges"], behaviour["nudged_runs"]) == (1, 1)
    assert behaviour["citations"] == {"kept": 1, "misquoted": 1, "unfetched": 0}
    assert behaviour["unsupported_number_answers"] == 1

    verifiers = doc["verifiers"]
    assert verifiers["haiku"] == {"pass": 1, "borderline": 1, "fail": 0, "error": 0}
    assert verifiers["agreement"] == [{"haiku": "pass", "jev": "pass", "items": 1}]
    assert verifiers["jev_confidence"] == {"bins": [0] * 8 + [1, 1], "exactly_one": 1}
    assert verifiers["review"] == {
        "items": 1,
        "haiku_doubt": 1,
        "jev_doubt": 0,
        "verifier_error": 1,
        "explanation": 0,
        "unsettled_option": 1,
        "verifier_quote": 0,
    }

    assert [(cell["mode"], cell["difficulty"]) for cell in doc["grid"]] == [
        ("learn", "easy"),
        ("quiz", "medium"),
        ("quiz", "hard"),
    ]
    budget = doc["budget"]
    assert budget["month_start"] == "2026-10-01T00:00:00+00:00"
    assert budget["anthropic_usd"] == pytest.approx(0.055)  # October's runs only
    assert budget["live_usd"] == pytest.approx(0.20)  # a run still going counts its reservation


def test_the_filters_scope_everything_but_the_grid_and_the_month() -> None:
    rows = sample_rows()

    quiz: Any = reference_stats(rows, StatsFilters(mode="quiz"), NOW)
    week: Any = reference_stats(rows, StatsFilters(days=7), NOW)
    nothing: Any = reference_stats(rows, StatsFilters(source="on_demand", difficulty="hard"), NOW)

    assert quiz["volume"]["runs"] == 2 and len(quiz["grid"]) == 3
    assert week["volume"]["runs"] == 2 and len(week["grid"]) == 2
    assert nothing["volume"]["runs"] == 0
    assert nothing["speed"]["run_seconds"] == {"median": None, "p95": None}
    assert nothing["budget"]["live_usd"] == pytest.approx(0.20)


def test_differences_name_each_field_that_differs() -> None:
    reference = {
        "generated_at": "2026-10-09T12:00:00+00:00",
        "volume": {"runs": 3, "cost": 0.1, "first_run_at": "2026-10-08T10:00:00+00:00"},
        "grid": [1, 2],
    }
    live = {
        "generated_at": "2026-10-09T12:00:01+00:00",
        "volume": {
            "runs": 4,
            "cost": 0.1000000001,
            "first_run_at": "2026-10-08T11:00:00+01:00",
            "added": True,
        },
        "grid": [1],
    }

    assert differences(reference, live) == [
        ".grid: 2 entries in the reference, 1 live",
        ".volume.added: only in the live function",
        ".volume.runs: reference 3, live 4",
    ]


def test_compare_reports_a_function_that_counts_differently(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rows = sample_rows()

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        filters = StatsFilters(
            mode=body["p_mode"],
            difficulty=body["p_difficulty"],
            source=body["p_source"],
            days=body["p_days"],
        )
        document: Any = json.loads(json.dumps(reference_stats(rows, filters, NOW)))
        if filters.mode == "quiz":
            document["volume"]["runs"] = 99
            del document["volume"]["gate"]
        return httpx2.Response(200, json=document)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    rest = RestClient(BASE, "publishable", client=client, retry_backoff_seconds=0.0)

    failures = compare(rows, rest, [StatsFilters(), StatsFilters(mode="quiz")])

    assert failures == 1
    printed = capsys.readouterr().out
    assert "SAME       all runs (3 runs)" in printed
    assert 'DIFFERENT  {"mode": "quiz"} (2 runs)' in printed
    assert ".volume.runs: reference 2, live 99" in printed
    assert ".volume.gate: only in the reference" in printed
    assert "/api/stats would refuse this reply" in printed
