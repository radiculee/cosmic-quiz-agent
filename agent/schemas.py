"""Pydantic models for what the agent produces and records.

These are the shapes stored in Supabase from Session 4, so they validate strictly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent.llm import Usage

Difficulty = Literal["easy", "medium", "hard"]
Mode = Literal["learn", "quiz"]


class Citation(BaseModel):
    """A source the model cites, with a short passage it says supports the answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class Explanation(BaseModel):
    """A LEARN-mode answer: a plain-language explanation backed by citations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    explanation: str = Field(min_length=1)
    citations: tuple[Citation, ...] = Field(min_length=1)


class QuizItem(BaseModel):
    """A QUIZ-mode item: one question, four options, one correct, plus the explanation.

    Generation and verification arrive in Session 3; the shape is fixed now so storage and the
    UI can be designed against it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    question: str = Field(min_length=1)
    options: tuple[str, str, str, str]
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=1)
    citations: tuple[Citation, ...] = Field(min_length=1)

    @field_validator("options")
    @classmethod
    def _options_distinct(cls, options: tuple[str, str, str, str]) -> tuple[str, str, str, str]:
        cleaned = [option.strip() for option in options]
        if any(not option for option in cleaned):
            raise ValueError("options must not be empty")
        if len({option.casefold() for option in cleaned}) != len(cleaned):
            raise ValueError("options must be distinct")
        return (cleaned[0], cleaned[1], cleaned[2], cleaned[3])

    @model_validator(mode="after")
    def _question_is_not_an_option(self) -> QuizItem:
        if self.question.strip().casefold() in {o.casefold() for o in self.options}:
            raise ValueError("the question must not repeat an option")
        return self

    @property
    def correct_option(self) -> str:
        return self.options[self.correct_index]


class CitationCheck(BaseModel):
    """Which citations survived the fetched-URL rule, and how many quotes appear verbatim."""

    model_config = ConfigDict(frozen=True)

    kept: tuple[Citation, ...]
    dropped: tuple[Citation, ...]
    quotes_found: int

    @property
    def passed(self) -> bool:
        return len(self.kept) > 0


Outcome = Literal[
    "passed",  # answer submitted and at least one citation was fetched in this run
    "failed_citations",  # answer submitted but every citation was dropped
    "no_answer",  # the model kept replying without calling submit_answer
    "budget_exceeded",  # step, time or token budget ran out
    "llm_error",  # a model call failed after retries
]


class Step(BaseModel):
    """One entry in the run log: a model call or a tool call."""

    model_config = ConfigDict(frozen=True)

    index: int
    kind: Literal["model", "tool"]
    summary: str
    seconds: float
    tool: str | None = None
    usage: Usage | None = None
    is_error: bool = False


class RunResult(BaseModel):
    """Everything about one agent run: the answer, the checks, the log and the cost."""

    model_config = ConfigDict(frozen=True)

    mode: Mode
    topic: str
    difficulty: Difficulty
    model: str
    outcome: Outcome
    detail: str = ""
    answer: Explanation | None = None
    citation_check: CitationCheck | None = None
    fetched_urls: tuple[str, ...] = ()
    steps: tuple[Step, ...] = ()
    model_calls: int = 0
    usage: Usage = Usage()
    cost_usd: float = 0.0
    seconds: float = 0.0
