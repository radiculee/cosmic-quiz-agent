"""The topic-image fill: the licence filter, the credit line, the NASA rules, the resize, the
fact card and the whole choice for a topic. API replies are recorded ones (tests/fixtures/images);
no test reaches Wikimedia, NASA or Supabase."""

from __future__ import annotations

import io
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from PIL import Image

from agent.bank import BankReader, BankTopic
from agent.rest import RestClient, StoreError
from agent.schemas import Difficulty
from agent.web import ApiRequest
from api import topics as topics_api
from curator import images
from curator.images import (
    Candidate,
    Chosen,
    ExistingRow,
    Fetcher,
    ImageRejectedError,
    MediaStore,
    TopicMedia,
    TopicRow,
)

FIXTURES = Path(__file__).parent / "fixtures" / "images"
SUPABASE = "https://project.supabase.co"


def fixture(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return loaded


def picture(width: int, height: int, *, mode: str = "RGB", fmt: str = "JPEG") -> bytes:
    """A smooth test picture, which compresses well like a real photograph of the sky."""
    gradient = Image.radial_gradient("L").resize((width, height))
    image = Image.merge("RGB", (gradient, gradient.rotate(90), gradient.rotate(180)))
    if mode != "RGB":
        image = image.convert(mode)
    buffer = io.BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def noise(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.effect_noise((width, height), 100).convert("RGB").save(buffer, "PNG")
    return buffer.getvalue()


def fetcher_for(handler: Callable[[httpx2.Request], httpx2.Response]) -> Fetcher:
    return Fetcher(httpx2.Client(transport=httpx2.MockTransport(handler)), pause_seconds=0)


# --- Licences ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "url"),
    [
        ("CC BY 4.0", None),
        ("CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/"),
        ("CC BY-SA 3.0 igo", None),
        ("CC BY 2.5 de", None),
        ("CC0", None),
        ("Public domain", None),
        ("PD-USGov-NASA", None),
    ],
)
def test_licences_that_allow_reuse_are_accepted(name: str, url: str | None) -> None:
    licence = images.licence_of({"LicenseShortName": name, "LicenseUrl": url or ""})

    assert licence.name == name
    if url:
        assert licence.url == url


def test_a_missing_licence_url_is_derived_for_creative_commons() -> None:
    assert (
        images.licence_of({"LicenseShortName": "CC BY-SA 4.0"}).url
        == "https://creativecommons.org/licenses/by-sa/4.0/"
    )
    assert (
        images.licence_of({"LicenseShortName": "CC0"}).url
        == "https://creativecommons.org/publicdomain/zero/1.0/"
    )


@pytest.mark.parametrize(
    "name",
    [
        "CC BY-NC 4.0",
        "CC BY-ND 2.0",
        "CC BY-NC-SA 3.0",
        "GFDL",
        "Fair use",
        "Attribution",
        "",
        "ARR",
    ],
)
def test_other_licences_are_rejected(name: str) -> None:
    with pytest.raises(ImageRejectedError):
        images.licence_of({"LicenseShortName": name})


def test_non_free_and_restricted_files_are_rejected_whatever_the_licence() -> None:
    with pytest.raises(ImageRejectedError, match="non-free"):
        images.licence_of({"LicenseShortName": "Public domain", "NonFree": "true"})
    with pytest.raises(ImageRejectedError, match="trademarked"):
        images.licence_of({"LicenseShortName": "CC BY 4.0", "Restrictions": "trademarked"})


def test_the_author_is_read_from_the_markup_and_a_credit_is_required() -> None:
    licence = images.licence_of({"LicenseShortName": "CC BY 4.0"})

    assert (
        images.author_of({"Artist": '<a href="x">Jane  &amp; Co</a><br/>'}, licence) == "Jane & Co"
    )
    assert images.author_of({"Artist": "Unknown author", "Attribution": "ESO"}, licence) == "ESO"
    # The uploader's requested credit wins over an Artist field with extra notes.
    assert (
        images.author_of({"Artist": "A team , cropped by B", "Attribution": "ESO"}, licence)
        == "ESO"
    )
    with pytest.raises(ImageRejectedError, match="no author"):
        images.author_of({"Artist": ""}, licence)
    public = images.licence_of({"LicenseShortName": "Public domain"})
    assert images.author_of({"Artist": ""}, public) == "Unknown author"
    with pytest.raises(ImageRejectedError):
        images.author_of({"AttributionRequired": "true"}, public)


def test_a_licence_name_left_on_the_end_of_an_author_is_removed() -> None:
    licence = images.licence_of({"LicenseShortName": "CC BY-SA 4.0"})

    assert images.author_of({"Artist": "Jane Doe, CC BY-SA 4.0"}, licence) == "Jane Doe"
    assert images.author_of({"Artist": "Jane Doe (CC BY 3.0)"}, licence) == "Jane Doe"
    assert (
        images.author_of({"Artist": "Creative Commons Fan Club"}, licence)
        == "Creative Commons Fan Club"
    )


def test_a_long_author_is_cut_at_a_word() -> None:
    licence = images.licence_of({"LicenseShortName": "CC BY 4.0"})

    author = images.author_of({"Artist": "word " * 100}, licence)

    assert len(author) <= images.MAX_AUTHOR_CHARS
    assert author.endswith("...")


def test_the_credit_line_names_author_licence_and_place() -> None:
    assert (
        images.credit_line("ESO", "CC BY 4.0", "Wikimedia Commons")
        == "ESO, CC BY 4.0, via Wikimedia Commons"
    )


# --- Wikipedia ----------------------------------------------------------------------------------


def wikipedia_handler(imageinfo: str = "imageinfo_m87.json") -> Callable[[httpx2.Request], Any]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.host == "en.wikipedia.org":
            prop = request.url.params["prop"]
            body = fixture("pageimages_black_hole.json" if prop == "pageimages" else imageinfo)
            return httpx2.Response(200, json=body)
        return httpx2.Response(404)

    return handler


def test_wikipedia_lead_image_with_a_cc_by_licence_becomes_a_candidate() -> None:
    candidate = images.wikipedia_candidate(fetcher_for(wikipedia_handler()), "Black hole")

    assert candidate.source == "wikipedia"
    assert candidate.licence_name == "CC BY 4.0"
    assert candidate.licence_url == "https://creativecommons.org/licenses/by/4.0"
    assert candidate.download_url.startswith("https://thumb.wikimedia.org/")
    assert candidate.file_page_url.startswith("https://commons.wikimedia.org/wiki/File:")
    assert candidate.credit.endswith(", CC BY 4.0, via Wikimedia Commons")
    assert candidate.author == "ESO"
    assert candidate.credit == "ESO, CC BY 4.0, via Wikimedia Commons"


def test_a_share_alike_igo_licence_is_accepted() -> None:
    candidate = images.wikipedia_candidate(
        fetcher_for(wikipedia_handler("imageinfo_mars.json")), "Mars"
    )

    assert candidate.licence_name == "CC BY-SA 3.0 igo"
    assert candidate.author == "ESA & MPS for OSIRIS Team MPS/UPD/LAM/IAA/RSSD/INTA/UPM/DASP/IDA"
    assert candidate.credit.count("CC BY-SA") == 1


def test_a_wikipedia_file_under_another_licence_is_rejected_with_the_reason() -> None:
    info = fixture("imageinfo_m87.json")
    info["query"]["pages"][0]["imageinfo"][0]["extmetadata"]["LicenseShortName"]["value"] = (
        "CC BY-NC 4.0"
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.params["prop"] == "pageimages":
            return httpx2.Response(200, json=fixture("pageimages_black_hole.json"))
        return httpx2.Response(200, json=info)

    with pytest.raises(ImageRejectedError, match=r"licence not accepted: CC BY-NC 4\.0"):
        images.wikipedia_candidate(fetcher_for(handler), "Black hole")


def test_a_page_without_a_lead_image_and_a_non_photo_file_are_rejected() -> None:
    def bare(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"query": {"pages": [{"title": "Odd"}]}})

    with pytest.raises(ImageRejectedError, match="no lead image"):
        images.wikipedia_candidate(fetcher_for(bare), "Odd")

    info = fixture("imageinfo_m87.json")
    info["query"]["pages"][0]["imageinfo"][0]["mime"] = "image/svg+xml"

    def svg(request: httpx2.Request) -> httpx2.Response:
        if request.url.params["prop"] == "pageimages":
            return httpx2.Response(200, json=fixture("pageimages_black_hole.json"))
        return httpx2.Response(200, json=info)

    with pytest.raises(ImageRejectedError, match="not a photo"):
        images.wikipedia_candidate(fetcher_for(svg), "Black hole")


def test_titles_come_from_the_cited_pages_best_match_first() -> None:
    def item(*urls: str) -> dict[str, Any]:
        return {
            "mode": "learn",
            "difficulty": "easy",
            "explanation": "Text.",
            "sources": [{"url": url} for url in urls],
        }

    topic = TopicRow.model_validate(
        {
            "id": 1,
            "name": "The Big Bang",
            "items": [
                item(
                    "https://en.wikipedia.org/wiki/Cosmic_inflation",
                    "https://en.wikipedia.org/wiki/Big_Bang#History",
                    "https://www.nasa.gov/x",
                ),
                item(
                    "https://en.wikipedia.org/wiki/Cosmic_inflation",
                    "https://en.wikipedia.org/wiki/File:Something.jpg",
                    "https://en.wikipedia.org/wiki/Hubble%27s_law",
                    "https://en.wikipedia.org/wiki/Timeline",
                    "https://en.wikipedia.org/wiki/Age_of_the_universe",
                ),
            ],
        }
    )

    titles = images.wikipedia_titles(topic)

    assert titles == ["Big Bang", "Cosmic inflation", "Hubble's law"]


# --- NASA ---------------------------------------------------------------------------------------


def nasa_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = fixture("nasa_search.json")["collection"]["items"]
    return entries


def candidate_of(entry: dict[str, Any], topic: str) -> Candidate:
    return images.nasa_candidate(entry["data"][0], entry["links"], topic)


def test_a_nasa_result_with_a_nasa_credit_is_accepted_at_1280_pixels() -> None:
    candidate = candidate_of(nasa_entries()[2], "Pillars of Creation")

    assert candidate.source == "nasa"
    assert candidate.download_url.endswith("PIA03096~medium.jpg")
    assert candidate.file_page_url == "https://images.nasa.gov/details/PIA03096"
    assert candidate.author.startswith("IRAC Image: NASA/JPL-Caltech")
    assert candidate.licence_name == "Public domain"
    assert candidate.credit.endswith("Public domain, via NASA Image and Video Library")


def test_a_nasa_result_credited_to_someone_else_is_rejected() -> None:
    # The first result's description says "Credit: ESO/M. Kornmesser".
    with pytest.raises(ImageRejectedError, match="credit is not NASA's"):
        candidate_of(nasa_entries()[0], "Pillars of Creation")


def test_a_nasa_result_that_claims_copyright_is_rejected() -> None:
    entry = nasa_entries()[2]
    entry["data"][0]["secondary_creator"] = "NASA/JPL (c) Example Agency"

    with pytest.raises(ImageRejectedError, match="copyright"):
        candidate_of(entry, "Pillars of Creation")

    entry = nasa_entries()[2]
    entry["data"][0]["description"] += " Used with permission."
    with pytest.raises(ImageRejectedError, match="copyright or permission"):
        candidate_of(entry, "Pillars of Creation")


def test_a_nasa_result_must_be_about_the_topic_and_have_a_usable_size() -> None:
    with pytest.raises(ImageRejectedError, match="not clearly about"):
        candidate_of(nasa_entries()[2], "Quasars")

    entry = nasa_entries()[2]
    entry["links"] = [link for link in entry["links"] if "~orig" in link["href"]]
    with pytest.raises(ImageRejectedError, match="no usable size"):
        candidate_of(entry, "Pillars of Creation")


def test_a_nasa_result_without_credits_is_credited_to_nasa() -> None:
    entry = nasa_entries()[1]  # a Hubble image with no photographer or secondary creator

    candidate = candidate_of(entry, "Pillars of Creation")

    assert candidate.author == "NASA"


# --- Resizing -----------------------------------------------------------------------------------


def webp_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "WEBP"
        return image.size


def test_a_large_picture_gives_a_16_9_card_and_a_link_preview() -> None:
    rendered = images.render(picture(1600, 1000))

    assert webp_size(rendered.card) == (640, 360)
    assert len(rendered.card) <= images.CARD_TARGET_BYTES
    assert rendered.preview is not None
    assert webp_size(rendered.preview) == (1200, 630)
    assert len(rendered.preview) <= images.PREVIEW_MAX_BYTES


def test_a_picture_too_small_for_the_preview_gives_a_card_only() -> None:
    rendered = images.render(picture(800, 500))

    assert webp_size(rendered.card) == (640, 360)
    assert rendered.preview is None


@pytest.mark.parametrize(
    ("size", "reason"),
    [((500, 400), "too small"), ((900, 1500), "shape"), ((3000, 600), "shape")],
)
def test_pictures_that_are_small_or_badly_shaped_are_rejected(
    size: tuple[int, int], reason: str
) -> None:
    with pytest.raises(ImageRejectedError, match=reason):
        images.render(picture(*size))


def test_transparent_and_palette_pictures_are_laid_on_the_card_colour() -> None:
    rendered = images.render(picture(900, 600, mode="RGBA", fmt="PNG"))

    with Image.open(io.BytesIO(rendered.card)) as card:
        assert card.mode == "RGB"
    palette = images.render(picture(900, 600, mode="P", fmt="PNG"))
    assert webp_size(palette.card) == (640, 360)


def test_a_picture_too_detailed_for_the_size_limit_is_rejected() -> None:
    with pytest.raises(ImageRejectedError, match="too detailed"):
        images.render(noise(900, 600))


def test_unreadable_and_unwanted_formats_are_rejected() -> None:
    with pytest.raises(ImageRejectedError, match="cannot read"):
        images.render(b"not an image")
    with pytest.raises(ImageRejectedError, match="GIF"):
        images.render(picture(900, 600, mode="P", fmt="GIF"))


def test_a_file_name_carries_a_hash_of_the_content() -> None:
    first = images.file_name("Dark energy", b"one", "card")
    again = images.file_name("Dark energy", b"one", "card")
    other = images.file_name("Dark energy", b"two", "card")

    assert first == again
    assert first != other
    assert first.startswith("dark-energy-")
    assert first.endswith("-card.webp")


# --- Fact cards ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("topic", "text", "category"),
    [
        ("Black holes", "Gravity so strong that light cannot escape.", "black-hole"),
        ("The Milky Way", "Our home galaxy holds hundreds of billions of stars.", "galaxy"),
        ("Dark matter", "It does not emit light.", "cosmology"),
        ("Neutrinos", "A neutrino is a tiny particle.", "particle"),
        ("Voyager 1", "A probe launched in 1977.", "mission"),
        ("The Sun and solar flares", "Bursts of radiation.", "star"),
        ("Saturn's rings", "Ice and rock around the planet.", "planet"),
        ("Halley's Comet", "Visible every 76 years.", "small-body"),
        ("Zzz", "Nothing relevant here.", "space"),
    ],
)
def test_a_topic_gets_the_category_its_name_and_text_point_to(
    topic: str, text: str, category: str
) -> None:
    assert images.category_of(topic, [text]) == category


