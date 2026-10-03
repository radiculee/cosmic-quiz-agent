"""Layer 2: a separate Haiku pass, with its own prompt, that checks an answer against its sources.

The verifier must quote the passage that supports the correct answer; the quote is then checked
against the page in code, so support the verifier cannot show sends the item to review. The layer
verdict is derived in `agent/gate.py` from the structured report, not taken from the model.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, ValidationError

from agent.config import Settings
from agent.gate import haiku_verdict
from agent.llm import JsonObject, LLMError, LLMProvider, prompt_tokens_bound
from agent.schemas import (
    Answer,
    DistractorJudgement,
    DistractorVerdict,
    HaikuReport,
    QuizItem,
    SupportVerdict,
)
from agent.verify import normalize_text, quote_on_page

SYSTEM_PROMPT = """\
You are a strict fact-checker for an astronomy quiz. You judge an item only against the sources \
given to you, never against your own knowledge. You are not the author of the item: assume \
nothing in it is right until a source shows it.
"""

_QUIZ_INSTRUCTIONS = """\
Check the quiz item against the sources:
1. answer: is the marked correct option supported by the sources? Give "supported", \
"contradicted" or "not_found", and copy, character for character, one continuous sentence or \
less from a source that supports it (an empty quote if none), with that source's URL.
2. distractors: for each of the three other options, give "wrong" if the sources show it is \
not the answer, "also_correct" if the sources support it as an answer too, or "unclear" if the \
sources do not settle it, with a one-sentence reason.
3. explanation_problems: list each statement in the explanation that the sources contradict or \
do not support, including any number that differs from the sources. List problems only: never \
list a statement to say it is supported, and do not flag different names or spellings that \
clearly refer to the same thing. An empty list if there are no problems.
"""

_LEARN_INSTRUCTIONS = """\
Check the explanation against the sources. explanation_problems: list each statement that the \
sources contradict or do not support, including any number that differs from the sources. List \
problems only: never list a statement to say it is supported, and do not flag different names or \
spellings that clearly refer to the same thing. An empty list if there are no problems.
"""

_PROBLEMS_SCHEMA: JsonObject = {"type": "array", "items": {"type": "string"}}

QUIZ_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["supported", "contradicted", "not_found"]},
                "quote": {"type": "string"},
                "source_url": {"type": "string"},
            },
            "required": ["verdict", "quote", "source_url"],
            "additionalProperties": False,
        },
        "distractors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "option": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["wrong", "also_correct", "unclear"]},
                    "reason": {"type": "string"},
                },
                "required": ["option", "verdict", "reason"],
                "additionalProperties": False,
            },
        },
        "explanation_problems": _PROBLEMS_SCHEMA,
    },
    "required": ["answer", "distractors", "explanation_problems"],
    "additionalProperties": False,
}

LEARN_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {"explanation_problems": _PROBLEMS_SCHEMA},
    "required": ["explanation_problems"],
    "additionalProperties": False,
}


class _AnswerJudgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: SupportVerdict
    quote: str
    source_url: str


class _DistractorReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option: str
    verdict: DistractorVerdict
    reason: str


class _QuizReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: _AnswerJudgement
    distractors: list[_DistractorReply]
    explanation_problems: list[str]


class _LearnReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation_problems: list[str]


def _sources_block(pages: Mapping[str, str]) -> str:
    return "\n\n".join(f'<source url="{url}">\n{text}\n</source>' for url, text in pages.items())


def build_prompt(answer: Answer, pages: Mapping[str, str]) -> str:
    sources = _sources_block(pages)
    if isinstance(answer, QuizItem):
        options = "\n".join(
            f"{'ABCD'[i]}. {option}{'  <- marked correct' if i == answer.correct_index else ''}"
            for i, option in enumerate(answer.options)
        )
        item = f"Question: {answer.question}\n{options}\n\nExplanation: {answer.explanation}"
        return f"{sources}\n\n<item>\n{item}\n</item>\n\n{_QUIZ_INSTRUCTIONS}"
    return (
        f"{sources}\n\n<explanation>\n{answer.explanation}\n</explanation>\n\n{_LEARN_INSTRUCTIONS}"
    )


def _match_distractors(
    item: QuizItem, replies: list[_DistractorReply]
) -> tuple[DistractorJudgement, ...]:
    """Pair each real distractor with the verifier's judgement of it (by text, else by order)."""
    by_text = {normalize_text(reply.option): reply for reply in replies}
    judged: list[DistractorJudgement] = []
    for position, option in enumerate(item.distractors):
        reply = by_text.get(normalize_text(option))
        if reply is None and position < len(replies):
            reply = replies[position]
        if reply is None:
            judged.append(
                DistractorJudgement(option=option, verdict="unclear", reason="not judged")
            )
        else:
            judged.append(
                DistractorJudgement(option=option, verdict=reply.verdict, reason=reply.reason)
            )
    return tuple(judged)


