from __future__ import annotations

import random
from typing import Any

import httpx2
import pytest

from agent.config import Settings
from agent.llm import LLMError, ToolResultsMessage
from agent.loop import MAX_NUDGES, length_ok, run_learn, run_quiz, shuffle_options
from agent.schemas import QuizItem
from tests.conftest import FakeLLM, FakeWeb, completion
from tests.test_tools import WIKI_API, wiki_extract

ARTICLE = "https://en.wikipedia.org/wiki/Neutron_star"
QUOTE = "A neutron star is the collapsed core of a massive star."
EASY_TEXT = " ".join(["word"] * 100)  # inside the easy range of 80 to 120 words


def submit(
    url: str = ARTICLE, quote: str = QUOTE, text: str = EASY_TEXT
) -> tuple[str, dict[str, Any]]:
    return (
        "submit_answer",
        {"explanation": text, "citations": [{"url": url, "quote": quote}]},
    )


FETCH = ("fetch_page", {"url": ARTICLE})


@pytest.fixture(autouse=True)
def wikipedia(web: FakeWeb) -> None:
    web.add(WIKI_API, wiki_extract)


def test_passing_run(settings: Settings, http: httpx2.Client) -> None:
    llm = FakeLLM([completion(FETCH), completion(submit())])
    steps: list[str] = []

    result = run_learn("Neutron stars", "easy", llm, settings, lambda s: steps.append(s.kind), http)

    assert result.outcome == "passed"
    assert result.answer is not None and result.answer.citations[0].url == ARTICLE
    assert result.code_check is not None and result.code_check.passed
    assert QUOTE in result.cited_pages[ARTICLE]
    assert steps == ["model", "tool", "model"]
    assert result.model_calls == 2
    # Two calls of 100 input and 10 output tokens at $1 and $5 per million.
    assert result.cost_usd == pytest.approx(0.0003)
    # The second model call saw the page text as a tool result.
    tool_results = llm.calls[1][-1]
    assert isinstance(tool_results, ToolResultsMessage)
    assert QUOTE in tool_results.results[0].content


def test_unfetched_citations_fail_after_one_correction(
    settings: Settings, http: httpx2.Client
) -> None:
    unread = submit(url="https://en.wikipedia.org/wiki/Pulsar")
    llm = FakeLLM([completion(unread), completion(unread)])

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "failed_checks"
    assert result.code_check is not None and len(result.code_check.citations.unfetched) == 1
    correction = llm.calls[1][-1]
    assert isinstance(correction, ToolResultsMessage)
    assert "not read in this run" in correction.results[0].content


def test_misquote_is_corrected(settings: Settings, http: httpx2.Client) -> None:
    misquoted = submit(quote="A neutron star is a collapsed stellar core.")
    llm = FakeLLM([completion(FETCH), completion(misquoted), completion(submit())])

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "passed"
    correction = llm.calls[2][-1]
    assert isinstance(correction, ToolResultsMessage)
    assert "not word for word" in correction.results[0].content


def test_unsupported_number_fails_after_one_correction(
    settings: Settings, http: httpx2.Client
) -> None:
    wrong_year = submit(text=EASY_TEXT + " It was first proposed in 1932.")
    llm = FakeLLM([completion(FETCH), completion(wrong_year), completion(wrong_year)])

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "failed_checks"
    assert "number not found in the cited pages: 1932" in result.detail


def test_misquoted_citation_is_dropped_when_another_is_valid(
    settings: Settings, http: httpx2.Client
) -> None:
    mixed = (
        "submit_answer",
        {
            "explanation": EASY_TEXT,
            "citations": [
                {"url": ARTICLE, "quote": QUOTE},
                {"url": ARTICLE, "quote": "Neutron stars are made of cheese."},
            ],
        },
    )
    llm = FakeLLM([completion(FETCH), completion(mixed), completion(mixed)])

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "passed"
    assert result.answer is not None and [c.quote for c in result.answer.citations] == [QUOTE]
    assert "not word for word" in result.detail


def test_invalid_answer_is_returned_to_the_model(settings: Settings, http: httpx2.Client) -> None:
    invalid = ("submit_answer", {"explanation": "No sources.", "citations": []})
    llm = FakeLLM([completion(FETCH), completion(invalid), completion(submit())])

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "passed"
    error_result = llm.calls[2][-1]
    assert isinstance(error_result, ToolResultsMessage) and error_result.results[0].is_error


