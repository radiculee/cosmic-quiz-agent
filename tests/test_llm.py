from __future__ import annotations

from typing import cast

import pytest

from agent.config import PRICES
from agent.llm import (
    AssistantMessage,
    ToolCall,
    ToolResult,
    ToolResultsMessage,
    Usage,
    UserMessage,
    _to_message_param,
    _to_stop_reason,
)


def test_usage_adds_and_prices() -> None:
    total = Usage(input_tokens=1000, output_tokens=100) + Usage(
        cache_write_tokens=4000, cache_read_tokens=10_000
    )

    assert total.total_input_tokens == 15_000
    # 1000 * $1 + 100 * $5 + 4000 * $1.25 + 10000 * $0.10, per million tokens
    assert total.cost_usd(PRICES["claude-haiku-4-5"]) == pytest.approx(0.0075)


def test_user_message_converts_to_plain_text() -> None:
    assert _to_message_param(UserMessage(text="Hi")) == {"role": "user", "content": "Hi"}


def test_assistant_message_skips_empty_text_and_keeps_tool_calls() -> None:
    message = AssistantMessage(
        text="  ",
        tool_calls=(ToolCall(id="t1", name="fetch_page", arguments={"url": "https://x"}),),
    )

    param = _to_message_param(message)

    assert param == {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": "t1", "name": "fetch_page", "input": {"url": "https://x"}}
        ],
    }


def test_tool_results_are_sent_together_as_one_user_message() -> None:
    message = ToolResultsMessage(
        results=(
            ToolResult(call_id="t1", content="ok"),
            ToolResult(call_id="t2", content="failed", is_error=True),
        )
    )

    param = _to_message_param(message)

    assert param["role"] == "user"
    # The SDK types content as a union of every block type; these are all tool results.
    blocks = cast(list[dict[str, object]], param["content"])
    assert [(b["tool_use_id"], b["is_error"]) for b in blocks] == [("t1", False), ("t2", True)]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("end_turn", "end_turn"),
        ("tool_use", "tool_use"),
        ("max_tokens", "max_tokens"),
        ("refusal", "other"),
        (None, "other"),
    ],
)
def test_stop_reasons_map_to_known_values(raw: str | None, expected: str) -> None:
    assert _to_stop_reason(raw) == expected
