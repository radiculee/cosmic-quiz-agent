"""Shared types for tools: the run context they read and write, the tool wrapper, and HTTP.

Every request a tool makes goes through `http_get`, which only ever contacts allow-listed hosts:
the URL is checked before it is requested, and redirects are followed here rather than by the
HTTP client, so each hop is checked before it is requested too (docs/SECURITY_AUDIT.md S4).
"""

from __future__ import annotations

import posixpath
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

import httpx2

from agent.config import Settings
from agent.llm import JsonObject, ToolSpec
from agent.verify import normalize_url

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_RETRY_AFTER_SECONDS = 5.0
# Redirects followed for one request, each to an allowed host. Real pages need one or two.
MAX_REDIRECTS = 5


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

    def host_allowed(self, url: str) -> bool:
        """Whether a request may go to this URL at all: https on the default port, to an
        allow-listed domain or one of its subdomains. Checked before every request and every
        redirect."""
        return self._allowed_domain(url) is not None

    def is_allowed(self, url: str) -> bool:
        """Whether fetch_page may read this page: an allowed host and, where the domain limits
        paths (arXiv: abstract pages only), a path inside them as the server would read it."""
        domain = self._allowed_domain(url)
        if domain is None:
            return False
        prefixes = self.settings.allowed_path_prefixes.get(domain)
        return prefixes is None or resolved_path(urlsplit(url).path).startswith(prefixes)

    def _allowed_domain(self, url: str) -> str | None:
        """The allow-listed domain this URL is on, or None if it may not be requested."""
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not host:
            return None
        try:
            port = parts.port
        except ValueError:  # not a number, or out of range
            return None
        if port not in (None, 443):
            return None
        for domain in self.settings.allowed_domains:
            if host == domain or host.endswith("." + domain):
                return domain
        return None


def resolved_path(path: str) -> str:
    """A URL path as a server reads it: percent-escapes decoded and dot segments resolved, so
    "/abs/../list" and "/abs/%2e%2e/list" are both "/list"."""
    return posixpath.normpath(unquote(path)) if path else "/"


ToolHandler = Callable[[JsonObject, ToolContext], str]


@dataclass(frozen=True)
class Tool:
    spec: ToolSpec
    run: ToolHandler


def make_http_client(settings: Settings) -> httpx2.Client:
    # Redirects are followed by `http_get`, which checks each hop against the allow-list first.
    return httpx2.Client(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=False,
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
    """GET an allow-listed URL, following up to MAX_REDIRECTS redirects to allowed hosts.

    The URL and each redirect's target are checked with `ToolContext.host_allowed` before they
    are requested, so no request ever reaches a host off the allow-list. A refused URL or hop,
    too many redirects, any other non-success status, or running out of retries raises
    ToolError, so the model is told what went wrong and can try something else.
    """
    if not ctx.host_allowed(url):
        raise ToolError(f"{url} is not on the allow-list.")
    response = _get_with_retries(ctx, url, params)
    hops = 0
    while response.is_redirect:
        if hops == MAX_REDIRECTS:
            raise ToolError(f"{url} redirected more than {MAX_REDIRECTS} times.")
        try:
            target = str(response.url.join(response.headers["location"]))
        except (httpx2.InvalidURL, ValueError) as error:
            raise ToolError(f"{url} redirected to an address that is not a URL.") from error
        if not ctx.host_allowed(target):
            raise ToolError(f"{url} redirected to {target}, which is not on the allow-list.")
        hops += 1
        response = _get_with_retries(ctx, target, None)
    return response


def _get_with_retries(
    ctx: ToolContext, url: str, params: Mapping[str, str] | None
) -> httpx2.Response:
    """One GET, retried on rate limits, server errors and network failures. A redirect is
    returned as it is, for `http_get` to check."""
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
