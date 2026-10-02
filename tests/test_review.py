"""The review queue: what the reviewer sees and how decisions are applied. No network."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx2

from agent.store import ReviewDecision, ReviewItem
from curator.review import format_item, review
from tests.test_store import store_with

QUIZ_ROW: dict[str, Any] = {
    "id": 6,
    "mode": "quiz",
    "difficulty": "easy",
    "question": "How long is the solar cycle?",
    "options": ["About 11 years", "About 22 years", "About 3 years", "About 100 years"],
    "correct_index": 0,
    "explanation": "The Sun's activity rises and falls over about 11 years.",
    "code_problems": [],
    "haiku_reasons": ["distractor not settled by sources: About 22 years"],
    "jev_reasons": [],
    "jev_criteria": "astro-1",
    "jev_threshold": 0.8,
    "created_at": "2026-10-02T12:40:06+00:00",
    "topics": {"name": "The Sun and solar flares", "kind": "evergreen"},
    "sources": [
        {
            "ordinal": 0,
            "url": "https://en.wikipedia.org/wiki/Solar_flare",
            "quote": "The occurrence of solar flares varies with the 11-year solar cycle.",
        }
    ],
    "claim_checks": [
        {
            "kind": "correct_answer",
            "claim": 'The answer to the question "How long?" is: About 11 years',
            "verdict": "supports",
            "confidence": 0.99,
        },
        {
            "kind": "distractor",
            "claim": 'The answer to the question "How long?" is: About 22 years',
            "verdict": "contradicts",
            "confidence": 0.71,
        },
        {"kind": "sentence", "claim": "x", "verdict": "supports", "confidence": 0.93},
        {"kind": "sentence", "claim": "y", "verdict": "says_nothing", "confidence": 0.6},
    ],
}


def quiz_item(item_id: int = 6) -> ReviewItem:
    return ReviewItem.model_validate({**QUIZ_ROW, "id": item_id})


class QueueStore:
    def __init__(self, stale: set[int] | None = None) -> None:
        self.decisions: list[tuple[int, ReviewDecision]] = []
        self.stale = stale or set()

    def review_queue(self) -> list[ReviewItem]:
        return [quiz_item()]

    def decide_review(self, item_id: int, decision: ReviewDecision) -> bool:
        if item_id in self.stale:
            return False
        self.decisions.append((item_id, decision))
        return True


def scripted(*answers: str) -> Iterator[str]:
    yield from answers


def test_quiz_item_shows_reasons_answer_sources_and_jev() -> None:
    text = format_item(quiz_item(), 1, 3)

    assert "[1/3] item 6  QUIZ easy  The Sun and solar flares (evergreen, added 2026-10-02)" in text
    assert "- Haiku: distractor not settled by sources: About 22 years" in text
    assert "A. About 11 years   <- marked correct" in text
    assert "1. https://en.wikipedia.org/wiki/Solar_flare" in text
    assert '"The occurrence of solar flares varies with the 11-year solar cycle."' in text
    assert "Jev source check (astro-1, threshold 0.8):" in text
    assert "distractor contradicts  0.71  About 22 years" in text
    assert "explanation: 1 of 2 sentences supported (lowest confidence 0.60)" in text


def test_learn_item_has_no_question_block() -> None:
    learn = quiz_item().model_copy(update={"mode": "learn", "question": None, "options": None})

    text = format_item(learn, 1, 1)

    assert "Question:" not in text and "LEARN easy" in text


def test_review_applies_decisions_and_reprompts_on_bad_input() -> None:
    store = QueueStore()
    answers = scripted("x", "p", "d", "s")
    said: list[str] = []

    tally = review(
        store, [quiz_item(1), quiz_item(2), quiz_item(3)], lambda _p: next(answers), said.append
    )

    assert store.decisions == [(1, "published"), (2, "discarded")]
    assert (tally.published, tally.discarded, tally.skipped) == (1, 1, 1)
    assert "Please answer p, d, s or q." in said


def test_review_stops_on_quit_or_end_of_input_and_reports_stale_items() -> None:
    store = QueueStore(stale={1})
    answers = scripted("p", "q")

    tally = review(store, [quiz_item(1), quiz_item(2)], lambda _p: next(answers), lambda _m: None)

    assert tally.changed_elsewhere == 1 and store.decisions == []

    def no_input(_prompt: str) -> str:
        raise EOFError

    assert review(store, [quiz_item(3)], no_input, lambda _m: None).published == 0


def test_supabase_review_queue_and_guarded_decision() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx2.Response(200, json=[QUIZ_ROW])
        return httpx2.Response(200, json=[{"id": 6}] if len(seen) == 2 else [])

    store = store_with(handler)
    items = store.review_queue()
    first = store.decide_review(6, "published")
    second = store.decide_review(6, "discarded")

    assert [item.id for item in items] == [6] and items[0].sources[0].ordinal == 0
    params = seen[0].url.params
    assert params["status"] == "eq.review" and params["claim_checks.layer"] == "eq.jev"
    patch = seen[1]
    assert patch.url.params["status"] == "eq.review"  # only while still in review
    assert json.loads(patch.content) == {"status": "published"}
    assert first is True and second is False
