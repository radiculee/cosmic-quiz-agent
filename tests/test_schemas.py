from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from agent.schemas import Explanation, QuizItem

CITATION = {"url": "https://en.wikipedia.org/wiki/Mars", "quote": "Mars is the fourth planet."}


def quiz(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "question": "Which planet is fourth from the Sun?",
        "options": ["Venus", "Earth", "Mars", "Jupiter"],
        "correct_index": 2,
        "explanation": "Mars is the fourth planet from the Sun.",
        "citations": [CITATION],
    }
    data.update(overrides)
    return data


def test_valid_quiz_item() -> None:
    item = QuizItem.model_validate(quiz())
    assert item.correct_option == "Mars"


@pytest.mark.parametrize(
    "overrides",
    [
        {"options": ["Venus", "Earth", "Mars"]},  # only three
        {"options": ["Venus", "Earth", "Mars", "Jupiter", "Saturn"]},  # five
        {"options": ["Venus", "Earth", "Mars", "mars "]},  # duplicate after cleaning
        {"options": ["Venus", "Earth", "Mars", "  "]},  # empty option
        {"correct_index": 4},
        {"citations": []},
        {"question": "Mars"},  # the question repeats an option
        {"unexpected": "field"},
    ],
)
def test_invalid_quiz_items_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        QuizItem.model_validate(quiz(**overrides))


def test_explanation_needs_a_citation() -> None:
    with pytest.raises(ValidationError):
        Explanation.model_validate({"explanation": "Text.", "citations": []})
