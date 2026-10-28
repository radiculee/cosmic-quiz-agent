"""Surprise me: the agent picks a topic the bank does not have yet, for a live search.

One short Haiku call proposes up to three topics within a theme drawn at random in code (so
repeated clicks range across astronomy). The code then takes the first proposal that is a valid
topic name (`clean_topic`) and not already in the bank, so the model cannot repeat a topic or
send markup through. Decided by Vedant on 2026-10-28.

A picked topic skips the on-topic check (Jev): the model proposes an astronomy topic by
construction, and nothing a visitor typed reaches its prompt. Visitors' custom topics are left
out of the "already covered" list, as in the Curator's news choice (curator/discover.py); the
duplicate check in code still compares against every name.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, ValidationError

from agent.config import Settings
from agent.llm import JsonObject, LLMError, LLMProvider, Usage, prompt_tokens_bound
from agent.store import TopicKind
from agent.topic_check import InvalidTopicError, clean_topic

MAX_PICKS = 3
# The pick is skipped if its cost bound exceeds this. A typical pick is about $0.001.
MAX_COST_USD = 0.01
_MAX_OUTPUT_TOKENS = 400

# One is drawn per pick, so the topics spread across the subject instead of the model's favourite.
THEMES = (
    "the planets, moons and small bodies of the Solar System",
    "the Sun and other stars, and how stars live and die",
    "galaxies, galaxy clusters and the large-scale universe",
    "cosmology and the history of the universe",
    "exoplanets and the search for life beyond Earth",
    "space telescopes, observatories and how astronomers observe",
    "crewed spaceflight, space stations and robotic missions",
    "black holes, neutron stars and other extreme objects",
    "phenomena seen from Earth: eclipses, meteors, auroras and comets",
)

SYSTEM_PROMPT = """\
You choose topics for Cosmic Quiz, an astronomy and space learning game. An agent will research \
the topic you choose on NASA, ESA, arXiv and Wikipedia pages and write questions and an \
explanation at three levels, from a beginner to an enthusiast."""

_INSTRUCTIONS = f"""\
Propose up to {MAX_PICKS} topics within the theme, best first. A good topic:
- names one well-documented object, phenomenon, mission, instrument or idea, which NASA, ESA \
or Wikipedia pages explain in depth;
- is broad enough for a beginner's question and deep enough for an enthusiast's;
- is not already covered by an existing topic, under any name.

Give each topic as a short encyclopedia heading of 1 to 6 words (for example "Pulsars", \
"The Kuiper Belt", "The Cassini mission"), and say in one sentence why it makes a good topic."""

PICKS_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"topic": {"type": "string"}, "why": {"type": "string"}},
                "required": ["topic", "why"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["picks"],
    "additionalProperties": False,
}


class TopicProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    why: str


class _PicksReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    picks: list[TopicProposal]


@dataclass
class TopicPick:
    """The chosen topic (or None), what the call cost, and why proposals were skipped."""

    topic: str | None
    usage: Usage = field(default_factory=Usage)
    cost_usd: float = 0.0
    notes: list[str] = field(default_factory=list)


def build_prompt(theme: str, existing: Sequence[tuple[str, TopicKind]]) -> str:
    # Visitors' custom topics are left out: their text is visitor-typed (see the module docstring).
    listed = "\n".join(f"- {name}" for name, kind in existing if kind != "custom")
    return (
        f"Theme: {theme}\n\nExisting topics (do not repeat these):\n{listed or '- (none yet)'}"
        f"\n\n{_INSTRUCTIONS}"
    )


def choose(
    proposals: Sequence[TopicProposal], existing: Sequence[tuple[str, TopicKind]]
) -> tuple[str | None, list[str]]:
    """The first proposal that is a valid topic name not in the bank, with a note for each one
    skipped. Names are compared as the bank's unique index compares them, ignoring case."""
    known = {name.strip().casefold() for name, _ in existing}
    notes: list[str] = []
    for proposal in proposals[:MAX_PICKS]:
        try:
            name = clean_topic(proposal.topic)
        except InvalidTopicError as error:
            notes.append(f"skipped {proposal.topic!r}: {error}")
            continue
        if name.casefold() in known:
            notes.append(f"skipped {name!r}: already in the bank")
            continue
        return name, notes
    return None, notes


class HaikuTopicPicker:
    """Picks with the search's model. `rng` is passed in so tests can fix the theme."""

    def __init__(
        self, llm: LLMProvider, settings: Settings, rng: random.Random | None = None
    ) -> None:
        self._llm = llm
        self._settings = settings
        self._rng = rng or random.Random()

    def pick(self, existing: Sequence[tuple[str, TopicKind]]) -> TopicPick:
        prompt = build_prompt(self._rng.choice(THEMES), existing)
        bound = self._settings.price.max_call_cost_usd(
            prompt_tokens_bound(SYSTEM_PROMPT, prompt, json.dumps(PICKS_SCHEMA)),
            _MAX_OUTPUT_TOKENS,
        )
        if bound > MAX_COST_USD:
            return TopicPick(topic=None, notes=[f"skipped: the call could cost up to ${bound:.4f}"])
        try:
            data, usage = self._llm.complete_json(
                SYSTEM_PROMPT, prompt, PICKS_SCHEMA, _MAX_OUTPUT_TOKENS
            )
        except LLMError as error:  # may have been billed, e.g. a reply cut off at the limit
            return TopicPick(
                topic=None,
                usage=error.usage,
                cost_usd=error.usage.cost_usd(self._settings.price),
                notes=[f"topic pick failed: {error}"],
            )
        cost = usage.cost_usd(self._settings.price)
        try:
            reply = _PicksReply.model_validate(data)
        except ValidationError as error:
            return TopicPick(topic=None, usage=usage, cost_usd=cost, notes=[f"bad reply: {error}"])
        topic, notes = choose(reply.picks, existing)
        if topic is None and not notes:
            notes.append("the model proposed no topic")
        return TopicPick(topic=topic, usage=usage, cost_usd=cost, notes=notes)
