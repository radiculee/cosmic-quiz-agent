"""The public side of the bank: what players can see.

Reads use the publishable key, so row-level security (supabase/schema.sql) guarantees they can
only ever return published items with fewer than 2 reports, never review or discarded ones, and
never server-only columns such as a news topic's unread article link.

The one exception is `LiveResults`, which uses the secret key to read back, by id only, the
item a player's own live run has just stored, including one in review (DESIGN.md decision 9).
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

    @property
    def complete(self) -> bool:
        """Whether both modes are at every difficulty: only such a topic is listed on Learn and
        Quiz (decided 2026-10-28), so every level has the same topics."""
        return all(set(DIFFICULTY_ORDER) <= set(found) for found in (self.learn, self.quiz))


class _TopicColumns(BaseModel):
    name: str
    kind: TopicKind


class _ItemIndexRow(BaseModel):
    mode: Mode
    difficulty: Difficulty
    topics: _TopicColumns


_INDEX_ROWS = TypeAdapter(list[_ItemIndexRow])


class _NameRow(BaseModel):
    name: str


_NAME_ROWS = TypeAdapter(list[_NameRow])
_TOPIC_ROWS = TypeAdapter(list[_TopicColumns])
_ID_ROWS = TypeAdapter(list[object])


# --- What a player sees ------------------------------------------------------------------------

# "review" is only ever shown to the player whose live run produced the item, labelled as not
# fully verified; the bank serves "published" items only.
ShownStatus = Literal["published", "review"]


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
    status: ShownStatus = "published"


class QuizAnswer(BaseModel):
    """Everything about a QUIZ item that is shown once the player has answered."""

    model_config = ConfigDict(frozen=True)

    id: int
    correct_index: int
    explanation: str
    sources: list[Source]
    source_check: SourceCheck
    # Why the checks held the item back, for an item in review. Sent only with the answer,
    # because a doubt about the explanation can give the answer away.
    doubts: list[str] = []


class LearnItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    mode: Literal["learn"] = "learn"
    difficulty: Difficulty
    topic: str
    explanation: str
    sources: list[Source]
    source_check: SourceCheck
    status: ShownStatus = "published"
    doubts: list[str] = []


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
    status: ShownStatus = "published"
    haiku_reasons: list[str] = []
    jev_reasons: list[str] = []
    question: str | None = None
    options: list[str] | None = None
    correct_index: int | None = None
    explanation: str
    topics: _TopicColumns
    sources: list[_SourceRow] = []
    claim_checks: list[_Check] = []


_ITEM_ROWS = TypeAdapter(list[_ItemRow])
_ITEM_SELECT = (
    "id,mode,difficulty,status,haiku_reasons,jev_reasons,question,options,correct_index,"
    "explanation,topics!inner(name,kind),"
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


def doubts_of(row: _ItemRow) -> list[str]:
    return [*row.haiku_reasons, *row.jev_reasons] if row.status == "review" else []


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
            status=row.status,
            doubts=doubts_of(row),
        )
    return QuizQuestion(
        id=row.id,
        difficulty=row.difficulty,
        topic=row.topics.name,
        question=row.question or "",
        options=row.options or [],
        status=row.status,
    )


def answer_of(row: _ItemRow) -> QuizAnswer:
    return QuizAnswer(
        id=row.id,
        correct_index=row.correct_index or 0,
        explanation=row.explanation,
        sources=sources_of(row),
        source_check=source_check_of(row),
        doubts=doubts_of(row),
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


# What players may see of the bank: published items with fewer than 2 reports. Row-level security
# already enforces this for the publishable key; the filter repeats it, so a reader is correct
# whichever key it is given.
_VISIBLE = {"status": "eq.published", "report_count": "lt.2"}


def _read_items(rest: RestClient, filters: dict[str, str]) -> list[_ItemRow]:
    reply = rest.send(
        "GET",
        "/items",
        params={
            "select": _ITEM_SELECT,
            "order": "id.asc",
            "sources.order": "ordinal.asc",
            "claim_checks.layer": "eq.jev",
            **filters,
        },
        retries=RETRIES,
    )
    return parse(_ITEM_ROWS, reply, "reading items")


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
            "/items",
            {"select": "mode,difficulty,topics(name,kind)", "order": "id.asc", **_VISIBLE},
        )
        return summarize(parse(_INDEX_ROWS, rows, "reading the bank's topics"))

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
        rows = _read_items(
            self._rest,
            {
                "topics.name": f"eq.{topic}",
                "mode": f"eq.{mode}",
                "difficulty": f"eq.{difficulty}",
                **_VISIBLE,
            },
        )
        fresh = [row for row in rows if row.id not in exclude] or rows
        if not fresh:
            return None
        return question_of((rng or random.Random()).choice(fresh))

    def topic_named(self, name: str) -> str | None:
        """The bank's own spelling of a topic with published items, matched ignoring case, or
        None if the bank has no such topic.

        One filtered read: `ilike` matches ignoring case (using the index on lower(name)). Topic
        names cannot contain `%` or `_` (agent/topic_check.py), but PostgREST reads `*` as a
        wildcard, so candidates are compared exactly here.
        """
        reply = self._rest.send(
            "GET",
            "/topics",
            params={"select": "name", "name": f"ilike.{name}", "limit": "10"},
            retries=RETRIES,
        )
        wanted = name.casefold()
        for row in parse(_NAME_ROWS, reply, "finding a topic"):
            if row.name.casefold() == wanted:
                return row.name
        return None

    def topic_names(self) -> list[tuple[str, TopicKind]]:
        """Every topic with a published item, newest first, whatever levels it has: what a
        Surprise me pick must not repeat (agent/topic_pick.py)."""
        rows = self._rest.read_all(
            "/topics", {"select": "name,kind", "order": "created_at.desc,id.desc"}
        )
        return [(row.name, row.kind) for row in parse(_TOPIC_ROWS, rows, "reading topic names")]

    def coverage(self, topic: str) -> BankTopic | None:
        """Where the bank can already serve this topic (its exact name): the difficulties with
        a published item, per mode. None if it has no published item for it. One small read: a
        topic has a handful of items."""
        reply = self._rest.send(
            "GET",
            "/items",
            params={
                "select": "mode,difficulty,topics!inner(name,kind)",
                "topics.name": f"eq.{topic}",
                "order": "id.asc",
                **_VISIBLE,
            },
            retries=RETRIES,
        )
        found = summarize(parse(_INDEX_ROWS, reply, "checking the bank"))
        return found[0] if found else None

    def is_published(self, item_id: int) -> bool:
        """Whether players can see this item (published, fewer than 2 reports)."""
        reply = self._rest.send(
            "GET",
            "/items",
            params={"select": "id", "id": f"eq.{item_id}", **_VISIBLE},
            retries=RETRIES,
        )
        return bool(parse(_ID_ROWS, reply, "checking an item"))

    def reveal(self, item_id: int) -> QuizAnswer | None:
        """The answer to a published quiz item, or None if there is no such item."""
        rows = _read_items(self._rest, {"id": f"eq.{item_id}", "mode": "eq.quiz", **_VISIBLE})
        return answer_of(rows[0]) if rows else None


# A live result as its player may see it: published or still in review, never discarded.
_SHOWN_TO_REQUESTER = {"status": "in.(published,review)"}


class LiveResults:
    """A player's own live result, read by id with the secret key, so an item in review can be
    shown to the player who asked for it (labelled as not fully verified). It can read nothing
    else: no listing, no search, never a discarded item."""

    def __init__(self, rest: RestClient) -> None:
        self._rest = rest

    @classmethod
    def from_env(cls) -> Self:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        if not url or not key:
            raise StoreError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set")
        return cls(RestClient(url, key))

    def close(self) -> None:
        self._rest.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def item(self, item_id: int) -> QuizQuestion | LearnItem | None:
        """The item as the player first sees it (a quiz item without its answer)."""
        rows = _read_items(self._rest, {"id": f"eq.{item_id}", **_SHOWN_TO_REQUESTER})
        return question_of(rows[0]) if rows else None

    def reveal(self, item_id: int) -> QuizAnswer | None:
        """A quiz item's answer, with the doubts that held it back if it is in review."""
        rows = _read_items(
            self._rest, {"id": f"eq.{item_id}", "mode": "eq.quiz", **_SHOWN_TO_REQUESTER}
        )
        return answer_of(rows[0]) if rows else None
