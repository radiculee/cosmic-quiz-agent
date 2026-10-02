"""Shared types for tools: the run context they read and write, the tool wrapper, and HTTP."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx2

from agent.config import Settings
from agent.llm import JsonObject, ToolSpec
from agent.verify import normalize_url

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_RETRY_AFTER_SECONDS = 5.0


class ToolError(Exception):
    """A tool failed in a way the model should hear about and can recover from."""


@dataclass
class ToolContext:
    """Per-run state shared by tools.

    `fetched` is the source of truth for the citation rule: normalized URL to the text returned
    to the model. Only tools that read a page's content add to it. A redirected page is recorded
    under both its requested and final URL, so `reads` keeps one URL (the last) per page read.
    """

    settings: Settings
    http: httpx2.Client
    fetched: dict[str, str] = field(default_factory=dict)
    reads: list[str] = field(default_factory=list)

    def record_fetch(self, text: str, *urls: str) -> None:
        for url in urls:
            self.fetched[normalize_url(url)] = text
        if urls:
            self.reads.append(normalize_url(urls[-1]))

    def is_allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not host:
            return False
        for domain in self.settings.allowed_domains:
            if host == domain or host.endswith("." + domain):
                prefixes = self.settings.allowed_path_prefixes.get(domain)
                return prefixes is None or parts.path.startswith(prefixes)
        return False


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


def _retry_delay(ctx: ToolContext, attempt: int, response: httpx2.Response | None) -> float:
    if response is not None:
        retry_after = response.headers.get("retry-after", "")
        if retry_after.isdigit():
            return min(float(retry_after), _MAX_RETRY_AFTER_SECONDS)
    return float(ctx.settings.http_retry_backoff_seconds * (2**attempt))


def http_get(
    ctx: ToolContext, url: str, params: Mapping[str, str] | None = None
) -> httpx2.Response:
    """GET with retries on rate limits, server errors and network failures.

    Any other non-success status, or running out of retries, raises ToolError so the model is
    told what went wrong and can try something else.
    """
    attempts = ctx.settings.http_retries + 1
    for attempt in range(attempts):
        response: httpx2.Response | None = None
        try:
            response = ctx.http.get(url, params=params)
        except httpx2.TransportError as error:
            if attempt == attempts - 1:
                raise ToolError(f"Could not reach {url}: {error}") from error
        else:
            if response.status_code not in _RETRY_STATUSES:
                if response.is_error:
                    raise ToolError(f"{url} returned HTTP {response.status_code}.")
                return response
            if attempt == attempts - 1:
                raise ToolError(
                    f"{url} returned HTTP {response.status_code} after {attempts} attempts."
                )
        time.sleep(_retry_delay(ctx, attempt, response))
    raise ToolError(f"Could not fetch {url}.")  # unreachable: the loop always returns or raises
