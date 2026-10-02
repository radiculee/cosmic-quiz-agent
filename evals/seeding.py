"""The planted-error set: items that passed the eval, each with one deliberate fault.

Four fault types, ten items each (decided 2026-10-01):
- wrong_number (code): a number in the explanation changed to a value the sources do not give.
- fake_quote (code): the first citation's quote changed so it is no longer on the page.
- unsupported_claim (Haiku): a plausible sentence the sources do not state, added to the
  explanation. Written without digits, so the number check cannot catch it.
- true_distractor (Haiku): one wrong option rewritten so the sources support it too.

Every planted item should end up not published. The report measures which layers catch which
faults. A fixed random seed makes the code faults and the item selection reproducible.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from agent.config import Settings
from agent.llm import JsonObject, LLMError, LLMProvider
from agent.schemas import Citation, Difficulty, ItemRecord, QuizItem, Verification
from agent.verifiers.jev import split_sentences
from agent.verify import normalize_url, numbers_in

FaultType = Literal["wrong_number", "fake_quote", "unsupported_claim", "true_distractor"]
FAULT_TYPES: tuple[FaultType, ...] = (
    "wrong_number",
    "fake_quote",
    "unsupported_claim",
    "true_distractor",
)
PER_FAULT = 10
SEED = 20261001

_LINKING_VERB = re.compile(r"\b(is|are|was|were)\b")
_LONG_WORD = re.compile(r"\b[a-z]{6,}\b")


class SeededItem(BaseModel):
    """One planted fault: the changed item, what changed, and the pages it cites."""

    model_config = ConfigDict(frozen=True)

    id: str
    fault: FaultType
    description: str
    topic: str
    difficulty: Difficulty
    item: QuizItem
    pages: dict[str, str]

    @property
    def fetched(self) -> dict[str, str]:
        """The pages keyed the way layer 1 expects: by normalized URL."""
        return {normalize_url(url): text for url, text in self.pages.items()}


class SeededResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    seeded: SeededItem
    verification: Verification
    anthropic_cost_usd: float = 0.0
    typesafe_cost_usd: float = 0.0


# --- Code faults --------------------------------------------------------------------------------


def _format_like(original: str, value: float) -> str:
    decimals = len(original.split(".")[1]) if "." in original else 0
    text = f"{value:,.{decimals}f}" if "," in original else f"{value:.{decimals}f}"
    return text


def plant_wrong_number(
    item: QuizItem, pages: Mapping[str, str], rng: random.Random
) -> tuple[QuizItem, str] | None:
    """Change one sourced number in the explanation to a value no cited page contains."""
    page_numbers = {n for text in pages.values() for n in numbers_in(text)}
    raw = re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", item.explanation)
    candidates = [
        r for r in raw if r.replace(",", "") in page_numbers and float(r.replace(",", "")) > 0
    ]
    if not candidates:
        return None
    original = rng.choice(candidates)
    value = float(original.replace(",", ""))
    for factor in (3.0, 7.0, 0.5, 11.0):
        replacement = _format_like(original, value * factor)
        if replacement.replace(",", "") not in page_numbers and replacement != original:
            explanation = item.explanation.replace(original, replacement, 1)
            changed = item.model_copy(update={"explanation": explanation})
            return changed, f"explanation number {original} changed to {replacement}"
    return None


def plant_fake_quote(item: QuizItem, rng: random.Random) -> tuple[QuizItem, str] | None:
    """Alter the first quote so it is no longer on its page: negate it, or swap a word."""
    first = item.citations[0]
    quote = first.quote
    if _LINKING_VERB.search(quote):
        altered = _LINKING_VERB.sub(lambda m: f"{m.group(1)} not", quote, count=1)
        how = "negated"
    else:
        words = _LONG_WORD.findall(quote)
        if not words:
            return None
        word = rng.choice(words)
        altered = re.sub(rf"\b{word}\b", "several", quote, count=1)
        how = f"'{word}' replaced"
    citations = (Citation(url=first.url, quote=altered), *item.citations[1:])
    return item.model_copy(update={"citations": citations}), f"first quote {how}: {altered!r}"


# --- Model-written faults -----------------------------------------------------------------------

_SEED_SYSTEM = (
    "You help test a fact-checking system for an astronomy quiz by writing deliberately flawed "
    "test cases. Follow the instructions exactly."
)

_CLAIM_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {"sentence": {"type": "string"}},
    "required": ["sentence"],
    "additionalProperties": False,
}
_OPTION_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {"option": {"type": "string"}},
    "required": ["option"],
    "additionalProperties": False,
}


def _sources(pages: Mapping[str, str]) -> str:
    return "\n\n".join(f'<source url="{u}">\n{t}\n</source>' for u, t in pages.items())


def plant_unsupported_claim(
    item: QuizItem, pages: Mapping[str, str], llm: LLMProvider, settings: Settings
) -> tuple[QuizItem, str, float] | None:
    prompt = (
        f"{_sources(pages)}\n\nQuiz question: {item.question}\n\n"
        "Write one sentence about this topic that sounds plausible and fits naturally into an "
        "explanation for a beginner, but that the sources above do NOT state anywhere. It must "
        "not be a paraphrase of anything in the sources. Use no digits and at most 25 words."
    )
    try:
        data, usage = llm.complete_json(_SEED_SYSTEM, prompt, _CLAIM_SCHEMA, 300)
    except LLMError:
        return None
    sentence = str(data.get("sentence", "")).strip()
    cost = usage.cost_usd(settings.price)
    if not sentence or re.search(r"\d", sentence):
        return None
    sentences = split_sentences(item.explanation)
    if sentences:
        first = sentences[0]
        explanation = item.explanation.replace(first, f"{first} {sentence}", 1)
    else:
        explanation = f"{sentence} {item.explanation}"
    changed = item.model_copy(update={"explanation": explanation})
    return changed, f"added unsupported sentence: {sentence!r}", cost


def plant_true_distractor(
    item: QuizItem,
    pages: Mapping[str, str],
    llm: LLMProvider,
    settings: Settings,
    rng: random.Random,
) -> tuple[QuizItem, str, float] | None:
    prompt = (
        f"{_sources(pages)}\n\nQuiz question: {item.question}\n"
        f"Correct answer: {item.correct_option}\n\n"
        "Write a different answer option that the sources above ALSO show to be correct for "
        "this question, worded differently from the correct answer and similar in length. It "
        "must be true according to the sources."
    )
    try:
        data, usage = llm.complete_json(_SEED_SYSTEM, prompt, _OPTION_SCHEMA, 200)
    except LLMError:
        return None
    option = str(data.get("option", "")).strip()
    cost = usage.cost_usd(settings.price)
    wrong = [i for i in range(len(item.options)) if i != item.correct_index]
    index = rng.choice(wrong)
    options = list(item.options)
    replaced = options[index]
    options[index] = option
    try:
        changed = QuizItem.model_validate({**item.model_dump(), "options": options})
    except ValidationError:
        return None
    return changed, f"distractor {replaced!r} replaced by true option {option!r}", cost


# --- Building the set ---------------------------------------------------------------------------


def eligible(records: Iterable[ItemRecord]) -> list[ItemRecord]:
    """Items that passed layer 1: the faults are planted into otherwise valid items."""
    return [
        r
        for r in records
        if isinstance(r.run.answer, QuizItem) and r.run.code_check and r.run.code_check.passed
    ]


def build_seeded_set(
    records: Iterable[ItemRecord],
    llm: LLMProvider,
    settings: Settings,
    on_item: Callable[[SeededItem], None] | None = None,
) -> tuple[list[SeededItem], float]:
    """Plant PER_FAULT faults of each type. Returns the items and the Anthropic cost of writing
    the model-planted ones."""
    rng = random.Random(SEED)
    pool = eligible(records)
    seeded: list[SeededItem] = []
    cost = 0.0
    for fault in FAULT_TYPES:
        candidates = pool[:]
        rng.shuffle(candidates)
        made = 0
        for record in candidates:
            if made == PER_FAULT:
                break
            item = record.run.answer
            assert isinstance(item, QuizItem)  # guaranteed by eligible()
            pages = record.run.cited_pages
            planted: tuple[QuizItem, str] | None = None
            if fault == "wrong_number":
                planted = plant_wrong_number(item, pages, rng)
            elif fault == "fake_quote":
                planted = plant_fake_quote(item, rng)
            else:
                written = (
                    plant_unsupported_claim(item, pages, llm, settings)
                    if fault == "unsupported_claim"
                    else plant_true_distractor(item, pages, llm, settings, rng)
                )
                if written is not None:
                    planted = (written[0], written[1])
                    cost += written[2]
            if planted is None:
                continue
            made += 1
            entry = SeededItem(
                id=f"{fault}-{made:02d}",
                fault=fault,
                description=planted[1],
                topic=record.run.topic,
                difficulty=record.run.difficulty,
                item=planted[0],
                pages=pages,
            )
            seeded.append(entry)
            if on_item is not None:
                on_item(entry)
    return seeded, cost