def test_a_hit_in_the_name_outweighs_the_text() -> None:
    text = "Stars, stars, stars and more stars fill this galaxy."

    assert images.category_of("Quasars", [text]) == "galaxy"


def test_the_fact_is_a_sentence_with_a_figure_that_stands_alone() -> None:
    text = (
        "Neutron stars are the collapsed cores of massive stars. "
        "They are very dense. "
        "A teaspoon of neutron star material would weigh about a billion tonnes on Earth. "
        "Short one."
    )

    assert images.pick_fact("Neutron stars", [text]) == (
        "A teaspoon of neutron star material would weigh about a billion tonnes on Earth."
    )


def test_the_fact_comes_from_the_earlier_text_when_scores_tie() -> None:
    first = "Jupiter is the largest planet in the solar system, by far."
    second = "Neptune is the largest planet in the solar system, by far."

    assert images.pick_fact("Planets", [first, second]) == first


def test_a_long_first_sentence_is_cut_when_nothing_fits() -> None:
    text = "word " * 100 + "end."

    fact = images.pick_fact("Topic", [text])

    assert fact is not None
    assert len(fact) <= images.MAX_FACT_CHARS
    assert fact.endswith("...")
    assert images.pick_fact("Topic", ["", "  "]) is None


def test_explanations_are_ordered_learn_first_and_easy_first() -> None:
    def item(mode: str, difficulty: str, text: str) -> dict[str, Any]:
        return {"mode": mode, "difficulty": difficulty, "explanation": text, "sources": []}

    topic = TopicRow.model_validate(
        {
            "id": 1,
            "name": "T",
            "items": [
                item("quiz", "easy", "quiz easy"),
                item("learn", "hard", "learn hard"),
                item("learn", "easy", "learn easy"),
            ],
        }
    )

    assert topic.explanations() == ["learn easy", "learn hard", "quiz easy"]


