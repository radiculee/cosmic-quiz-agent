"""Topic images: a credited picture for every topic card, or a fact card where none fits.

python -m curator.images [--dry-run] [--topic NAME] [--refresh] [--pause SECONDS]

Decided 2026-10-30 (docs/SESSIONS.md, Decisions). The fill is code only: it makes no model calls
and costs nothing. For each topic in the bank it looks for a picture, in this order:

1. The lead image of each Wikipedia page the topic's published items cite (best match first).
   The file's licence is read from the Wikimedia API (`extmetadata`) and only public domain, CC0,
   CC BY and CC BY-SA are accepted. Anything else, or anything unclear, is turned down and the
   reason is kept in `topic_images.notes`.
2. A result of the NASA Image and Video Library. It has no licence field, so a result is accepted
   only if every credit it names is NASA's or a NASA partner's and nothing in it claims copyright;
   NASA's media guidelines make its own images free to reuse.
3. Otherwise a fact card: a category for the card's art and one sentence from the topic's
   published explanation, chosen by rules in code. A fact can be replaced by hand (set `locked`).

A picture is cut to 16:9, resized and saved as WebP, once at 640 px wide for the card (about
40 KB) and, when the source is big enough, once at 1200 x 630 for link previews. The files go into
the public Storage bucket `topic-images` under names that contain a hash of their content. The
site serves them from its own address (`/media/*`, vercel.json), so a visitor's browser never
contacts Wikimedia, NASA or Supabase for a picture.

--dry-run reads the bank and the picture sources and prints each choice (picture, licence,
credit, sizes) without uploading or writing anything. A topic that already has a picture is
left alone unless --refresh is given; one that only has a fact is tried again, so a new source
page or a loosened rule can still find it a picture. A `locked` row is never replaced.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import os
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from typing import Literal
from urllib.parse import unquote, urlsplit

import httpx2
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, TypeAdapter

from agent.config import load_settings
from agent.console import slugify, use_utf8_output
from agent.rest import RETRIES, RestClient, StoreError, parse

BUCKET = "topic-images"

# --- Sizes ------------------------------------------------------------------------------------

CARD_WIDTH = 640
CARD_HEIGHT = 360  # 16:9
PREVIEW_WIDTH = 1200
PREVIEW_HEIGHT = 630  # the shape link previews use
CARD_TARGET_BYTES = 40_000
CARD_MAX_BYTES = 60_000
PREVIEW_MAX_BYTES = 120_000
MIN_QUALITY = 40
QUALITY_STEP = 5
START_QUALITY = 85
# A source that is much taller or wider than the card would lose most of itself to the crop.
MIN_ASPECT = 0.8
MAX_ASPECT = 2.5
MAX_DOWNLOAD_BYTES = 15_000_000
# Pictures are asked for at this width, so no original of many megapixels is ever downloaded.
SOURCE_WIDTH = 1280
# Transparent pictures are laid on the card colour (--surface).
BACKGROUND = (13, 17, 23)

# --- Where pictures come from ------------------------------------------------------------------

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
NASA_SEARCH = "https://images-api.nasa.gov/search"
NASA_DETAILS = "https://images.nasa.gov/details/"
ALLOWED_HOSTS = frozenset(
    {
        "en.wikipedia.org",
        "upload.wikimedia.org",
        "thumb.wikimedia.org",
        "images-api.nasa.gov",
        "images-assets.nasa.gov",
    }
)
MAX_WIKIPEDIA_PAGES = 3
MAX_NASA_RESULTS = 8
# A TIFF original is fine: the 1280 px rendition Commons serves for it is a JPEG or PNG.
RASTER_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/tiff"})
# NASA renditions in the order we prefer them: 1280 px wide first.
NASA_SIZES = ("~medium.", "~large.", "~small.")
# A NASA credit passes if it names one of these. ESO, a university or a photographer alone does
# not: those images are not covered by NASA's media guidelines.
NASA_CREDIT_WORDS = ("nasa", "jpl", "gsfc", "goddard", "stsci", "usgs", "cxc", "caltech", "csa")
_COPYRIGHT_MARKERS = (
    "©",
    "copyright",
    "(c)",
    "all rights reserved",
    "permission",
    "licensed",
)

Source = Literal["wikipedia", "nasa"]


class ImageRejectedError(Exception):
    """A picture was looked at and turned down; the message says why (kept in `notes`)."""


class FetchError(Exception):
    """A picture source could not be reached. Unlike a rejection this says nothing about the
    picture, so the topic is left as it was and tried again on the next run."""


# --- Reading pages and files ------------------------------------------------------------------

_TAGS = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")
MAX_AUTHOR_CHARS = 150


def plain_text(markup: str) -> str:
    """Text without tags or character references, on one line."""
    return _SPACES.sub(" ", html.unescape(_TAGS.sub(" ", markup))).strip()


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rsplit(" ", 1)[0].rstrip(",;:") + "..."


# --- Licences ---------------------------------------------------------------------------------


class Licence(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    url: str | None


_PUBLIC_DOMAIN = re.compile(r"^(public domain|pd)\b")
_CC0 = re.compile(r"^(cc0|cc zero)\b")
# CC BY or CC BY-SA, any version, with the IGO or a country suffix some versions carry. NC and ND
# variants have another word after "by" and so never match.
_CC_BY = re.compile(r"^cc by( sa)? (\d\.\d)( igo)?( [a-z]{2,3})?$")
_UNKNOWN_AUTHORS = ("unknown", "anonymous", "n/a")


def _normalized(name: str) -> str:
    return _SPACES.sub(" ", name.lower().replace("-", " ").replace("_", " ")).strip()


def licence_of(meta: Mapping[str, str]) -> Licence:
    """The licence a Commons file is offered under, or ImageRejectedError.

    `meta` is the file's `extmetadata`, one string per key. Public domain, CC0, CC BY and
    CC BY-SA (any version) are accepted. A file flagged non-free or with restrictions (a
    trademark, a person's likeness) is turned down whatever its licence says.
    """
    name = plain_text(meta.get("LicenseShortName", ""))
    if not name:
        raise ImageRejectedError("no licence name")
    if meta.get("NonFree", "").strip().lower() in ("true", "1", "yes"):
        raise ImageRejectedError("marked non-free")
    if meta.get("Restrictions", "").strip():
        raise ImageRejectedError(f"restrictions: {plain_text(meta['Restrictions'])}")
    key = _normalized(name)
    given_url = meta.get("LicenseUrl", "").strip() or None
    if _CC0.match(key):
        return Licence(
            name=name, url=given_url or "https://creativecommons.org/publicdomain/zero/1.0/"
        )
    if _PUBLIC_DOMAIN.match(key):
        return Licence(name=name, url=given_url)
    match = _CC_BY.match(key)
    if match:
        share_alike = "-sa" if match.group(1) else ""
        url = given_url or f"https://creativecommons.org/licenses/by{share_alike}/{match.group(2)}/"
        return Licence(name=name, url=url)
    raise ImageRejectedError(f"licence not accepted: {name}")


_TRAILING_LICENCE = re.compile(
    r"(?:[,;(]\s*|\s+-\s+)(?:cc[ -]by|creative commons)[^,;]*\)?\s*$", re.IGNORECASE
)


def _tidy_author(text: str) -> str:
    """An author as one clean phrase: no licence name left on the end (the credit line names the
    licence itself) and no stray space before a comma."""
    text = _TRAILING_LICENCE.sub("", plain_text(text)).strip(" ,;")
    return re.sub(r"\s+([,;])", r"\1", text)


def author_of(meta: Mapping[str, str], licence: Licence) -> str:
    """Who to credit. Commons' `Attribution` is the credit text the uploader asks for, so it
    comes first; `Artist` can carry extra notes. A licence that requires a credit cannot be used
    without a name."""
    for key in ("Attribution", "Artist"):
        text = _tidy_author(meta.get(key, ""))
        if text and not text.lower().startswith(_UNKNOWN_AUTHORS):
            return _shorten(text, MAX_AUTHOR_CHARS)
    needs_credit = meta.get("AttributionRequired", "").strip().lower() == "true" or (
        licence.name.lower().startswith("cc by")
    )
    if needs_credit:
        raise ImageRejectedError("the licence needs a credit but the file names no author")
    return "Unknown author"


def credit_line(author: str, licence_name: str, via: str) -> str:
    """The line shown with a picture: who made it, the licence and where it was found."""
    return f"{author}, {licence_name}, via {via}"


# --- Candidates -------------------------------------------------------------------------------


class Candidate(BaseModel):
    """A picture that passed the licence rules and is ready to download."""

    model_config = ConfigDict(frozen=True)

    source: Source
    download_url: str
    file_page_url: str
    author: str
    licence_name: str
    licence_url: str | None
    credit: str


class Fetcher:
    """GETs from the picture sources: a descriptive User-Agent, a pause between requests (the
    Wikimedia and NASA APIs ask for polite use), retries on rate limits and server errors, and
    a check that a request only ever goes to a known host."""

    def __init__(self, client: httpx2.Client, pause_seconds: float = 0.3) -> None:
        self._client = client
        self._pause = pause_seconds
        self._last = 0.0

    def _get(self, url: str, params: Mapping[str, str] | None) -> httpx2.Response:
        if urlsplit(url).hostname not in ALLOWED_HOSTS:
            raise FetchError(f"{url} is not a known picture host")
        for attempt in range(RETRIES + 1):
            wait = self._last + self._pause - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                response = self._client.get(url, params=params)
            except httpx2.HTTPError as error:
                self._last = time.monotonic()
                if attempt == RETRIES:
                    raise FetchError(f"{url}: {type(error).__name__}") from error
                time.sleep(2**attempt)
                continue
            self._last = time.monotonic()
            if response.status_code in (429, 500, 502, 503, 504) and attempt < RETRIES:
                retry_after = response.headers.get("retry-after", "")
                time.sleep(min(float(retry_after), 30.0) if retry_after.isdigit() else 2**attempt)
                continue
            if response.status_code >= 400:
                raise FetchError(f"{url}: HTTP {response.status_code}")
            if response.url.host not in ALLOWED_HOSTS:
                raise FetchError(f"{url} redirected to {response.url.host}")
            return response
        raise FetchError(f"{url}: no reply")  # unreachable: the last attempt returns or raises

    def json(self, url: str, params: Mapping[str, str] | None = None) -> object:
        try:
            return self._get(url, params).json()
        except ValueError as error:
            raise FetchError(f"{url}: the reply was not JSON") from error

    def image_bytes(self, url: str) -> bytes:
        data = self._get(url, None).content
        if len(data) > MAX_DOWNLOAD_BYTES:
            raise ImageRejectedError("the file is too large to fetch")
        return data


def _object(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _objects(value: object) -> list[dict[str, object]]:
    return [entry for entry in value if isinstance(entry, dict)] if isinstance(value, list) else []


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def wikipedia_candidate(fetcher: Fetcher, page_title: str) -> Candidate:
    """The lead image of an English Wikipedia page, if its licence allows reuse.

    Two calls to the same API: the page's lead image (`pageimages`), then that file's licence
    and a 1280 px rendition (`imageinfo`). The English Wikipedia API answers for Commons files
    too, so one host covers both.
    """
    pages = _objects(
        _object(
            _object(
                fetcher.json(
                    WIKIPEDIA_API,
                    {
                        "action": "query",
                        "format": "json",
                        "formatversion": "2",
                        "redirects": "1",
                        "prop": "pageimages",
                        "piprop": "name",
                        "titles": page_title,
                    },
                )
            ).get("query")
        ).get("pages")
    )
    file_name = _text(pages[0].get("pageimage")) if pages else ""
    if not file_name:
        raise ImageRejectedError(f"{page_title}: the page has no lead image")

    pages = _objects(
        _object(
            _object(
                fetcher.json(
                    WIKIPEDIA_API,
                    {
                        "action": "query",
                        "format": "json",
                        "formatversion": "2",
                        "prop": "imageinfo",
                        "iiprop": "url|size|mime|extmetadata",
                        "iiurlwidth": str(SOURCE_WIDTH),
                        "titles": f"File:{file_name}",
                    },
                )
            ).get("query")
        ).get("pages")
    )
    infos = _objects(pages[0].get("imageinfo")) if pages else []
    if not infos:
        raise ImageRejectedError(f"{file_name}: no file information")
    info = infos[0]
    if _text(info.get("mime")) not in RASTER_TYPES:
        raise ImageRejectedError(
            f"{file_name}: {_text(info.get('mime')) or 'unknown type'} is not a photo"
        )
    meta = {
        key: str(entry["value"])
        for key, entry in _object(info.get("extmetadata")).items()
        if isinstance(entry, dict) and "value" in entry
    }
    try:
        licence = licence_of(meta)
        author = author_of(meta, licence)
    except ImageRejectedError as rejection:
        raise ImageRejectedError(f"{file_name}: {rejection}") from rejection
    download = _text(info.get("thumburl")) or _text(info.get("url"))
    page_url = _text(info.get("descriptionurl"))
    if not download or not page_url:
        raise ImageRejectedError(f"{file_name}: no download address")
    via = "Wikimedia Commons" if _text(pages[0].get("imagerepository")) == "shared" else "Wikipedia"
    return Candidate(
        source="wikipedia",
        download_url=download,
        file_page_url=page_url,
        author=author,
        licence_name=licence.name,
        licence_url=licence.url,
        credit=credit_line(author, licence.name, via),
    )


_CREDIT_IN_TEXT = re.compile(
    r"\bcredits?\s*:\s*(.+?)(?=\s{2,}|\s+read more|\s+image\b|$)", re.IGNORECASE
)
_WORDS = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset({"the", "a", "an", "of", "and", "in", "on", "to", "for", "is", "how"})


def significant_words(name: str) -> list[str]:
    return [word for word in _WORDS.findall(name.lower()) if word not in _STOP_WORDS]


def nasa_credits(data: Mapping[str, object]) -> list[str]:
    """Every credit a NASA library entry names, in its fields and in its description."""
    credits = [plain_text(_text(data.get(key))) for key in ("photographer", "secondary_creator")]
    found = _CREDIT_IN_TEXT.findall(plain_text(_text(data.get("description"))))
    return [credit for credit in [*credits, *found] if credit]


def nasa_candidate(
    data: Mapping[str, object], links: Sequence[Mapping[str, object]], topic: str
) -> Candidate:
    """A library result that is about the topic, free of third-party credits, with a usable size."""
    nasa_id = _text(data.get("nasa_id"))
    title = plain_text(_text(data.get("title")))
    if _text(data.get("media_type")) != "image" or not nasa_id:
        raise ImageRejectedError(f"{nasa_id or title}: not an image")
    keywords = data.get("keywords")
    keyword_text = " ".join(str(word) for word in keywords) if isinstance(keywords, list) else ""
    about = f"{title} {keyword_text} {plain_text(_text(data.get('description')))}".lower()
    if not all(word in about for word in significant_words(topic)):
        raise ImageRejectedError(f"{nasa_id}: not clearly about {topic}")
    description = plain_text(_text(data.get("description"))).lower()
    if any(marker in description for marker in _COPYRIGHT_MARKERS):
        raise ImageRejectedError(f"{nasa_id}: the description mentions copyright or permission")
    credits = nasa_credits(data)
    for credit in credits:
        lowered = credit.lower()
        if any(marker in lowered for marker in _COPYRIGHT_MARKERS):
            raise ImageRejectedError(f"{nasa_id}: credit claims copyright: {credit}")
        if not any(word in lowered for word in NASA_CREDIT_WORDS):
            raise ImageRejectedError(f"{nasa_id}: credit is not NASA's: {credit}")
    download = ""
    for size in NASA_SIZES:
        download = next(
            (_text(link.get("href")) for link in links if size in _text(link.get("href"))), ""
        )
        if download:
            break
    if not download:
        raise ImageRejectedError(f"{nasa_id}: no usable size")
    author = _shorten(credits[0], MAX_AUTHOR_CHARS) if credits else "NASA"
    return Candidate(
        source="nasa",
        download_url=download.replace("http://", "https://", 1),
        file_page_url=f"{NASA_DETAILS}{nasa_id}",
        author=author,
        licence_name="Public domain",
        licence_url="https://www.nasa.gov/nasa-brand-center/images-and-media/",
        credit=credit_line(author, "Public domain", "NASA Image and Video Library"),
    )


# --- Resizing ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rendered:
    card: bytes
    preview: bytes | None


def _webp(image: Image.Image, target: int, limit: int) -> bytes:
    """The best-looking WebP at or under `target` bytes; the smallest one if none reaches it,
    provided it fits `limit`."""
    smallest = b""
    for quality in range(START_QUALITY, MIN_QUALITY - 1, -QUALITY_STEP):
        buffer = io.BytesIO()
        image.save(buffer, "WEBP", quality=quality, method=6)
        smallest = buffer.getvalue()
        if len(smallest) <= target:
            return smallest
    if len(smallest) > limit:
        raise ImageRejectedError(
            f"too detailed to fit {limit // 1000} KB ({len(smallest) // 1000} KB)"
        )
    return smallest


def render(data: bytes) -> Rendered:
    """Cut a picture to 16:9 and save the card (and, if it is big enough, the preview) as WebP."""
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ("JPEG", "PNG", "WEBP"):
                raise ImageRejectedError(f"{source.format} is not a photo format we use")
            source.load()
            picture = source.copy()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise ImageRejectedError(f"cannot read the file ({type(error).__name__})") from error
    width, height = picture.size
    if width < CARD_WIDTH or height < CARD_HEIGHT:
        raise ImageRejectedError(f"too small ({width} x {height})")
    if not MIN_ASPECT <= width / height <= MAX_ASPECT:
        raise ImageRejectedError(f"shape {width} x {height} would lose too much to the crop")
    if picture.mode in ("RGBA", "LA") or "transparency" in picture.info:
        rgba = picture.convert("RGBA")
        flat = Image.new("RGB", rgba.size, BACKGROUND)
        flat.paste(rgba, mask=rgba.getchannel("A"))
        picture = flat
    else:
        picture = picture.convert("RGB")
    card = _webp(
        ImageOps.fit(picture, (CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS),
        CARD_TARGET_BYTES,
        CARD_MAX_BYTES,
    )
    preview: bytes | None = None
    if width >= PREVIEW_WIDTH and height >= PREVIEW_HEIGHT:
        try:
            preview = _webp(
                ImageOps.fit(picture, (PREVIEW_WIDTH, PREVIEW_HEIGHT), Image.Resampling.LANCZOS),
                PREVIEW_MAX_BYTES,
                PREVIEW_MAX_BYTES,
            )
        except ImageRejectedError:
            preview = None  # the card is fine; link previews fall back to the site's own
    return Rendered(card=card, preview=preview)


def file_name(topic: str, data: bytes, kind: Literal["card", "preview"]) -> str:
    """A name that changes whenever the file does, so it can be cached for a year."""
    return f"{slugify(topic, 50)}-{hashlib.sha256(data).hexdigest()[:10]}-{kind}.webp"


# --- Fact cards -------------------------------------------------------------------------------

# Categories in priority order (a tie goes to the earlier one); the card's art is chosen from
# them. A keyword matches the start of a word, so "galax" covers galaxy and galaxies.
CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
    (category, tuple(words.split("|")))
    for category, words in (
        ("black-hole", "black hole|event horizon|singularit|accretion|hawking"),
        ("galaxy", "galax|milky way|andromeda|quasar|active galactic"),
        ("cosmology", "universe|big bang|dark matter|dark energy|cosmic|inflation|redshift"),
        ("particle", "particle|neutrino|quark|antimatter|atom|photon|boson|electron"),
        (
            "mission",
            "mission|spacecraft|probe|rover|lander|orbiter|telescope|satellite|launch|apollo|voyager",
        ),
        (
            "star",
            "star|stellar|supernova|nebula|sun|solar|pulsar|magnetar|neutron|dwarf|nova|fusion",
        ),
        ("planet", "planet|exoplanet|mars|venus|jupiter|saturn|mercury|neptune|uranus|earth|moon"),
        ("small-body", "comet|asteroid|meteor|kuiper|oort"),
    )
)
DEFAULT_CATEGORY = "space"
_NAME_WEIGHT = 5

MIN_FACT_CHARS = 50
MAX_FACT_CHARS = 170
IDEAL_FACT_CHARS = 100
_SENTENCES = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_DANGLING_START = re.compile(
    r"^(it|its|this|these|those|that|they|their|he|she|such)\b", re.IGNORECASE
)
_STRIKING = re.compile(
    r"\b(largest|smallest|first|hottest|coldest|fastest|brightest|oldest|densest|only|most|"
    r"billion|million|thousand|times)\b",
    re.IGNORECASE,
)


def _keyword_hits(text: str, keywords: Sequence[str]) -> int:
    lowered = text.lower()
    return sum(len(re.findall(r"\b" + re.escape(word), lowered)) for word in keywords)


def category_of(topic: str, texts: Sequence[str]) -> str:
    """The card's category: the one whose keywords appear most, a hit in the topic's name
    counting five times a hit in the explanations."""
    body = " ".join(texts)
    best, best_score = DEFAULT_CATEGORY, 0
    for category, keywords in CATEGORIES:
        score = _NAME_WEIGHT * _keyword_hits(topic, keywords) + _keyword_hits(body, keywords)
        if score > best_score:
            best, best_score = category, score
    return best


def _fact_score(sentence: str, topic_words: Sequence[str]) -> float:
    score = 0.0
    if re.search(r"\d", sentence):
        score += 3
    if _STRIKING.search(sentence):
        score += 2
    if any(word in sentence.lower() for word in topic_words):
        score += 1
    if _DANGLING_START.match(sentence):
        score -= 3
    if "(" in sentence or ";" in sentence:
        score -= 1
    return score - abs(len(sentence) - IDEAL_FACT_CHARS) / 50


def pick_fact(topic: str, texts: Sequence[str]) -> str | None:
    """One sentence that stands alone, taken word for word from the explanations (best first).

    A sentence of a sensible length wins on a number, a superlative or the topic's own words, and
    loses if it opens with a pronoun that points back to a sentence we are not showing. If none
    has a sensible length, the first sentence is cut at a word. None only if there is no text.
    """
    words = significant_words(topic)
    best: tuple[float, str] | None = None
    for text in texts:
        for sentence in _SENTENCES.split(_SPACES.sub(" ", text).strip()):
            if MIN_FACT_CHARS <= len(sentence) <= MAX_FACT_CHARS:
                score = _fact_score(sentence, words)
                if best is None or score > best[0]:
                    best = (score, sentence)
    if best is not None:
        return best[1]
    for text in texts:
        flat = _SPACES.sub(" ", text).strip()
        if flat:
            return _shorten(_SENTENCES.split(flat)[0], MAX_FACT_CHARS)
    return None


# --- What is stored ---------------------------------------------------------------------------


class TopicMedia(BaseModel):
    """What one `topic_images` row says (migration 012)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["image", "fact"]
    card_path: str | None = None
    card_width: int | None = None
    card_height: int | None = None
    preview_path: str | None = None
    source: Source | None = None
    author: str | None = None
    licence_name: str | None = None
    licence_url: str | None = None
    file_page_url: str | None = None
    credit: str | None = None
    category: str | None = None
    fact: str | None = None
    notes: str = ""

    @property
    def paths(self) -> list[str]:
        return [path for path in (self.card_path, self.preview_path) if path]


@dataclass
class Chosen:
    media: TopicMedia
    files: dict[str, bytes] = field(default_factory=dict)  # bucket path -> WebP bytes


class _SourceRow(BaseModel):
    url: str


class _ItemRow(BaseModel):
    mode: Literal["learn", "quiz"]
    difficulty: Literal["easy", "medium", "hard"]
    explanation: str
    sources: list[_SourceRow]


class TopicRow(BaseModel):
    """A topic with the published items to look for pictures and facts in."""

    id: int
    name: str
    items: list[_ItemRow]

    def explanations(self) -> list[str]:
        """The published explanations, learn before quiz and easier before harder."""
        levels = {"easy": 0, "medium": 1, "hard": 2}
        ranked = sorted(
            self.items, key=lambda item: (item.mode != "learn", levels[item.difficulty])
        )
        return [item.explanation for item in ranked]


def wikipedia_titles(topic: TopicRow) -> list[str]:
    """The English Wikipedia pages the topic's items cite, best first: the page named like the
    topic, then the most cited, at most MAX_WIKIPEDIA_PAGES."""
    counts: dict[str, int] = {}
    for item in topic.items:
        for source in item.sources:
            parts = urlsplit(source.url)
            if parts.hostname != "en.wikipedia.org" or not parts.path.startswith("/wiki/"):
                continue
            title = unquote(parts.path.removeprefix("/wiki/")).replace("_", " ")
            if title and ":" not in title:
                counts[title] = counts.get(title, 0) + 1
    wanted = " ".join(significant_words(topic.name))
    ranked = sorted(
        counts, key=lambda title: (" ".join(significant_words(title)) != wanted, -counts[title])
    )
    return ranked[:MAX_WIKIPEDIA_PAGES]


def choose_media(topic: TopicRow, fetcher: Fetcher) -> Chosen | None:
    """A picture for the topic, or a fact card if no source has an acceptable one.

    None if a source could not be reached and nothing was found: the topic is then left as it
    is, because a fact card would hide a picture that an outage kept from us.
    """
    notes: list[str] = []
    unreachable = False

    def attempt(label: str, make: Callable[[], Candidate]) -> Chosen | None:
        nonlocal unreachable
        try:
            candidate = make()
            rendered = render(fetcher.image_bytes(candidate.download_url))
        except ImageRejectedError as rejection:
            notes.append(f"{label}: {rejection}")
            return None
        except FetchError as error:
            unreachable = True
            notes.append(f"{label}: unreachable ({error})")
            return None
        return _chosen(topic.name, candidate, rendered)

    for title in wikipedia_titles(topic):
        found = attempt(f"wikipedia {title}", partial(wikipedia_candidate, fetcher, title))
        if found:
            return found
    for candidate in nasa_candidates(topic, fetcher, notes):
        found = attempt("nasa", _ready(candidate))
        if found:
            return found
    if unreachable:
        return None
    texts = topic.explanations()
    fact = pick_fact(topic.name, texts)
    if fact is None:
        return None
    media = TopicMedia(
        kind="fact", category=category_of(topic.name, texts), fact=fact, notes="; ".join(notes)
    )
    return Chosen(media=media)


def nasa_candidates(topic: TopicRow, fetcher: Fetcher, notes: list[str]) -> list[Candidate]:
    """One candidate per library result that is worth downloading. Results the rules turn down are
    noted here and not offered; a search that fails is noted and offers nothing."""
    try:
        reply = _object(
            fetcher.json(NASA_SEARCH, {"q": topic.name, "media_type": "image", "page_size": "10"})
        )
    except FetchError as error:
        notes.append(f"nasa: unreachable ({error})")
        return []
    entries = _objects(_object(reply.get("collection")).get("items"))
    makers: list[Candidate] = []
    for entry in entries[:MAX_NASA_RESULTS]:
        data = _object((_objects(entry.get("data")) or [{}])[0])
        links = _objects(entry.get("links"))
        try:
            candidate = nasa_candidate(data, links, topic.name)
        except ImageRejectedError as rejection:
            notes.append(f"nasa {rejection}")
            continue
        makers.append(candidate)
    return makers


def _ready(candidate: Candidate) -> Callable[[], Candidate]:
    return lambda: candidate


def _chosen(topic: str, candidate: Candidate, rendered: Rendered) -> Chosen:
    card_name = file_name(topic, rendered.card, "card")
    files = {card_name: rendered.card}
    preview_name: str | None = None
    if rendered.preview is not None:
        preview_name = file_name(topic, rendered.preview, "preview")
        files[preview_name] = rendered.preview
    media = TopicMedia(
        kind="image",
        card_path=card_name,
        card_width=CARD_WIDTH,
        card_height=CARD_HEIGHT,
        preview_path=preview_name,
        source=candidate.source,
        author=candidate.author,
        licence_name=candidate.licence_name,
        licence_url=candidate.licence_url,
        file_page_url=candidate.file_page_url,
        credit=candidate.credit,
    )
    return Chosen(media=media, files=files)


# --- The bank ---------------------------------------------------------------------------------


class ExistingRow(BaseModel):
    topic_id: int
    kind: Literal["image", "fact"]
    locked: bool
    card_path: str | None = None
    preview_path: str | None = None

    @property
    def paths(self) -> list[str]:
        return [path for path in (self.card_path, self.preview_path) if path]


_TOPIC_ROWS = TypeAdapter(list[TopicRow])
_EXISTING_ROWS = TypeAdapter(list[ExistingRow])


class MediaStore:
    """Reads topics and writes `topic_images` rows and Storage files with the secret key."""

    def __init__(self, rest: RestClient, http: httpx2.Client, url: str, key: str) -> None:
        self._rest = rest
        self._http = http
        self._storage = f"{url.rstrip('/')}/storage/v1/object"
        self._key = key

    @classmethod
    def from_env(cls) -> MediaStore:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        if not url or not key:
            raise StoreError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set")
        http = httpx2.Client(timeout=60.0)
        return cls(RestClient(url, key, client=http), http, url, key)

    def close(self) -> None:
        self._http.close()

    def topics(self) -> list[TopicRow]:
        """Every topic with a published item, with those items' explanations and sources."""
        rows = self._rest.read_all(
            "/topics",
            {
                "select": "id,name,items(mode,difficulty,explanation,sources(url))",
                "items.status": "eq.published",
                "order": "id.asc",
            },
        )
        return [topic for topic in parse(_TOPIC_ROWS, rows, "reading topics") if topic.items]

    def existing(self, *, table_may_be_missing: bool) -> dict[int, ExistingRow]:
        """The rows already written. A dry run may meet a bank that has not had migration 012
        yet; a real run may not."""
        try:
            rows = self._rest.read_all(
                "/topic_images",
                {"select": "topic_id,kind,locked,card_path,preview_path", "order": "topic_id.asc"},
            )
        except StoreError as error:
            if table_may_be_missing and error.status == 404:
                return {}
            raise
        return {row.topic_id: row for row in parse(_EXISTING_ROWS, rows, "reading topic images")}

    def upload(self, path: str, data: bytes) -> None:
        response = self._http.post(
            f"{self._storage}/{BUCKET}/{path}",
            content=data,
            headers={
                "apikey": self._key,
                "Content-Type": "image/webp",
                "Cache-Control": "max-age=31536000",
                "x-upsert": "true",
            },
        )
        if response.status_code >= 400:
            raise StoreError(
                f"uploading {path}: HTTP {response.status_code} {response.text}",
                response.status_code,
            )

    def remove(self, paths: Sequence[str]) -> None:
        """Delete files nothing points to any more. A failure only leaves an orphan, so it is
        reported by the caller and not raised."""
        for path in paths:
            response = self._http.delete(
                f"{self._storage}/{BUCKET}/{path}", headers={"apikey": self._key}
            )
            if response.status_code >= 400:
                raise StoreError(
                    f"removing {path}: HTTP {response.status_code}", response.status_code
                )

    def save(self, topic_id: int, media: TopicMedia) -> None:
        body = {
            "topic_id": topic_id,
            **media.model_dump(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self._rest.send(
            "POST",
            "/topic_images",
            json=body,
            params={"on_conflict": "topic_id"},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            retries=RETRIES,
        )


# --- The command line -------------------------------------------------------------------------


def describe(topic: str, chosen: Chosen) -> str:
    """One topic's choice as the dry run prints it."""
    media = chosen.media
    if media.kind == "fact":
        return (
            f'{topic}\n    FACT  {media.category}\n    "{media.fact}"\n'
            f"    turned down: {media.notes or 'nothing found'}"
        )
    sizes = ", ".join(
        f"{name.rsplit('-', 1)[1].split('.')[0]} {len(data) / 1000:.1f} KB"
        for name, data in chosen.files.items()
    )
    return (
        f"{topic}\n    IMAGE  {media.source}  {media.licence_name}\n"
        f"    credit: {media.credit}\n    page:   {media.file_page_url}\n    files:  {sizes}"
    )


@dataclass
class Tally:
    images: int = 0
    facts: int = 0
    skipped: int = 0
    unreachable: int = 0


def fill(
    store: MediaStore,
    fetcher: Fetcher,
    *,
    dry_run: bool,
    only: str | None,
    refresh: bool,
    out: Callable[[str], None] = print,
) -> Tally:
    """Choose (and, unless dry_run, save) a picture or fact for every topic that needs one."""
    tally = Tally()
    existing = store.existing(table_may_be_missing=dry_run)
    for topic in store.topics():
        if only is not None and topic.name.casefold() != only.casefold():
            continue
        row = existing.get(topic.id)
        if row is not None and (row.locked or (row.kind == "image" and not refresh)):
            tally.skipped += 1
            continue
        chosen = choose_media(topic, fetcher)
        if chosen is None:
            tally.unreachable += 1
            out(f"{topic.name}\n    left as it was: a source could not be reached")
            continue
        out(describe(topic.name, chosen))
        if chosen.media.kind == "image":
            tally.images += 1
        else:
            tally.facts += 1
        if dry_run:
            continue
        for path, data in chosen.files.items():
            store.upload(path, data)
        store.save(topic.id, chosen.media)
        if row is not None:
            stale = [path for path in row.paths if path not in chosen.media.paths]
            try:
                store.remove(stale)
            except StoreError as error:
                out(f"    could not remove an old file ({error}); it is only an orphan")
    return tally


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m curator.images", description=__doc__.split("\n")[0]
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the choices; upload and write nothing"
    )
    parser.add_argument("--topic", help="only this topic (matched ignoring case)")
    parser.add_argument(
        "--refresh", action="store_true", help="look again at topics that have a picture"
    )
    parser.add_argument(
        "--pause", type=float, default=0.3, help="seconds between requests to a picture source"
    )
    args = parser.parse_args(argv)
    use_utf8_output()
    settings = load_settings()
    store = MediaStore.from_env()
    client = httpx2.Client(
        timeout=30.0, headers={"User-Agent": settings.user_agent}, follow_redirects=True
    )
    try:
        tally = fill(
            store,
            Fetcher(client, args.pause),
            dry_run=args.dry_run,
            only=args.topic,
            refresh=args.refresh,
        )
    except StoreError as error:
        print(f"The bank refused the request: {error}", file=sys.stderr)
        return 1
    finally:
        client.close()
        store.close()
    verb = "would be" if args.dry_run else "were"
    print(
        f"\n{tally.images} pictures and {tally.facts} facts {verb} saved; "
        f"{tally.skipped} left as they are; {tally.unreachable} not reached."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
