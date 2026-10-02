"""Prompts for LEARN mode: research a topic, then explain it with cited sources."""

from __future__ import annotations

from agent.prompts.common import RESEARCH_RULES, WORD_LIMITS, WRITING_RULES, lead_line
from agent.schemas import Difficulty

SUBMIT_TOOL = "submit_answer"

SYSTEM_PROMPT = f"""\
You are the research agent for Cosmic Quiz, an astronomy and space learning game. For each \
topic you research it with your tools, then call {SUBMIT_TOOL} with a plain-language \
explanation and its sources.

{RESEARCH_RULES}
{WRITING_RULES}- Call {SUBMIT_TOOL} exactly once; never reply with plain text instead.
"""

_DIFFICULTY_FOCUS: dict[Difficulty, str] = {
    "easy": "Cover the well-known basics: what it is and why it matters.",
    "medium": "Explain the mechanism: how it works and why it happens.",
    "hard": (
        "Include specific numbers or recent findings from the sources, and define one "
        "technical term precisely. Use a research paper or a recent news item if one is "
        "relevant."
    ),
}


def user_prompt(topic: str, difficulty: Difficulty, lead_url: str | None = None) -> str:
    low, high = WORD_LIMITS[difficulty]
    return (
        f"Topic: {topic}\n"
        f"Difficulty: {difficulty}. {low} to {high} words. {_DIFFICULTY_FOCUS[difficulty]}"
        f"{lead_line(lead_url)}"
    )