def _prompt_tokens(llm: LLMProvider, prompt: str, schema: JsonObject) -> int:
    """The verifier prompt's size: exact from the free token counter, or the byte bound (which
    is about four times larger for English) if the counter cannot be reached."""
    try:
        return llm.count_json_tokens(SYSTEM_PROMPT, prompt, schema)
    except LLMError:
        return prompt_tokens_bound(SYSTEM_PROMPT, prompt, json.dumps(schema))


def _judge(
    answer: Answer, pages: Mapping[str, str], data: JsonObject, report: HaikuReport
) -> HaikuReport:
    """Fill a report from the verifier's reply. Raises ValidationError on a malformed reply."""
    if isinstance(answer, QuizItem):
        reply = _QuizReply.model_validate(data)
        page = pages.get(reply.answer.source_url, "")
        quote = reply.answer.quote
        return report.model_copy(
            update={
                "answer_verdict": reply.answer.verdict,
                "answer_quote": quote,
                # The verifier's own quote must be on the page it names, or on any cited page.
                "answer_quote_verbatim": bool(quote.strip())
                and (
                    quote_on_page(quote, page)
                    or any(quote_on_page(quote, t) for t in pages.values())
                ),
                "distractors": _match_distractors(answer, reply.distractors),
                "explanation_problems": tuple(reply.explanation_problems),
            }
        )
    learn_reply = _LearnReply.model_validate(data)
    return report.model_copy(
        update={"explanation_problems": tuple(learn_reply.explanation_problems)}
    )


def verify_with_haiku(
    answer: Answer, pages: Mapping[str, str], llm: LLMProvider, settings: Settings
) -> HaikuReport:
    """Layer 2 for one answer. Never loses the cost of a call that was made: every report after
    the call carries its usage, whatever went wrong."""
    started = time.monotonic()
    is_quiz = isinstance(answer, QuizItem)
    prompt = build_prompt(answer, pages)
    schema = QUIZ_SCHEMA if is_quiz else LEARN_SCHEMA
    bound = settings.price.max_call_cost_usd(
        _prompt_tokens(llm, prompt, schema), settings.verifier_max_output_tokens
    )
    if bound > settings.max_verifier_cost_usd:
        limit = settings.max_verifier_cost_usd
        reason = f"verifier skipped: the call could cost up to ${bound:.4f}, over ${limit:.2f}"
        return HaikuReport(verdict="error", reasons=(reason,))
    try:
        data, usage = llm.complete_json(
            SYSTEM_PROMPT, prompt, schema, settings.verifier_max_output_tokens
        )
    except LLMError as error:  # may have been billed, e.g. a reply cut off at the output limit
        return HaikuReport(
            verdict="error",
            reasons=(str(error),),
            usage=error.usage,
            cost_usd=error.usage.cost_usd(settings.price),
            seconds=round(time.monotonic() - started, 2),
        )

    paid = HaikuReport(
        verdict="pass",
        usage=usage,
        cost_usd=usage.cost_usd(settings.price),
        seconds=round(time.monotonic() - started, 2),
    )
    try:
        report = _judge(answer, pages, data, paid)
    except ValidationError as error:
        return paid.model_copy(
            update={
                "verdict": "error",
                "reasons": (f"verifier reply did not match the schema: {error}",),
            }
        )
    except Exception as error:  # a bug after a paid call: keep the cost, send the item to review
        return paid.model_copy(
            update={"verdict": "error", "reasons": (f"verifier crashed: {error!r}",)}
        )
    verdict, reasons = haiku_verdict(report, is_quiz=is_quiz)
    return report.model_copy(update={"verdict": verdict, "reasons": reasons})


__all__ = ["LEARN_SCHEMA", "QUIZ_SCHEMA", "build_prompt", "verify_with_haiku"]
