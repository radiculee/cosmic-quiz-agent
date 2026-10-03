"""Provider-neutral LLM interface and its Anthropic implementation.

The agent loop only uses the types defined here, so another provider (for example an OpenRouter
client) can be added by writing one more class that satisfies `LLMProvider`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Literal, Protocol

import anthropic
from anthropic.types import (
    ContentBlockParam,
    MessageParam,
    TextBlockParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
)
from pydantic import BaseModel, ConfigDict

from agent.config import ModelPrice

JsonObject = dict[str, Any]

# Tokens the API adds around messages, tool definitions and the tool-use instructions, on top of
# the text we send. Generous on purpose: it only feeds an upper bound.
FORMAT_ALLOWANCE_TOKENS = 1500


def prompt_tokens_bound(*texts: str) -> int:
    """An upper bound on the tokens these texts become. Every token covers at least one byte
    of UTF-8 text, so the byte count can never be lower than the token count."""
    return sum(len(text.encode("utf-8")) for text in texts) + FORMAT_ALLOWANCE_TOKENS


class ToolSpec(BaseModel):
    """A tool the model may call, described by a JSON schema for its arguments."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: JsonObject


class ToolCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    arguments: JsonObject


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    call_id: str
    content: str
    is_error: bool = False


class UserMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["user"] = "user"
    text: str


class AssistantMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["assistant"] = "assistant"
    text: str
    tool_calls: tuple[ToolCall, ...] = ()


class ToolResultsMessage(BaseModel):
    """The results of every tool call from the previous assistant message, sent together."""

    model_config = ConfigDict(frozen=True)

    role: Literal["tool"] = "tool"
    results: tuple[ToolResult, ...]


Message = UserMessage | AssistantMessage | ToolResultsMessage


class Usage(BaseModel):
    """Token counts for one or more model calls."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
        )

    @property
    def total_input_tokens(self) -> int:
        """Every prompt token sent, whether billed at the full, cache-write or cache-read rate."""
        return self.input_tokens + self.cache_write_tokens + self.cache_read_tokens

    def cost_usd(self, price: ModelPrice) -> float:
        return (
            self.input_tokens * price.input_per_mtok
            + self.output_tokens * price.output_per_mtok
            + self.cache_write_tokens * price.cache_write_per_mtok
            + self.cache_read_tokens * price.cache_read_per_mtok
        ) / 1_000_000


StopReason = Literal["end_turn", "tool_use", "max_tokens", "other"]


class Completion(BaseModel):
    model_config = ConfigDict(frozen=True)

    message: AssistantMessage
    stop_reason: StopReason
    usage: Usage


class LLMError(Exception):
    """A model call failed after the provider's own retries.

    `usage` holds what the failed call was still billed for (for example a reply cut off at the
    output limit), so the cost of every call is logged even when it fails.
    """

    def __init__(self, message: str, usage: Usage | None = None) -> None:
        super().__init__(message)
        self.usage = usage or Usage()


class LLMProvider(Protocol):
    @property
    def model(self) -> str: ...

    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        max_tokens: int,
    ) -> Completion: ...

    def complete_json(
        self, system: str, prompt: str, schema: JsonObject, max_tokens: int
    ) -> tuple[JsonObject, Usage]:
        """One call whose reply is a JSON object matching `schema`."""
        ...

    def count_json_tokens(self, system: str, prompt: str, schema: JsonObject) -> int:
        """The exact prompt size of a `complete_json` call, without making it (free)."""
        ...


class AnthropicProvider:
    """Claude via the official `anthropic` SDK.

    Tools are sent with `strict: true`, so arguments always match their schema. Automatic prompt
    caching is requested on every call; it only takes effect once the prompt passes the model's
    minimum cacheable length (4,096 tokens on Haiku 4.5).
    """

    def __init__(
        self,
        model: str,
        *,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._model = model
        # The SDK retries connection errors, 408, 409, 429 and 5xx with exponential backoff.
        self._client = client or anthropic.Anthropic(
            timeout=timeout_seconds, max_retries=max_retries
        )

    @property
    def model(self) -> str:
        return self._model

    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        max_tokens: int,
    ) -> Completion:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[_to_message_param(message) for message in messages],
                tools=[_to_tool_param(tool) for tool in tools],
                cache_control={"type": "ephemeral"},
            )
        except anthropic.AnthropicError as error:
            # Covers API errors after retries and client errors such as a missing API key.
            raise LLMError(f"{type(error).__name__}: {error}") from error

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                arguments = block.input if isinstance(block.input, dict) else {}
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=arguments))

        usage = response.usage
        return Completion(
            message=AssistantMessage(text="".join(text_parts), tool_calls=tuple(tool_calls)),
            stop_reason=_to_stop_reason(response.stop_reason),
            usage=Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_write_tokens=usage.cache_creation_input_tokens or 0,
                cache_read_tokens=usage.cache_read_input_tokens or 0,
            ),
        )

    def complete_json(
        self, system: str, prompt: str, schema: JsonObject, max_tokens: int
    ) -> tuple[JsonObject, Usage]:
        """Structured output: the API constrains the reply to `schema` (`output_config.format`)."""
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except anthropic.AnthropicError as error:
            raise LLMError(f"{type(error).__name__}: {error}") from error

        usage = Usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_write_tokens=response.usage.cache_creation_input_tokens or 0,
            cache_read_tokens=response.usage.cache_read_input_tokens or 0,
        )
        # From here on the call has been billed, so every failure carries its usage.
        if response.stop_reason != "end_turn":
            raise LLMError(f"structured output stopped early ({response.stop_reason})", usage)
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise LLMError("structured output was not valid JSON", usage) from error
        if not isinstance(data, dict):
            raise LLMError("structured output was not a JSON object", usage)
        return data, usage

    def count_json_tokens(self, system: str, prompt: str, schema: JsonObject) -> int:
        """Anthropic's token counting endpoint: free, and exact for this model."""
        try:
            response = self._client.messages.count_tokens(
                model=self._model,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except anthropic.AnthropicError as error:
            raise LLMError(f"{type(error).__name__}: {error}") from error
        return response.input_tokens


def _to_stop_reason(reason: str | None) -> StopReason:
    if reason == "end_turn":
        return "end_turn"
    if reason == "tool_use":
        return "tool_use"
    if reason == "max_tokens":
        return "max_tokens"
    return "other"


def _to_tool_param(tool: ToolSpec) -> ToolParam:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "strict": True,
    }


def _to_message_param(message: Message) -> MessageParam:
    if isinstance(message, UserMessage):
        return {"role": "user", "content": message.text}

    if isinstance(message, AssistantMessage):
        blocks: list[ContentBlockParam] = []
        # The API rejects empty text blocks, so only send text the model actually wrote.
        if message.text.strip():
            text_block: TextBlockParam = {"type": "text", "text": message.text}
            blocks.append(text_block)
        for call in message.tool_calls:
            tool_use: ToolUseBlockParam = {
                "type": "tool_use",
                "id": call.id,
                "name": call.name,
                "input": call.arguments,
            }
            blocks.append(tool_use)
        return {"role": "assistant", "content": blocks}

    results: list[ToolResultBlockParam] = [
        {
            "type": "tool_result",
            "tool_use_id": result.call_id,
            "content": result.content,
            "is_error": result.is_error,
        }
        for result in message.results
    ]
    return {"role": "user", "content": results}