# --- Choosing for a topic -------------------------------------------------------------------------


def topic_row(
    name: str = "Black hole", url: str = "https://en.wikipedia.org/wiki/Black_hole"
) -> TopicRow:
    return TopicRow.model_validate(
        {
            "id": 7,
            "name": name,
            "items": [
                {
                    "mode": "learn",
                    "difficulty": "easy",
                    "explanation": (
                        "A black hole is a region where gravity is so strong that nothing escapes "
                        "it, not even light, once it crosses the event horizon."
                    ),
                    "sources": [{"url": url}],
                }
            ],
        }
    )


def web(
    *, wikipedia: bool = True, nasa: bool = True, status: int = 200
) -> Callable[[httpx2.Request], httpx2.Response]:
    """A fake of every host the fill talks to."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        host = request.url.host
        if status != 200:
            return httpx2.Response(status)
        if host == "en.wikipedia.org":
            if not wikipedia:
                return httpx2.Response(200, json={"query": {"pages": [{"title": "Page"}]}})
            prop = request.url.params["prop"]
            name = "pageimages_black_hole.json" if prop == "pageimages" else "imageinfo_m87.json"
            return httpx2.Response(200, json=fixture(name))
        if host == "thumb.wikimedia.org":
            return httpx2.Response(200, content=picture(1280, 1280))
        if host == "images-api.nasa.gov":
            body = fixture("nasa_search.json") if nasa else {"collection": {"items": []}}
            return httpx2.Response(200, json=body)
        if host == "images-assets.nasa.gov":
            return httpx2.Response(200, content=picture(1280, 951))
        return httpx2.Response(404)

    return handler


def test_a_topic_with_a_wikipedia_picture_gets_an_image_row_and_two_files() -> None:
    chosen = images.choose_media(topic_row(), fetcher_for(web()))

    assert chosen is not None
    media = chosen.media
    assert media.kind == "image"
    assert media.source == "wikipedia"
    assert media.card_width == 640
    assert media.card_height == 360
    assert media.card_path is not None
    assert media.preview_path is not None
    assert set(chosen.files) == {media.card_path, media.preview_path}
    assert media.card_path.startswith("black-hole-")
    assert media.credit is not None
    assert media.licence_name == "CC BY 4.0"
    assert media.category is None
    assert media.fact is None


def test_nasa_is_tried_when_wikipedia_has_nothing_acceptable() -> None:
    topic = topic_row("Pillars of Creation", "https://en.wikipedia.org/wiki/Pillars_of_Creation")

    chosen = images.choose_media(topic, fetcher_for(web(wikipedia=False)))

    assert chosen is not None
    assert chosen.media.source == "nasa"
    assert (
        chosen.media.file_page_url
        == "https://images.nasa.gov/details/GSFC_20171208_Archive_e000842"
    )


def test_a_topic_with_no_acceptable_picture_gets_a_fact_with_the_reasons() -> None:
    chosen = images.choose_media(topic_row(), fetcher_for(web(wikipedia=False, nasa=False)))

    assert chosen is not None
    media = chosen.media
    assert media.kind == "fact"
    assert media.category == "black-hole"
    assert media.fact is not None
    assert media.fact.startswith("A black hole is a region")
    assert "wikipedia Black hole: Black hole: the page has no lead image" in media.notes
    assert chosen.files == {}


def test_a_source_that_cannot_be_reached_leaves_the_topic_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A fact card here would hide a picture that an outage kept from us.
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    assert images.choose_media(topic_row(), fetcher_for(web(status=503))) is None


def test_a_rejected_wikipedia_picture_falls_through_to_the_next_source() -> None:
    def small(request: httpx2.Request) -> httpx2.Response:
        if request.url.host == "thumb.wikimedia.org":
            return httpx2.Response(200, content=picture(300, 200))
        return web()(request)

    topic = topic_row("Pillars of Creation", "https://en.wikipedia.org/wiki/Black_hole")

    chosen = images.choose_media(topic, fetcher_for(small))

    assert chosen is not None
    assert chosen.media.source == "nasa"


def test_the_fetcher_only_talks_to_known_hosts() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("no request should be made")

    with pytest.raises(images.FetchError, match="not a known picture host"):
        fetcher_for(handler).json("https://example.com/api")


def test_the_fetcher_retries_a_rate_limit_then_succeeds() -> None:
    replies = [
        httpx2.Response(429, headers={"retry-after": "0"}),
        httpx2.Response(200, json={"a": 1}),
    ]

    def handler(_request: httpx2.Request) -> httpx2.Response:
        return replies.pop(0)

    assert fetcher_for(handler).json("https://en.wikipedia.org/w/api.php") == {"a": 1}


# --- The bank -----------------------------------------------------------------------------------


class Recorder:
    """Answers Supabase's REST and Storage calls and keeps every request."""

    def __init__(self, topic_images: object = None, status: int = 200) -> None:
        self.requests: list[httpx2.Request] = []
        self.topic_images = topic_images if topic_images is not None else []
        self.status = status

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if request.url.path == "/rest/v1/topic_images" and request.method == "GET":
            if self.status != 200:
                return httpx2.Response(self.status, json={"message": "no such table"})
            return httpx2.Response(200, json=self.topic_images)
        if request.url.path == "/rest/v1/topics":
            return httpx2.Response(200, json=[topic_row().model_dump(mode="json")])
        return httpx2.Response(200 if request.method != "POST" else 201)

    def writes(self) -> list[httpx2.Request]:
        return [r for r in self.requests if r.method in ("POST", "DELETE")]


