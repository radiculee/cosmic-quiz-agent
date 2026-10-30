"""GET /api/topics: every topic in the bank at every level, with the modes and difficulties.

Learn and Quiz list a topic only once both modes are published at all three difficulties
(decided 2026-10-28), so each level offers the same topics. A topic still missing a level is
left out until `python -m curator complete` or `daily` fills it; a live search still finds it
(agent/ondemand.py reads the bank directly).

Each topic also carries a picture with its credit (`image`) or a fact (`fact`), once
`python -m curator.images` has chosen one (migration 012, decided 2026-10-30). Both are additive:
a topic without either, or a bank that has not had the migration yet, is listed as before.

The UI uses the list to suggest topics as the player types, to pick a random one and to draw the
topic cards.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, TypeAdapter

from agent.bank import BankReader, BankTopic, TopicFact, TopicImage
from agent.rest import RETRIES, RestClient, StoreError, parse
from agent.web import ApiRequest, ApiResponse, error_response, json_response, make_app

# The bank changes at most once a day (the Curator), so a short edge cache is safe.
CACHE_SECONDS = 300
# vercel.json rewrites /media/* to the public Storage bucket `topic-images`, so a visitor's
# browser only ever contacts this site for a picture.
MEDIA_PREFIX = "/media/"

# Named columns only: the browser roles may not read `locked` or `notes` (migration 012).
_MEDIA_COLUMNS = (
    "kind,card_path,card_width,card_height,preview_path,source,licence_name,licence_url,"
    "file_page_url,credit,category,fact,topics!inner(name)"
)


class _TopicName(BaseModel):
    name: str


class _MediaRow(BaseModel):
    kind: Literal["image", "fact"]
    card_path: str | None = None
    card_width: int | None = None
    card_height: int | None = None
    preview_path: str | None = None
    source: Literal["wikipedia", "nasa"] | None = None
    licence_name: str | None = None
    licence_url: str | None = None
    file_page_url: str | None = None
    credit: str | None = None
    category: str | None = None
    fact: str | None = None
    topics: _TopicName


_MEDIA_ROWS = TypeAdapter(list[_MediaRow])


def with_media(topic: BankTopic, row: _MediaRow | None) -> BankTopic:
    """The topic with its picture or fact, if the row has a complete one."""
    if row is None:
        return topic
    if (
        row.kind == "image"
        and row.card_path
        and row.card_width
        and row.card_height
        and row.source
        and row.licence_name
        and row.file_page_url
        and row.credit
    ):
        image = TopicImage(
            src=MEDIA_PREFIX + row.card_path,
            width=row.card_width,
            height=row.card_height,
            preview=MEDIA_PREFIX + row.preview_path if row.preview_path else None,
            credit=row.credit,
            licence=row.licence_name,
            licence_url=row.licence_url,
            page_url=row.file_page_url,
            source=row.source,
        )
        return topic.model_copy(update={"image": image})
    if row.kind == "fact" and row.category and row.fact:
        return topic.model_copy(update={"fact": TopicFact(category=row.category, text=row.fact)})
    return topic


def fetch_media(rest: RestClient) -> dict[str, _MediaRow]:
    """Every topic's picture or fact row, by topic name."""
    reply = rest.send(
        "GET",
        "/topic_images",
        params={"select": _MEDIA_COLUMNS, "limit": "1000"},
        retries=RETRIES,
    )
    return {row.topics.name: row for row in parse(_MEDIA_ROWS, reply, "reading topic images")}


def read_media() -> dict[str, _MediaRow]:
    """`fetch_media` with the publishable key. Empty if the bank cannot be read or has no
    `topic_images` table yet: pictures are an addition, and their absence must not take the
    topic list down with it."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not url or not key:
        return {}
    try:
        with RestClient(url, key) as rest:
            return fetch_media(rest)
    except StoreError:
        return {}


def handle(request: ApiRequest) -> ApiResponse:
    if request.method != "GET":
        return error_response(405, "Use GET.")
    try:
        with BankReader.from_env() as bank:
            topics = bank.topics()
    except StoreError:
        return error_response(503, "The question bank is not reachable right now.")
    media = read_media()
    body = {
        "topics": [
            with_media(topic, media.get(topic.name)).model_dump(mode="json", exclude_none=True)
            for topic in topics
            if topic.complete
        ]
    }
    return json_response(body, cache_seconds=CACHE_SECONDS)


app = make_app(handle)
