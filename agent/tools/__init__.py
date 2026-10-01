"""Evidence tools the model can call, plus the submit_answer tool that ends a run."""

from __future__ import annotations

from agent.llm import ToolSpec
from agent.tools.base import Tool, ToolContext, ToolError, make_http_client
from agent.tools.fetch import FETCH_PAGE
from agent.tools.wikipedia import SEARCH_WIKIPEDIA

RESEARCH_TOOLS: tuple[Tool, ...] = (SEARCH_WIKIPEDIA, FETCH_PAGE)

# Handled by the loop itself: the arguments are the final answer, validated with Pydantic.
SUBMIT_ANSWER = ToolSpec(
    name="submit_answer",
    description=(
        "Submit the final explanation with its citations. Call this exactly once, after "
        "reading the pages you cite with fetch_page. Calling it ends the run."
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
                            "description": "URL from the 'URL:' line of a fetch_page result.",
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

__all__ = [
    "RESEARCH_TOOLS",
    "SUBMIT_ANSWER",
    "Tool",
    "ToolContext",
    "ToolError",
    "make_http_client",
]