def store_for(recorder: Recorder) -> MediaStore:
    http = httpx2.Client(transport=httpx2.MockTransport(recorder))
    return MediaStore(
        RestClient(SUPABASE, "secret", client=http, retry_backoff_seconds=0),
        http,
        SUPABASE,
        "secret",
    )


def test_upload_sends_a_cacheable_webp_with_the_secret_key() -> None:
    recorder = Recorder()

    store_for(recorder).upload("a-b-card.webp", b"data")

    (request,) = recorder.requests
    assert str(request.url) == f"{SUPABASE}/storage/v1/object/topic-images/a-b-card.webp"
    assert request.headers["apikey"] == "secret"
    assert request.headers["content-type"] == "image/webp"
    assert request.headers["cache-control"] == "max-age=31536000"
    assert request.content == b"data"


def test_save_upserts_one_row_per_topic() -> None:
    recorder = Recorder()
    media = TopicMedia(kind="fact", category="star", fact="A fact that is long enough to keep.")

    store_for(recorder).save(7, media)

    (request,) = recorder.requests
    assert request.url.params["on_conflict"] == "topic_id"
    assert "merge-duplicates" in request.headers["prefer"]
    body = json.loads(request.content)
    assert body["topic_id"] == 7
    assert body["kind"] == "fact"
    assert body["category"] == "star"
    assert "locked" not in body, "a hand-set lock must survive an upsert"
    assert body["card_path"] is None, "switching from an image clears its columns"


