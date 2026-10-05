"""Pydantic models for what the agent produces, checks and records.

These are the shapes stored in Supabase from Session 4, so they validate strictly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent.llm import Usage

Difficulty = Literal["easy", "medium", "hard"]
Mode = Literal["learn", "quiz"]
LayerVerdict = Literal["pass", "borderline", "fail", "error"]
Status = Literal["published", "review", "discarded"]


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
    """A QUIZ-mode item: one question, four options, one correct, plus the explanation."""

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

    @property
    def distractors(self) -> tuple[str, ...]:
        return tuple(o for i, o in enumerate(self.options) if i != self.correct_index)


Answer = Explanation | QuizItem


# --- Layer 1: code checks ---------------------------------------------------------------------


class CitationCheck(BaseModel):
    """Citations sorted by the two code-enforced rules: fetched in this run, quoted verbatim."""

    model_config = ConfigDict(frozen=True)

    kept: tuple[Citation, ...]
    unfetched: tuple[Citation, ...] = ()
    misquoted: tuple[Citation, ...] = ()

    @property
    def passed(self) -> bool:
        return len(self.kept) > 0


class CodeCheck(BaseModel):
    """Layer 1 of the publish gate: deterministic checks, no model involved."""

    model_config = ConfigDict(frozen=True)

    citations: CitationCheck
    unsupported_numbers: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.citations.passed and not self.unsupported_numbers

    @property
    def problems(self) -> tuple[str, ...]:
        return self.describe()

    def describe(self, *, show_unread_urls: bool = True) -> tuple[str, ...]:
        """The problems in words. Pass `show_unread_urls=False` for anything a player could
        see: a URL that was not read in the run may never be shown as a source."""
        found: list[str] = []
        if show_unread_urls:
            found += [
                f"cited URL was not read in this run: {c.url}" for c in self.citations.unfetched
            ]
        elif self.citations.unfetched:
            found.append(
                f"{len(self.citations.unfetched)} cited URL(s) not read in this run, dropped"
            )
        found += [
            f"quote is not word for word on {c.url}: {c.quote!r}" for c in self.citations.misquoted
        ]
        found += [f"number not found in the cited pages: {n}" for n in self.unsupported_numbers]
        if not self.citations.passed and not found:
            found.append("no valid citations")
        return tuple(found)


# --- Layer 2: Haiku verifier ------------------------------------------------------------------

SupportVerdict = Literal["supported", "contradicted", "not_found"]
DistractorVerdict = Literal["wrong", "also_correct", "unclear"]


class DistractorJudgement(BaseModel):
    model_config = ConfigDict(frozen=True)

    option: str
    verdict: DistractorVerdict
    reason: str


class HaikuReport(BaseModel):
    """Layer 2: a separate Haiku pass that must quote the passage supporting the answer."""

    model_config = ConfigDict(frozen=True)

    verdict: LayerVerdict
    reasons: tuple[str, ...] = ()
    answer_verdict: SupportVerdict | None = None
    answer_quote: str = ""
    answer_quote_verbatim: bool = False
    distractors: tuple[DistractorJudgement, ...] = ()
    explanation_problems: tuple[str, ...] = ()
    usage: Usage = Usage()
    cost_usd: float = 0.0
    seconds: float = 0.0


# --- Layer 3: Jev second opinion --------------------------------------------------------------

ClaimKind = Literal["correct_answer", "distractor", "sentence"]
JevVerdict = Literal["supports", "contradicts", "says_nothing"]


class JevCheck(BaseModel):
    """One claim checked by Jev against the cited pages, with its full probability spread."""

    model_config = ConfigDict(frozen=True)

    kind: ClaimKind
    claim: str
    verdict: JevVerdict
    confidence: float
    probabilities: dict[str, float]


class JevReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: LayerVerdict
    reasons: tuple[str, ...] = ()
    model: str = ""
    # Which criteria wording Jev answered against (agent/verifiers/jev.py). Records saved before
    # the wording was versioned used the first one.
    criteria: str = "generic-1"
    threshold: float = 0.8
    checks: tuple[JevCheck, ...] = ()
    input_tokens: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0


class Verification(BaseModel):
    """All three layers for one item. The publish decision is made from this in agent/gate.py."""

    model_config = ConfigDict(frozen=True)

    code: CodeCheck
    haiku: HaikuReport | None = None
    jev: JevReport | None = None


# --- Runs -------------------------------------------------------------------------------------

Outcome = Literal[
    "passed",  # answer submitted and the layer 1 code checks passed
    "failed_checks",  # answer submitted but failed the code checks after one correction
    "no_answer",  # the model kept replying without calling the submit tool
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
    # A tool call's arguments as the model sent them (the live log shows the query or URL).
    arguments: dict[str, object] | None = None
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
    answer: Answer | None = None
    code_check: CodeCheck | None = None
    # Text of each cited page exactly as the model read it, for the verifiers and storage.
    cited_pages: dict[str, str] = Field(default_factory=dict)
    fetched_urls: tuple[str, ...] = ()
    pages_read: tuple[str, ...] = ()  # one URL per page or record read; a redirect counts once
    steps: tuple[Step, ...] = ()
    model_calls: int = 0
    nudges: int = 0  # nudge messages sent: the model replied without a tool call
    usage: Usage = Usage()
    cost_usd: float = 0.0
    seconds: float = 0.0


class ItemRecord(BaseModel):
    """A run with its verification and publish status: what the CLI saves and the eval scores."""

    model_config = ConfigDict(frozen=True)

    run: RunResult
    verification: Verification | None = None
    status: Status | None = None
    rule: str | None = None

    @property
    def anthropic_cost_usd(self) -> float:
        haiku = self.verification.haiku if self.verification else None
        return self.run.cost_usd + (haiku.cost_usd if haiku else 0.0)

    @property
    def typesafe_cost_usd(self) -> float:
        jev = self.verification.jev if self.verification else None
        return jev.cost_usd if jev else 0.0
