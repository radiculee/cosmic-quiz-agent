"""Pydantic models for what the agent produces.

`QuizItem` and `Run` arrive in later sessions; the spike only needs LEARN explanations.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Difficulty = Literal["easy", "medium", "hard"]


class Citation(BaseModel):
    """A source the model cites, with a short passage it says supports the explanation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class Explanation(BaseModel):
    """A LEARN-mode answer: a plain-language explanation backed by citations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    explanation: str = Field(min_length=1)
    citations: tuple[Citation, ...] = Field(min_length=1)
