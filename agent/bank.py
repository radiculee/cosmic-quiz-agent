"""The public side of the bank: what players can see.

Reads use the publishable key, so row-level security (supabase/schema.sql) guarantees they can
only ever return published items with fewer than 2 reports, never review or discarded ones, and
never server-only columns such as a news topic's unread article link.
"""

from __future__ import annotations

import os
import random
from collections import defaultdict
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, TypeAdapter

from agent.rest import RETRIES, RestClient, StoreError, parse
from agent.schemas import ClaimKind, Difficulty, JevVerdict, Mode
from agent.store import TopicKind, domain

DIFFICULTY_ORDER: tuple[Difficulty, ...] = ("easy", "medium", "hard")


class BankTopic(BaseModel):
    """A topic and the difficulties that have at least one published item, per mode."""

    model_config = ConfigDict(frozen=True)

    name: str
    kind: TopicKind
    learn: list[Difficulty]
    quiz: list[Difficulty]


class _TopicColumns(BaseModel):
    name: str
    kind: TopicKind


class _ItemIndexRow(BaseModel):
    mode: Mode
    difficulty: Difficulty
    topics: _TopicColumns


_INDEX_ROWS = TypeAdapter(list[_ItemIndexRow])


# --- What a player sees ------------------------------------------------------------------------


class Source(BaseModel):
    """A cited page: read by the agent in its run, with the passage quoted from it."""

    model_config = ConfigDict(frozen=True)

    url: str
    site: str
    quote: str


class OptionCheck(BaseModel):
    """What Jev found the cited pages say about one answer option."""

    model_config = ConfigDict(frozen=True)

    option: int
    verdict: JevVerdict
    confidence: float


class SourceCheck(BaseModel):
    """Jev's second opinion, as players see it. It says what the cited sources support; it is
    not a measure of accuracy. `options` is empty for LEARN items."""

    model_config = ConfigDict(frozen=True)

    options: list[OptionCheck]
    sentences: int
    sentences_supported: int


class QuizQuestion(BaseModel):
    """A QUIZ item before it is answered: no correct answer, explanation or sources."""

    model_config = ConfigDict(frozen=True)

    id: int
    mode: Literal["quiz"] = "quiz"
    difficulty: Difficulty
    topic: str
    question: str
    options: list[str]


class QuizAnswer(BaseModel):
    """Everything about a QUIZ item that is shown once the player has answered."""

    model_config = ConfigDict(frozen=True)

    id: int
    correct_index: int
    explanation: str
    sources: list[Source]
    source_check: SourceCheck


class LearnItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    mode: Literal["learn"] = "learn"
    difficulty: Difficulty
    topic: str
    explanation: str
    sources: list[Source]
    source_check: SourceCheck


class _Check(BaseModel):
    kind: ClaimKind
    claim: str
    verdict: JevVerdict
    confidence: float | None = None


class _SourceRow(BaseModel):
    ordinal: int
    url: str
    quote: str


class _ItemRow(BaseModel):
    id: int
    mode: Mode
    difficulty: Difficulty
    question: str | None = None
    options: list[str] | None = None
    correct_index: int | None = None
    explanation: str
    topics: _TopicColumns
    sources: list[_SourceRow] = []
    claim_checks: list[_Check] = []


_ITEM_ROWS = TypeAdapter(list[_ItemRow])
_ITEM_SELECT = (
    "id,mode,difficulty,question,options,correct_index,explanation,topics!inner(name,kind),"
    "sources(ordinal,url,quote),claim_checks(kind,claim,verdict,confidence)"
)
_ANSWER_MARK = " is: "


def sources_of(row: _ItemRow) -> list[Source]:
    ordered = sorted(row.sources, key=lambda source: source.ordinal)
    return [Source(url=s.url, site=domain(s.url), quote=s.quote) for s in ordered]


def source_check_of(row: _ItemRow) -> SourceCheck:
    """Jev's stored checks, matched to the item's options by text.

    Each answer and distractor claim reads 'The answer to the question "..." is: <option>'
    (agent/verifiers/jev.py), so the option is the text after the last ' is: '.
    """
    options = row.options or []
    by_text = {option.strip().casefold(): index for index, option in enumerate(options)}
    option_checks: list[OptionCheck] = []
    for check in row.claim_checks:
        if check.kind not in ("correct_answer", "distractor") or check.confidence is None:
            continue
        text = check.claim.rsplit(_ANSWER_MARK, 1)[-1].strip().casefold()
        index = by_text.get(text)
        if index is not None:
            option_checks.append(
                OptionCheck(option=index, verdict=check.verdict, confidence=check.confidence)
            )
    sentences = [check for check in row.claim_checks if check.kind == "sentence"]
    return SourceCheck(
        options=sorted(option_checks, key=lambda check: check.option),
        sentences=len(sentences),
        sentences_supported=sum(1 for check in sentences if check.verdict == "supports"),
    )


