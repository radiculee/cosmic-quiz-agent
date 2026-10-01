"""Shared types for tools: the run context they read and write, and the tool wrapper."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx2

from agent.config import Settings
from agent.llm import JsonObject, ToolSpec
from agent.verify import normalize_url


class ToolError(Exception):
    """A tool failed in a way the model should hear about and can recover from."""


@dataclass
class ToolContext:
    """Per-run state shared by tools.

    `fetched` is the source of truth for the citation rule: normalized URL to the text returned
    to the model. Only `fetch_page` adds to it.
    """

    settings: Settings
    http: httpx2.Client
    fetched: dict[str, str] = field(default_factory=dict)

    def record_fetch(self, text: str, *urls: str) -> None:
        for url in urls:
            self.fetched[normalize_url(url)] = text

    def is_allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not host:
            return False
        return any(
            host == domain or host.endswith("." + domain)
            for domain in self.settings.allowed_domains
        )


ToolHandler = Callable[[JsonObject, ToolContext], str]


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    run: ToolHandler


def make_http_client(settings: Settings) -> httpx2.Client:
    return httpx2.Client(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    )
