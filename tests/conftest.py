"""Shared fixtures: a fake web for tools and a scripted LLM for the loop. Nothing touches the
network or a paid API."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from typing import Any

import httpx2
import pytest

from agent.config import Settings
from agent.llm import (
    AssistantMessage,
    Completion,
    Message,
    StopReason,
    ToolCall,
    ToolSpec,
    Usage,
)
from agent.tools import ToolContext

Route = Callable[[httpx2.Request], httpx2.Response]


class FakeWeb:
    """Routes requests by URL prefix to canned responses and records every request.

    Routes are checked in the order they were added, so add specific prefixes first.
    """

    def __init__(self) -> None:
        self.routes: list[tuple[str, Route]] = []
        self.requests: list[httpx2.Request] = []

    def add(self, url_prefix: str, route: Route) -> None:
        self.routes.append((url_prefix, route))

    def add_text(
        self,
        url_prefix: str,
        text: str,
        content_type: str = "text/html; charset=utf-8",
        status: int = 200,
    ) -> None:
        self.add(
            url_prefix,
            lambda _request: httpx2.Response(
                status, text=text, headers={"content-type": content_type}
            ),
        )

    def add_json(self, url_prefix: str, data: object, status: int = 200) -> None:
        self.add(url_prefix, lambda _request: httpx2.Response(status, json=data))

    def add_redirect(self, url_prefix: str, location: str) -> None:
        self.add(url_prefix, lambda _request: httpx2.Response(301, headers={"location": location}))

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        url = str(request.url)
        for prefix, route in self.routes:
            if url.startswith(prefix):
                return route(request)
        return httpx2.Response(404, text="not found")


class FakeLLM:
    """Plays back a scripted list of completions (or errors) and records what it was sent."""

    def __init__(
        self,
        script: Sequence[Completion | Exception] = (),
        json_replies: Sequence[dict[str, Any] | Exception] = (),
    ) -> None:
        self._script = list(script)
        self._json_replies = list(json_replies)
        self.calls: list[list[Message]] = []
        self.json_prompts: list[str] = []

    @property
    def model(self) -> str:
        return "claude-haiku-4-5"

    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
        max_tokens: int,
    ) -> Completion:
        self.calls.append(list(messages))
        if not self._script:
            raise AssertionError("FakeLLM ran out of scripted completions")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def complete_json(
        self, system: str, prompt: str, schema: dict[str, Any], max_tokens: int
    ) -> tuple[dict[str, Any], Usage]:
        self.json_prompts.append(prompt)
        if not self._json_replies:
            raise AssertionError("FakeLLM ran out of scripted JSON replies")
        reply = self._json_replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply, CALL_USAGE

    def count_json_tokens(self, system: str, prompt: str, schema: dict[str, Any]) -> int:
        """About four characters per token, like English text."""
        return (len(system) + len(prompt)) // 4


CALL_USAGE = Usage(input_tokens=100, output_tokens=10)


def completion(
    *calls: tuple[str, dict[str, Any]],
    text: str = "",
    stop_reason: StopReason | None = None,
) -> Completion:
    """Build a scripted model turn that makes the given tool calls."""
    tool_calls = tuple(
        ToolCall(id=f"call_{index}", name=name, arguments=arguments)
        for index, (name, arguments) in enumerate(calls)
    )
    return Completion(
        message=AssistantMessage(text=text, tool_calls=tool_calls),
        stop_reason=stop_reason or ("tool_use" if tool_calls else "end_turn"),
        usage=CALL_USAGE,
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(http_retry_backoff_seconds=0.0)


@pytest.fixture
def web() -> FakeWeb:
    return FakeWeb()


@pytest.fixture
def http(web: FakeWeb, settings: Settings) -> Iterator[httpx2.Client]:
    client = httpx2.Client(
        transport=httpx2.MockTransport(web.handler),
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    )
    yield client
    client.close()


@pytest.fixture
def ctx(settings: Settings, http: httpx2.Client) -> ToolContext:
    return ToolContext(settings=settings, http=http)