def test_tool_errors_are_returned_to_the_model(settings: Settings, http: httpx2.Client) -> None:
    blocked = ("fetch_page", {"url": "https://example.com/stars"})
    llm = FakeLLM([completion(blocked), completion(FETCH), completion(submit())])

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "passed"
    first_result = llm.calls[1][-1]
    assert isinstance(first_result, ToolResultsMessage)
    assert first_result.results[0].is_error and "not allowed" in first_result.results[0].content
    assert [s.is_error for s in result.steps if s.kind == "tool"] == [True, False]


def test_model_that_never_submits_gets_nudged_then_stops(
    settings: Settings, http: httpx2.Client
) -> None:
    llm = FakeLLM([completion(text="Here is my answer.") for _ in range(MAX_NUDGES + 1)])

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "no_answer"
    assert result.model_calls == MAX_NUDGES + 1


def test_step_budget_stops_the_run(http: httpx2.Client) -> None:
    settings = Settings(max_steps=2, http_retry_backoff_seconds=0.0)
    llm = FakeLLM([completion(FETCH), completion(FETCH), completion(submit())])

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "budget_exceeded"
    assert "step budget" in result.detail
    assert result.model_calls == 2


def test_model_errors_end_the_run_with_the_cost_so_far(
    settings: Settings, http: httpx2.Client
) -> None:
    llm = FakeLLM([completion(FETCH), LLMError("RateLimitError: slow down")])

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "llm_error"
    assert "slow down" in result.detail
    assert result.cost_usd == pytest.approx(0.00015)


@pytest.mark.parametrize(
    ("words", "ok"),
    [(71, False), (72, True), (100, True), (132, True), (133, False)],
)
def test_easy_length_allows_ten_percent_either_side(words: int, ok: bool) -> None:
    assert length_ok(words, "easy") is ok


def test_wrong_length_gets_one_correction(settings: Settings, http: httpx2.Client) -> None:
    too_long = " ".join(["word"] * 152)
    llm = FakeLLM([completion(FETCH), completion(submit(text=too_long)), completion(submit())])

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "passed"
    assert result.detail == ""
    correction = llm.calls[2][-1]
    assert isinstance(correction, ToolResultsMessage)
    assert "152 words; easy needs 80 to 120" in correction.results[0].content


def test_second_wrong_length_is_accepted_with_a_note(
    settings: Settings, http: httpx2.Client
) -> None:
    too_long = " ".join(["word"] * 152)
    llm = FakeLLM(
        [completion(FETCH), completion(submit(text=too_long)), completion(submit(text=too_long))]
    )

    result = run_learn("Neutron stars", "easy", llm, settings, http_client=http)

    assert result.outcome == "passed"
    assert result.detail == "The explanation is 152 words; easy needs 80 to 120."
    assert result.model_calls == 3


def quiz_submission(correct_index: int = 0) -> tuple[str, dict[str, Any]]:
    options = ["A collapsed stellar core", "A young planet", "A comet", "A gas cloud"]
    return (
        "submit_quiz",
        {
            "question": "What is a neutron star?",
            "options": options,
            "correct_index": correct_index,
            "explanation": EASY_TEXT,
            "citations": [{"url": ARTICLE, "quote": QUOTE}],
        },
    )


def test_quiz_run_shuffles_options_and_keeps_the_answer(
    settings: Settings, http: httpx2.Client
) -> None:
    llm = FakeLLM([completion(FETCH), completion(quiz_submission())])

    result = run_quiz(
        "Neutron stars", "easy", llm, settings, http_client=http, rng=random.Random(3)
    )

    assert result.outcome == "passed" and result.mode == "quiz"
    assert isinstance(result.answer, QuizItem)
    assert result.answer.correct_option == "A collapsed stellar core"
    assert sorted(result.answer.options) == sorted(quiz_submission()[1]["options"])


def test_shuffle_spreads_the_correct_position() -> None:
    item = QuizItem.model_validate({k: v for k, v in quiz_submission()[1].items()})
    rng = random.Random(0)

    positions = {shuffle_options(item, rng).correct_index for _ in range(50)}

    assert positions == {0, 1, 2, 3}