def test_an_upload_the_bank_refuses_raises() -> None:
    http = httpx2.Client(
        transport=httpx2.MockTransport(lambda _r: httpx2.Response(400, text="bad"))
    )
    store = MediaStore(RestClient(SUPABASE, "secret", client=http), http, SUPABASE, "secret")

    with pytest.raises(StoreError, match="HTTP 400"):
        store.upload("x.webp", b"")


def fill(
    recorder: Recorder,
    *,
    dry_run: bool = False,
    only: str | None = None,
    refresh: bool = False,
) -> images.Tally:
    return images.fill(
        store_for(recorder),
        fetcher_for(web()),
        dry_run=dry_run,
        only=only,
        refresh=refresh,
        out=lambda _text: None,
    )


def test_a_dry_run_reads_and_writes_nothing() -> None:
    recorder = Recorder(status=404)  # even a bank without migration 012

    tally = fill(recorder, dry_run=True)

    assert tally.images == 1
    assert recorder.writes() == []


def test_a_real_run_uploads_the_files_before_it_saves_the_row() -> None:
    recorder = Recorder()

    tally = fill(recorder)

    assert tally.images == 1
    paths = [r.url.path for r in recorder.writes()]
    assert paths[0].startswith("/storage/v1/object/topic-images/black-hole-")
    assert paths[1].startswith("/storage/v1/object/topic-images/black-hole-")
    assert paths[2] == "/rest/v1/topic_images"


