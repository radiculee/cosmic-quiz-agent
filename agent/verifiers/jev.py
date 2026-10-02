"""Layer 3: TypeSafe Jev as an independent second opinion, one request per item.

Each claim (the correct answer, each distractor, each explanation sentence) becomes one Choice
question over the full text of the cited pages: does the source support it, contradict it, or say
nothing about it? Jev answers with probabilities, which are stored so the layer verdict can be
recomputed at any threshold (see `agent/gate.py`). Jev cannot check arithmetic or numbers
reliably, which is why layer 1 checks numbers in code.
"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, ConfigDict, ValidationError
from typesafe_sdk import Choice, ChoiceAnswer, TypeSafeClient, TypeSafeError

from agent.config import Settings
from agent.gate import jev_verdict
from agent.llm import JsonObject
from agent.schemas import Answer, ClaimKind, JevCheck, JevReport, JevVerdict, QuizItem

CRITERIA: dict[str, str] = {
    "supports": "The sources state the claim or directly imply it, including any numbers in it.",
    "contradicts": "The sources state something that conflicts with the claim.",
    "says_nothing": "The sources do not address the claim.",
}
_INSTRUCTIONS = "How do the sources relate to this claim? Claim: {claim}"
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_MIN_SENTENCE_CHARS = 20


class JevError(Exception):
    """A Jev request failed."""


class ClaimAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: JevVerdict
    confidence: float
    probabilities: dict[str, float]


class ClaimResults(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    input_tokens: int
    answers: dict[str, ClaimAnswer]


class JevClient(Protocol):
    def check_claims(self, state: JsonObject, claims: Mapping[str, str]) -> ClaimResults: ...


class TypeSafeJev:
    """Jev via the official `typesafe-sdk`, which reads TYPESAFE_API_KEY from the environment."""

    def __init__(self, model: str, timeout_seconds: float) -> None:
        self._client = TypeSafeClient(model=model, timeout=timeout_seconds)

    def check_claims(self, state: JsonObject, claims: Mapping[str, str]) -> ClaimResults:
        questions = {
            key: Choice(instructions=_INSTRUCTIONS.format(claim=claim), criteria=CRITERIA)
            for key, claim in claims.items()
        }
        try:
            response = self._client.system_one(state=state, questions=questions)
        except TypeSafeError as error:
            raise JevError(f"{type(error).__name__}: {error}") from error

        answers: dict[str, ClaimAnswer] = {}
        for key in claims:
            answer = response.answers[key]
            if not isinstance(answer, ChoiceAnswer):
                raise JevError(f"expected a choice answer for {key}, got {type(answer).__name__}")
            probabilities = {str(k): float(v) for k, v in dict(answer.probabilities or {}).items()}
            try:
                parsed = ClaimAnswer.model_validate(
                    {
                        "verdict": str(answer.choice),
                        "confidence": float(answer.confidence),
                        "probabilities": probabilities,
                    }
                )
            except ValidationError as error:
                raise JevError(f"unexpected Jev answer for {key}: {error}") from error
            answers[key] = parsed
        return ClaimResults(
            model=str(response.model),
            input_tokens=response.usage.input_tokens or 0,
            answers=answers,
        )


def split_sentences(text: str) -> list[str]:
    sentences = (s.strip() for s in _SENTENCE_END.split(" ".join(text.split())))
    return [s for s in sentences if len(s) >= _MIN_SENTENCE_CHARS]


def build_claims(answer: Answer) -> dict[str, tuple[ClaimKind, str]]:
    """Claims to check, keyed for the Jev request: the answer, each distractor, each sentence."""
    claims: dict[str, tuple[ClaimKind, str]] = {}
    if isinstance(answer, QuizItem):
        question = answer.question
        claims["correct_answer"] = (
            "correct_answer",
            f'The answer to the question "{question}" is: {answer.correct_option}',
        )
        for i, option in enumerate(answer.distractors):
            claims[f"distractor_{i}"] = (
                "distractor",
                f'The answer to the question "{question}" is: {option}',
            )
    for i, sentence in enumerate(split_sentences(answer.explanation)):
        claims[f"sentence_{i}"] = ("sentence", sentence)
    return claims


def verify_with_jev(
    answer: Answer, pages: Mapping[str, str], jev: JevClient, settings: Settings
) -> JevReport:
    started = time.monotonic()
    claims = build_claims(answer)
    state: JsonObject = {"sources": [{"url": url, "text": text} for url, text in pages.items()]}
    try:
        results = jev.check_claims(state, {key: claim for key, (_, claim) in claims.items()})
    except JevError as error:
        return JevReport(
            verdict="error",
            reasons=(str(error),),
            model=settings.jev_model,
            threshold=settings.jev_threshold,
            seconds=round(time.monotonic() - started, 2),
        )

    checks = tuple(
        JevCheck(
            kind=kind,
            claim=claim,
            verdict=results.answers[key].verdict,
            confidence=results.answers[key].confidence,
            probabilities=results.answers[key].probabilities,
        )
        for key, (kind, claim) in claims.items()
    )
    verdict, reasons = jev_verdict(checks, settings.jev_threshold)
    return JevReport(
        verdict=verdict,
        reasons=reasons,
        model=results.model,
        threshold=settings.jev_threshold,
        checks=checks,
        input_tokens=results.input_tokens,
        cost_usd=results.input_tokens * settings.jev_input_per_mtok / 1_000_000,
        seconds=round(time.monotonic() - started, 2),
    )
