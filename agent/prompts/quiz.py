"""Prompts for QUIZ mode: research a topic, then write one four-option question with sources.

Per-difficulty guidance follows DESIGN.md decision 13 (depth plus distractors).
"""

from __future__ import annotations

from agent.prompts.common import RESEARCH_RULES, WORD_LIMITS, WRITING_RULES
from agent.schemas import Difficulty

SUBMIT_TOOL = "submit_quiz"

SYSTEM_PROMPT = f"""\
You are the question writer for Cosmic Quiz, an astronomy and space learning game. For each \
topic you research it with your tools, then call {SUBMIT_TOOL} with one multiple-choice \
question, four options, the index of the correct option, an explanation and its sources.

{RESEARCH_RULES}
How to write the question:
- Ask about one fact or idea that your sources state clearly. Exactly one option must be \
correct according to the sources, and the first citation's quote must support it.
- The three wrong options (distractors) must be clearly wrong according to the sources, but \
believable to someone who has not learned the topic. Never use "all of the above", "none of \
the above" or trick wording.
- Keep all four options similar in length and form, so the right one does not stand out.
- The explanation is shown after the player answers: say why the correct option is right, and \
briefly why the most tempting wrong option is wrong. Write it about the topic, for the player: \
never mention "distractors", "options", option letters or how the question was written.

{WRITING_RULES}- Call {SUBMIT_TOOL} exactly once; never reply with plain text instead.
"""

_DIFFICULTY_FOCUS: dict[Difficulty, str] = {
    "easy": (
        "Ask about a well-known fact. Distractors are clearly wrong to anyone who knows the "
        "basics. Prefer Wikipedia and NASA sources."
    ),
    "medium": (
        "Ask about a mechanism or a 'why'. Distractors are plausible explanations that the "
        "sources show to be wrong."
    ),
    "hard": (
        "Ask about a specific number or a recent finding. Build distractors from common "
        "misconceptions or nearby values. Use a research paper or a recent news item if one "
        "is relevant, and define one technical term in the explanation."
    ),
}


def user_prompt(topic: str, difficulty: Difficulty) -> str:
    low, high = WORD_LIMITS[difficulty]
    return (
        f"Topic: {topic}\n"
        f"Difficulty: {difficulty}. {_DIFFICULTY_FOCUS[difficulty]}\n"
        f"Explanation: {low} to {high} words."
    )