def question_of(row: _ItemRow) -> QuizQuestion | LearnItem:
    """What the player first sees: a quiz question without its answer, or a whole LEARN item."""
    if row.mode == "learn":
        return LearnItem(
            id=row.id,
            difficulty=row.difficulty,
            topic=row.topics.name,
            explanation=row.explanation,
            sources=sources_of(row),
            source_check=source_check_of(row),
        )
    return QuizQuestion(
        id=row.id,
        difficulty=row.difficulty,
        topic=row.topics.name,
        question=row.question or "",
        options=row.options or [],
    )


def answer_of(row: _ItemRow) -> QuizAnswer:
    return QuizAnswer(
        id=row.id,
        correct_index=row.correct_index or 0,
        explanation=row.explanation,
        sources=sources_of(row),
        source_check=source_check_of(row),
    )


def summarize(rows: list[_ItemIndexRow]) -> list[BankTopic]:
    """One entry per topic, alphabetical, with its difficulties in easy-medium-hard order."""
    available: dict[tuple[str, TopicKind], dict[Mode, set[Difficulty]]] = defaultdict(
        lambda: {"learn": set(), "quiz": set()}
    )
    for row in rows:
        available[(row.topics.name, row.topics.kind)][row.mode].add(row.difficulty)

    def ordered(found: set[Difficulty]) -> list[Difficulty]:
        return [d for d in DIFFICULTY_ORDER if d in found]

    return [
        BankTopic(name=name, kind=kind, learn=ordered(modes["learn"]), quiz=ordered(modes["quiz"]))
        for (name, kind), modes in sorted(available.items(), key=lambda entry: entry[0][0].lower())
    ]


class BankReader:
    """Reads the published bank with the publishable key."""

    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    @classmethod
    def from_env(cls) -> Self:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
        if not url or not key:
            raise StoreError("SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be set")
        return cls(RestClient(url, key))

    def close(self) -> None:
        self._rest.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def topics(self) -> list[BankTopic]:
        """Every topic with a published item, and where it has them."""
        rows = self._rest.read_all(
            "/items", {"select": "mode,difficulty,topics(name,kind)", "order": "id.asc"}
        )
        return summarize(parse(_INDEX_ROWS, rows, "reading the bank's topics"))

    def _items(self, params: dict[str, str]) -> list[_ItemRow]:
        reply = self._rest.send(
            "GET",
            "/items",
            params={
                "select": _ITEM_SELECT,
                "order": "id.asc",
                "sources.order": "ordinal.asc",
                "claim_checks.layer": "eq.jev",
                **params,
            },
            retries=RETRIES,
        )
        return parse(_ITEM_ROWS, reply, "reading items")

    def random_item(
        self,
        topic: str,
        mode: Mode,
        difficulty: Difficulty,
        exclude: frozenset[int] = frozenset(),
        rng: random.Random | None = None,
    ) -> QuizQuestion | LearnItem | None:
        """A random published item for the topic, mode and difficulty, avoiding `exclude` (items
        the player has just seen) while there is another to show. None if there is none."""
        rows = self._items(
            {"topics.name": f"eq.{topic}", "mode": f"eq.{mode}", "difficulty": f"eq.{difficulty}"}
        )
        fresh = [row for row in rows if row.id not in exclude] or rows
        if not fresh:
            return None
        return question_of((rng or random.Random()).choice(fresh))

    def is_published(self, item_id: int) -> bool:
        """Whether players can see this item (published, fewer than 2 reports)."""
        reply = self._rest.send(
            "GET", "/items", params={"select": "id", "id": f"eq.{item_id}"}, retries=RETRIES
        )
        return bool(parse(TypeAdapter(list[object]), reply, "checking an item"))

    def reveal(self, item_id: int) -> QuizAnswer | None:
        """The answer to a published quiz item, or None if there is no such item."""
        rows = self._items({"id": f"eq.{item_id}", "mode": "eq.quiz"})
        return answer_of(rows[0]) if rows else None
