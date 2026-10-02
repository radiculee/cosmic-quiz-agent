"""Evidence tools the model can call, plus the submit_answer tool that ends a run."""

from __future__ import annotations

from agent.llm import ToolSpec
from agent.tools.arxiv import SEARCH_ARXIV
from agent.tools.base import Tool, ToolContext, ToolError, make_http_client
from agent.tools.feeds import FETCH_FEED
from agent.tools.fetch import FETCH_PAGE
from agent.tools.nasa import NASA_APOD, SEARCH_NASA_IMAGES
from agent.tools.wikipedia import SEARCH_WIKIPEDIA

# Order is part of the cached prompt prefix: keep it stable.
RESEARCH_TOOLS: tuple[Tool, ...] = (
    SEARCH_WIKIPEDIA,
    SEARCH_ARXIV,
    FETCH_FEED,
    NASA_APOD,
    SEARCH_NASA_IMAGES,
    FETCH_PAGE,
)

# Handled by the loop itself: the arguments are the final answer, validated with Pydantic.
SUBMIT_ANSWER = ToolSpec(
    name="submit_answer",
    description=(
        "Submit the final explanation with its citations. Call this exactly once, after "
        "reading the pages you cite. Calling it ends the run."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "explanation": {
                "type": "string",
                "description": "The plain-language explanation for the player.",
            },
            "citations": {
                "type": "array",
                "description": "Sources supporting the explanation, at least one.",
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL from the 'URL:' line of a page you read.",
                        },
                        "quote": {
                            "type": "string",
                            "description": "A short passage copied word for word from that page.",
                        },
                    },
                    "required": ["url", "quote"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["explanation", "citations"],
        "additionalProperties": False,
    },
)

_CITATIONS_SCHEMA = SUBMIT_ANSWER.input_schema["properties"]["citations"]

SUBMIT_QUIZ = ToolSpec(
    name="submit_quiz",
    description=(
        "Submit the finished quiz question with its citations. Call this exactly once, after "
        "reading the pages you cite. Calling it ends the run."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question shown to the player."},
            "options": {
                "type": "array",
                "description": "Exactly four answer options: one correct, three wrong.",
                "items": {"type": "string"},
            },
            "correct_index": {
                "type": "integer",
                "description": "Position of the correct option in options: 0, 1, 2 or 3.",
            },
            "explanation": {
                "type": "string",
                "description": "Shown after answering: why the correct option is right.",
            },
            "citations": {
                **_CITATIONS_SCHEMA,
                "description": "Sources, at least one. The first quote must support the answer.",
            },
        },
        "required": ["question", "options", "correct_index", "explanation", "citations"],
        "additionalProperties": False,
    },
)

__all__ = [
    "RESEARCH_TOOLS",
    "SUBMIT_ANSWER",
    "SUBMIT_QUIZ",
    "Tool",
    "ToolContext",
    "ToolError",
    "make_http_client",
]
