"""NASA sources: Astronomy Picture of the Day and the NASA Image and Video Library (no key needed).

APOD moved to science.nasa.gov in 2026 and its JSON API now returns placeholders, so `nasa_apod`
reads the dated page (apod.nasa.gov/apod/apYYMMDD.html). Older dates redirect to their permanent
science.nasa.gov article; recent dates redirect to the landing page, so the article is found from
the landing page's links instead.

Image library records are read from the official images API; each record's text is what its
images.nasa.gov page shows, so the record is citable under that URL.
"""

from __future__ import annotations

import html
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from agent.llm import JsonObject, ToolSpec
from agent.tools.base import Tool, ToolContext, ToolError, http_get
from agent.tools.fetch import fetch_html, html_page, record_and_format

APOD_FIRST_DAY = date(1995, 6, 16)
APOD_LANDING_PATH = "/apod"
IMAGES_API_URL = "https://images-api.nasa.gov/search"
MAX_IMAGE_RESULTS = 5
_MAX_DESCRIPTION_CHARS = 700
_TAG = re.compile(r"<[^>]+>")


class _ApodArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str

    @field_validator("date")
    @classmethod
    def _valid_date(cls, value: str) -> str:
        value = value.strip().lower()
        if value == "today":
            return value
        try:
            day = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("use YYYY-MM-DD or 'today'") from error
        if not APOD_FIRST_DAY <= day <= datetime.now(UTC).date():
            raise ValueError(f"APOD dates run from {APOD_FIRST_DAY.isoformat()} to today")
        return value


class _ImageSearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=200)


def apod_url(day: date) -> str:
    return f"https://apod.nasa.gov/apod/ap{day:%y%m%d}.html"


def _find_recent_article(day: date, landing_html: str) -> str | None:
    """Find a recent day's permanent article link on the APOD landing page.

    Recent dated URLs redirect to the landing page instead of their article, but the landing page
    links to recent articles, whose slugs start with apod-<year>-<month>-<day>.
    """
    month = day.strftime("%B").lower()
    pattern = re.compile(
        rf"https://science\.nasa\.gov/image-article/apod-{day.year}-{month}-0?{day.day}-"
        r"[a-z0-9\-]+/"
    )
    match = pattern.search(landing_html)
    return match.group(0) if match else None


def _read_apod_day(day: date, ctx: ToolContext) -> str | None:
    """Read one day's APOD article, or None if no permanent article can be found for that day."""
    requested = apod_url(day)
    response = http_get(ctx, requested)
    if urlsplit(str(response.url)).path.rstrip("/") != APOD_LANDING_PATH:
        final_url, title, text = html_page(requested, response, ctx)
        return record_and_format(ctx, requested, final_url, title, text)

    # Landed on the landing page, which changes daily and cannot be cited: find the article.
    article_url = _find_recent_article(day, response.text)
    if article_url is None:
        return None
    final_url, title, text = fetch_html(article_url, ctx)
    return record_and_format(ctx, article_url, final_url, title, text)


def nasa_apod(arguments: JsonObject, ctx: ToolContext) -> str:
    try:
        args = _ApodArgs.model_validate(arguments)
    except ValidationError as error:
        raise ToolError(f"Invalid arguments: {error}") from error

    if args.date == "today":
        # APOD publishes on US Eastern time, so today's entry may not exist yet in UTC terms.
        today = datetime.now(UTC).date()
        for day in (today, today - timedelta(days=1)):
            page = _read_apod_day(day, ctx)
            if page is not None:
                return page
        raise ToolError("Could not find a recent APOD entry. Try a specific date.")

    page = _read_apod_day(date.fromisoformat(args.date), ctx)
    if page is None:
        raise ToolError(
            f"No APOD entry could be read for {args.date}. Since APOD moved to "
            "science.nasa.gov, recent dates other than today cannot be looked up by date; use "
            "'today' or another source."
        )
    return page


def _clean(text: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", text)).split())


def search_nasa_images(arguments: JsonObject, ctx: ToolContext) -> str:
    try:
        args = _ImageSearchArgs.model_validate(arguments)
    except ValidationError as error:
        raise ToolError(f"Invalid arguments: {error}") from error

    response = http_get(
        ctx,
        IMAGES_API_URL,
        {"q": args.query, "media_type": "image", "page_size": str(MAX_IMAGE_RESULTS)},
    )
    try:
        items: list[dict[str, Any]] = response.json()["collection"]["items"]
    except (ValueError, KeyError, TypeError) as error:
        raise ToolError("The NASA image library returned an unexpected response.") from error

    blocks: list[str] = []
    for item in items[:MAX_IMAGE_RESULTS]:
        data = (item.get("data") or [{}])[0]
        nasa_id = str(data.get("nasa_id", "")).strip()
        if not nasa_id:
            continue
        url = f"https://images.nasa.gov/details/{nasa_id}"
        title = _clean(str(data.get("title", "")))
        created = str(data.get("date_created", ""))[:10]
        center = _clean(str(data.get("center", "")))
        description = _clean(str(data.get("description", "")))[:_MAX_DESCRIPTION_CHARS]
        text = f"{title}\nCreated: {created} ({center})\n\n{description}"
        ctx.record_fetch(text, url)
        blocks.append(f"URL: {url}\n{text}")

    if not blocks:
        return f"No NASA images found for {args.query!r}."
    header = (
        f"NASA image library records for {args.query!r}. Each record is citable by its URL.\n\n"
    )
    return header + "\n\n---\n\n".join(blocks)


NASA_APOD = Tool(
    spec=ToolSpec(
        name="nasa_apod",
        description=(
            "Read NASA's Astronomy Picture of the Day for a date: the title and the "
            "astronomer-written explanation. The result is citable by its 'URL:' line."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "A date as YYYY-MM-DD (from 1995-06-16), or 'today'.",
                },
            },
            "required": ["date"],
            "additionalProperties": False,
        },
    ),
    run=nasa_apod,
)

SEARCH_NASA_IMAGES = Tool(
    spec=ToolSpec(
        name="search_nasa_images",
        description=(
            "Search the NASA Image and Video Library. Returns up to 5 image records with their "
            "official descriptions; each record is citable by its URL. Useful for missions, "
            "spacecraft and specific observed objects."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to look for, for example 'Crab Nebula Hubble'.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    run=search_nasa_images,
)
