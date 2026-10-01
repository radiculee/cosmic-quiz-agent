"""Wikipedia search and article text, via the public MediaWiki Action API (no key needed)."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.llm import JsonObject, ToolSpec
from agent.tools.base import Tool, ToolContext, ToolError, http_get

SEARCH_HOST = "en.wikipedia.org"
MAX_RESULTS = 5

_TAG = re.compile(r"<[^>]+>")
# Reference sections add tokens without adding facts the agent can use.
_TRAILING_SECTIONS = re.compile(
    r"\n=+\s*(See also|References|Notes|Footnotes|Citations|Sources|Bibliography|"
    r"Further reading|External links)\s*=+",
    re.IGNORECASE,
)


class _SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=200)


def _api_get(ctx: ToolContext, host: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"https://{host}/w/api.php"
    response = http_get(ctx, url, {**params, "format": "json", "formatversion": "2"})
    try:
        data = response.json()
    except ValueError as error:
        raise ToolError("Wikipedia returned a response that was not JSON.") from error
    if not isinstance(data, dict):
        raise ToolError("Wikipedia returned an unexpected response.")
    return data


def article_url(host: str, title: str) -> str:
    return f"https://{host}/wiki/{quote(title.replace(' ', '_'), safe='()_,')}"


def parse_article_url(url: str) -> tuple[str, str] | None:
    """Return (host, title) for a Wikipedia article URL, or None if it is not one."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not (host == "wikipedia.org" or host.endswith(".wikipedia.org")):
        return None
    if not parts.path.startswith("/wiki/") or len(parts.path) <= len("/wiki/"):
        return None
    title = unquote(parts.path[len("/wiki/") :]).replace("_", " ")
    return host, title


def search_wikipedia(arguments: JsonObject, ctx: ToolContext) -> str:
    try:
        args = _SearchArgs.model_validate(arguments)
    except ValidationError as error:
        raise ToolError(f"Invalid arguments: {error}") from error

    data = _api_get(
        ctx,
        SEARCH_HOST,
        {
            "action": "query",
            "list": "search",
            "srsearch": args.query,
            "srlimit": str(MAX_RESULTS),
            "srprop": "snippet",
        },
    )
    results = data.get("query", {}).get("search", [])
    if not results:
        return f"No Wikipedia articles found for {args.query!r}. Try a different query."

    lines = [f"Wikipedia results for {args.query!r}:"]
    for index, result in enumerate(results, start=1):
        title = str(result.get("title", ""))
        snippet = html.unescape(_TAG.sub("", str(result.get("snippet", ""))))
        lines.append(f"{index}. {title}\n   URL: {article_url(SEARCH_HOST, title)}\n   {snippet}")
    lines.append("Use fetch_page on a URL to read the article. Search results cannot be cited.")
    return "\n".join(lines)


def fetch_article(host: str, title: str, ctx: ToolContext) -> tuple[str, str, str]:
    """Fetch an article as plain text. Returns (canonical_url, title, text)."""
    data = _api_get(
        ctx,
        host,
        {
            "action": "query",
            "prop": "extracts",
            "explaintext": "1",
            "redirects": "1",
            "titles": title,
        },
    )
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or not pages[0].get("extract"):
        raise ToolError(f"Wikipedia has no article titled {title!r}.")

    page = pages[0]
    canonical_title = str(page.get("title", title))
    text = str(page["extract"])
    match = _TRAILING_SECTIONS.search(text)
    if match:
        text = text[: match.start()]
    return article_url(host, canonical_title), canonical_title, text.strip()


SEARCH_WIKIPEDIA = Tool(
    spec=ToolSpec(
        name="search_wikipedia",
        description=(
            "Search English Wikipedia. Returns up to 5 article titles with URLs and short "
            "snippets. Snippets are for choosing what to read; they cannot be cited. "
            "Call fetch_page on a result URL to read the article."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms, for example 'Neutron star formation'.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    run=search_wikipedia,
)