def test_a_real_run_needs_the_table() -> None:
    with pytest.raises(StoreError):
        fill(Recorder(status=404))


def test_a_topic_with_a_picture_is_skipped_unless_refreshed_and_a_lock_is_kept() -> None:
    row = {
        "topic_id": 7,
        "kind": "image",
        "locked": False,
        "card_path": "old-card.webp",
        "preview_path": None,
    }

    skipped = fill(Recorder([row]))
    refreshed = fill(Recorder([row]), refresh=True)
    locked = fill(Recorder([{**row, "kind": "fact", "locked": True}]), refresh=True)

    assert skipped.skipped == 1
    assert skipped.images == 0
    assert refreshed.images == 1
    assert locked.skipped == 1
    assert locked.images == 0


def test_a_fact_row_is_tried_again_and_the_replaced_files_are_removed() -> None:
    old = {
        "topic_id": 7,
        "kind": "image",
        "locked": False,
        "card_path": "old-card.webp",
        "preview_path": "old-preview.webp",
    }
    recorder = Recorder([old])

    fill(recorder, refresh=True)

    removed = [r.url.path for r in recorder.requests if r.method == "DELETE"]
    assert removed == [
        "/storage/v1/object/topic-images/old-card.webp",
        "/storage/v1/object/topic-images/old-preview.webp",
    ]


