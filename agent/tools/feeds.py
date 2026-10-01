"""fetch_feed: the latest items from NASA and ESA news feeds (RSS, no key needed).

Feed items are leads, not sources: an item becomes citable once fetch_page reads its link. The
webbtelescope.org and hubblesite.org feeds now redirect to NASA pages without RSS, so Webb and
Hubble news comes from ESA's esawebb.org and esahubble.org feeds and NASA's science feed.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from agent.llm import JsonObject, ToolSpec
from agent.tools.base import Tool, ToolContext, ToolError, http_get

FeedName = Literal["nasa_news", "nasa_science", "esa_space_science", "esa_webb", "esa_hubble"]

FEEDS: dict[FeedName, tuple[str, str]] = {
    "nasa_news": ("NASA news releases", "https://www.nasa.gov/news-release/feed/"),
    "nasa_science": ("NASA Science", "https://science.nasa.gov/feed/"),
    "esa_space_science": (
        "ESA Space Science",
        "https://www.esa.int/rssfeed/Our_Activities/Space_Science",
    ),
    "esa_webb": ("ESA/Webb news", "https://esawebb.org/news/feed/"),
    "esa_hubble": ("ESA/Hubble news", "https://esahubble.org/news/feed/"),
}

MAX_ITEMS = 10
_SUMMARY_CHARS = 250
_TAG = re.compile(r"<[^>]+>")
_MISSING_ATTRIBUTE_SPACE = re.compile(r'"xmlns:')


class _FeedArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feed: FeedName


class FeedItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    link: str
    published: str
    summary: str


def _clean(text: str | None) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", text or "")).split())


def _repair(xml_text: str) -> str:
    """Fix a known publisher bug: science.nasa.gov's feed omits the space between two xmlns
    attributes on the root element, which makes the whole document invalid XML."""
    return _MISSING_ATTRIBUTE_SPACE.sub('" xmlns:', xml_text)


def parse_rss(xml_text: str) -> list[FeedItem]:
    try:
        root = ET.fromstring(_repair(xml_text))
    except ET.ParseError as error:
        raise ToolError("The feed was not valid XML.") from error

    items: list[FeedItem] = []
    for item in root.iter("item"):
        link = _clean(item.findtext("link"))
        if not link:
            continue
        items.append(
            FeedItem(
                title=_clean(item.findtext("title")),
                link=link,
                published=_clean(item.findtext("pubDate")),
                summary=_clean(item.findtext("description"))[:_SUMMARY_CHARS],
            )
        )
    return items


def fetch_feed(arguments: JsonObject, ctx: ToolContext) -> str:
    try:
        args = _FeedArgs.model_validate(arguments)
    except ValidationError as error:
        names = ", ".join(FEEDS)
        raise ToolError(f"Invalid arguments, feed must be one of: {names}. {error}") from error

    label, url = FEEDS[args.feed]
    items = parse_rss(http_get(ctx, url).text)[:MAX_ITEMS]
    if not items:
        return f"The {label} feed has no items right now."

    lines = [f"Latest items from {label}:"]
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item.title} ({item.published})\n   URL: {item.link}")
        if item.summary:
            lines.append(f"   {item.summary}")
    lines.append("Feed items cannot be cited: call fetch_page on an item URL to read it.")
    return "\n".join(lines)


FETCH_FEED = Tool(
    spec=ToolSpec(
        name="fetch_feed",
        description=(
            "List the latest news items from a NASA or ESA feed: nasa_news (NASA news "
            "releases), nasa_science (NASA Science), esa_space_science (ESA space science), "
            "esa_webb (James Webb Space Telescope), esa_hubble (Hubble). Use it for recent "
            "discoveries. Items are leads only: call fetch_page on an item URL before citing it."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "feed": {"type": "string", "enum": list(FEEDS)},
            },
            "required": ["feed"],
            "additionalProperties": False,
        },
    ),
    run=fetch_feed,
)
