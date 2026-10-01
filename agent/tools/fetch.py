"""fetch_page: read a page from an allow-listed domain as plain text.

Every successful fetch is recorded in the run context, which is what makes a URL citable.
Wikipedia articles go through the MediaWiki API for clean text; other pages are fetched as HTML
and reduced to their headings, paragraphs and list items.
"""

from __future__ import annotations

from html.parser import HTMLParser

import httpx2
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.llm import JsonObject, ToolSpec
from agent.tools.base import Tool, ToolContext, ToolError
from agent.tools.wikipedia import fetch_article, parse_article_url

_MAX_HTML_BYTES = 2_000_000


class _FetchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2000)


class _TextExtractor(HTMLParser):
    """Collects readable text from HTML, skipping navigation, scripts and page chrome.

    Blocks inside <main> or <article> are kept separately; when a page has them, only those are
    used, which drops menus that sit outside a <nav> element.
    """

    _SKIP = frozenset(
        {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form"}
    )
    _BLOCKS = frozenset({"p", "h1", "h2", "h3", "h4", "li", "blockquote", "figcaption"})
    _MAIN = frozenset({"main", "article"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._all_blocks: list[str] = []
        self._main_blocks: list[str] = []
        self._skip_depth = 0
        self._block_depth = 0
        self._main_depth = 0
        self._in_title = False
        self._current: list[str] = []

    @property
    def blocks(self) -> list[str]:
        return self._main_blocks or self._all_blocks

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._MAIN:
            self._main_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self._BLOCKS and self._skip_depth == 0:
            self._block_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in self._MAIN and self._main_depth > 0:
            self._main_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self._BLOCKS and self._block_depth > 0:
            self._block_depth -= 1
            if self._block_depth == 0:
                text = " ".join("".join(self._current).split())
                if text:
                    self._all_blocks.append(text)
                    if self._main_depth > 0:
                        self._main_blocks.append(text)
                self._current = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0 and self._block_depth > 0:
            self._current.append(data)


def _fetch_html(url: str, ctx: ToolContext) -> tuple[str, str, str]:
    """Fetch an HTML page. Returns (final_url, title, text)."""
    try:
        response = ctx.http.get(url)
        response.raise_for_status()
    except httpx2.HTTPError as error:
        raise ToolError(f"Could not fetch {url}: {error}") from error

    final_url = str(response.url)
    if not ctx.is_allowed(final_url):
        raise ToolError(f"{url} redirected to {final_url}, which is not on the allow-list.")
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type:
        raise ToolError(f"{url} is not an HTML page (content type {content_type!r}).")

    extractor = _TextExtractor()
    extractor.feed(response.text[:_MAX_HTML_BYTES])
    text = "\n\n".join(extractor.blocks)
    if not text:
        raise ToolError(f"No readable text found at {url}.")
    return final_url, " ".join(extractor.title.split()), text


def fetch_page(arguments: JsonObject, ctx: ToolContext) -> str:
    try:
        args = _FetchArgs.model_validate(arguments)
    except ValidationError as error:
        raise ToolError(f"Invalid arguments: {error}") from error

    url = args.url.strip()
    if not ctx.is_allowed(url):
        allowed = ", ".join(ctx.settings.allowed_domains)
        raise ToolError(f"{url} is not allowed. Only https pages on these domains: {allowed}.")

    article = parse_article_url(url)
    if article is not None:
        final_url, title, text = fetch_article(*article, ctx)
    else:
        final_url, title, text = _fetch_html(url, ctx)

    limit = ctx.settings.max_page_chars
    truncated = len(text) > limit
    text = text[:limit]
    # Record exactly the text the model sees, under both the requested and the final URL.
    ctx.record_fetch(text, url, final_url)

    note = "\n\n[Page truncated.]" if truncated else ""
    return f"URL: {final_url}\nTitle: {title}\n\n{text}{note}"


FETCH_PAGE = Tool(
    spec=ToolSpec(
        name="fetch_page",
        description=(
            "Read a web page as plain text. Only https pages on allow-listed domains work "
            "(Wikipedia, NASA, ESA). Only pages read with this tool can be cited; cite the URL "
            "shown on the 'URL:' line of the result."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full https URL of the page."},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    ),
    run=fetch_page,
)