def test_only_the_named_topic_is_filled() -> None:
    assert fill(Recorder(), only="no such topic").images == 0
    assert fill(Recorder(), only="BLACK HOLE").images == 1


def test_describe_shows_the_credit_licence_and_sizes() -> None:
    chosen = images.choose_media(topic_row(), fetcher_for(web()))
    assert chosen is not None

    text = images.describe("Black hole", chosen)

    assert "IMAGE  wikipedia  CC BY 4.0" in text
    assert chosen.media.credit is not None
    assert chosen.media.credit in text
    assert "card" in text
    assert "preview" in text
    fact = Chosen(media=TopicMedia(kind="fact", category="star", fact="Fact.", notes="none found"))
    assert "FACT  star" in images.describe("Topic", fact)


def test_existing_rows_validate() -> None:
    row = ExistingRow.model_validate({"topic_id": 1, "kind": "fact", "locked": False})

    assert row.paths == []


# --- The topics endpoint ------------------------------------------------------------------------

LEVELS: tuple[Difficulty, ...] = ("easy", "medium", "hard")
AURORAS = BankTopic(name="Auroras", kind="evergreen", learn=list(LEVELS), quiz=list(LEVELS))

IMAGE_ROW: dict[str, Any] = {
    "kind": "image",
    "card_path": "auroras-0123456789-card.webp",
    "card_width": 640,
    "card_height": 360,
    "preview_path": "auroras-abcdef0123-preview.webp",
    "source": "wikipedia",
    "licence_name": "CC BY 4.0",
    "licence_url": "https://creativecommons.org/licenses/by/4.0",
    "file_page_url": "https://commons.wikimedia.org/wiki/File:Aurora.jpg",
    "credit": "Jane Doe, CC BY 4.0, via Wikimedia Commons",
    "category": None,
    "fact": None,
    "topics": {"name": "Auroras"},
}
FACT_ROW: dict[str, Any] = {
    "kind": "fact",
    "category": "planet",
    "fact": "Auroras glow where charged particles meet the upper atmosphere.",
    "topics": {"name": "Auroras"},
}


def media_of(row: dict[str, Any]) -> dict[str, topics_api._MediaRow]:
    rows = [topics_api._MediaRow.model_validate(row)]
    return {entry.topics.name: entry for entry in rows}


def test_an_image_row_adds_a_picture_served_from_this_site() -> None:
    topic = topics_api.with_media(AURORAS, media_of(IMAGE_ROW)["Auroras"])

    assert topic.fact is None
    assert topic.image is not None
    assert topic.image.src == "/media/auroras-0123456789-card.webp"
    assert topic.image.preview == "/media/auroras-abcdef0123-preview.webp"
    assert (topic.image.width, topic.image.height) == (640, 360)
    assert topic.image.credit == "Jane Doe, CC BY 4.0, via Wikimedia Commons"
    assert topic.image.licence == "CC BY 4.0"
    assert topic.image.page_url.startswith("https://commons.wikimedia.org/")


def test_a_fact_row_adds_a_fact_and_an_incomplete_row_adds_nothing() -> None:
    topic = topics_api.with_media(AURORAS, media_of(FACT_ROW)["Auroras"])

    assert topic.image is None
    assert topic.fact is not None
    assert topic.fact.category == "planet"
    incomplete = media_of({**IMAGE_ROW, "credit": None})["Auroras"]
    assert topics_api.with_media(AURORAS, incomplete) == AURORAS
    assert topics_api.with_media(AURORAS, None) == AURORAS


class _Reader:
    """Stands in for BankReader: one complete topic."""

    def __enter__(self) -> _Reader:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def topics(self) -> list[BankTopic]:
        return [AURORAS]


def test_the_endpoint_adds_the_new_fields_and_leaves_the_old_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(BankReader, "from_env", classmethod(lambda cls: _Reader()))
    monkeypatch.setattr(topics_api, "read_media", lambda: media_of(IMAGE_ROW))

    response = topics_api.handle(ApiRequest(method="GET", path="/api/topics"))

    assert response.status == 200
    assert isinstance(response.body, dict)
    (topic,) = response.body["topics"]
    assert topic["name"] == "Auroras"
    assert topic["learn"] == list(LEVELS)
    assert topic["image"]["src"] == "/media/auroras-0123456789-card.webp"
    assert "fact" not in topic, "an absent fact is left out, not sent as null"


def test_pictures_that_cannot_be_read_do_not_take_the_topic_list_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", SUPABASE)
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable")
    http = httpx2.Client(transport=httpx2.MockTransport(lambda _r: httpx2.Response(404, json={})))
    monkeypatch.setattr(
        topics_api, "RestClient", lambda url, key: RestClient(url, key, client=http)
    )

    assert topics_api.read_media() == {}
    monkeypatch.delenv("SUPABASE_URL")
    assert topics_api.read_media() == {}


def test_the_topic_images_request_names_its_columns() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=[IMAGE_ROW])

    rest = RestClient(
        SUPABASE, "publishable", client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )

    found = topics_api.fetch_media(rest)

    assert list(found) == ["Auroras"]
    selected = seen[0].url.params["select"]
    assert "locked" not in selected
    assert "notes" not in selected


# --- Packaging ----------------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent


def test_pillow_stays_out_of_what_vercel_installs() -> None:
    # Vercel installs from pyproject.toml, so Pillow there would reach every function's bundle.
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    runtime = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    media = (ROOT / "requirements-media.txt").read_text(encoding="utf-8")

    assert not any("pillow" in dependency.lower() for dependency in project["dependencies"])
    assert "pillow" not in runtime.lower()
    assert "pillow==" in media.lower()
    assert "-r requirements-media.txt" in (ROOT / "requirements-dev.txt").read_text(
        encoding="utf-8"
    )
