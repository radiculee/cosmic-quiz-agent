from __future__ import annotations

import httpx2
import pytest

from agent.config import Settings
from agent.tools import ToolContext, ToolError
from agent.tools.arxiv import build_search_query, parse_abs_url, search_arxiv
from agent.tools.base import http_get
from agent.tools.feeds import fetch_feed, parse_rss
from agent.tools.fetch import fetch_page
from agent.tools.nasa import nasa_apod, search_nasa_images
from agent.tools.wikipedia import search_wikipedia
from agent.verify import normalize_url
from tests.conftest import FakeWeb

WIKI_API = "https://en.wikipedia.org/w/api.php"


# --- Allow-list -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://en.wikipedia.org/wiki/Moon", True),
        ("https://science.nasa.gov/universe/stars/", True),
        ("https://esawebb.org/news/weic2619/", True),
        ("https://arxiv.org/abs/2203.04890", True),
        ("https://arxiv.org/pdf/2203.04890", False),  # arXiv: abstract pages only
        ("https://arxiv.org/list/astro-ph/new", False),
        ("http://en.wikipedia.org/wiki/Moon", False),  # https only
        ("https://evilnasa.gov/page", False),  # not a subdomain of nasa.gov
        ("https://nasa.gov.example.com/page", False),
        ("https://example.com/page", False),
    ],
)
def test_allow_list(ctx: ToolContext, url: str, allowed: bool) -> None:
    assert ctx.is_allowed(url) is allowed


# --- HTTP retries -----------------------------------------------------------------------------


def test_http_get_retries_server_errors_then_succeeds(ctx: ToolContext, web: FakeWeb) -> None:
    statuses = iter([503, 200])
    web.add("https://example.org/", lambda _r: httpx2.Response(next(statuses), text="ok"))

    response = http_get(ctx, "https://example.org/page")

    assert response.text == "ok"
    assert len(web.requests) == 2


def test_http_get_gives_up_after_retries(ctx: ToolContext, web: FakeWeb) -> None:
    web.add_text("https://example.org/", "busy", status=503)

    with pytest.raises(ToolError, match="503 after 3 attempts"):
        http_get(ctx, "https://example.org/page")
    assert len(web.requests) == 3  # one try plus two retries


def test_http_get_does_not_retry_client_errors(ctx: ToolContext, web: FakeWeb) -> None:
    web.add_text("https://example.org/", "gone", status=404)

    with pytest.raises(ToolError, match="404"):
        http_get(ctx, "https://example.org/page")
    assert len(web.requests) == 1


# --- Wikipedia --------------------------------------------------------------------------------


def wiki_extract(request: httpx2.Request) -> httpx2.Response:
    assert request.url.params["prop"] == "extracts"
    page = {
        "title": "Neutron star",
        "extract": (
            "A neutron star is the collapsed core of a massive star.\n\n"
            "== History ==\nFirst proposed in 1934.\n\n== References ==\nLong list of refs."
        ),
    }
    return httpx2.Response(200, json={"query": {"pages": [page]}})


def test_search_wikipedia_lists_results_without_recording(ctx: ToolContext, web: FakeWeb) -> None:
    result = {
        "title": "Neutron star",
        "snippet": 'A <span class="x">neutron</span> star &amp; core',
    }
    web.add_json(WIKI_API, {"query": {"search": [result]}})

    output = search_wikipedia({"query": "neutron star"}, ctx)

    assert "URL: https://en.wikipedia.org/wiki/Neutron_star" in output
    assert "A neutron star & core" in output
    assert ctx.fetched == {}  # search results are not citable


def test_fetch_wikipedia_records_canonical_url_and_drops_reference_sections(
    ctx: ToolContext, web: FakeWeb
) -> None:
    web.add(WIKI_API, wiki_extract)

    output = fetch_page({"url": "https://en.wikipedia.org/wiki/Neutron_stars"}, ctx)

    assert output.startswith("URL: https://en.wikipedia.org/wiki/Neutron_star\n")
    assert "First proposed in 1934." in output
    assert "Long list of refs." not in output
    assert normalize_url("https://en.wikipedia.org/wiki/Neutron_star") in ctx.fetched
    assert normalize_url("https://en.wikipedia.org/wiki/Neutron_stars") in ctx.fetched


# --- fetch_page on HTML ------------------------------------------------------------------------

PAGE_HTML = """
<html><head><title>Stars - NASA Science</title></head><body>
<nav><ul><li>Home</li><li>Missions</li></ul></nav>
<ul><li>Menu item outside main</li></ul>
<main><h1>Star Basics</h1><p>Stars are giant balls of hot gas.</p>
<script>var x = 1;</script><p>Most are   mostly hydrogen.</p></main>
</body></html>
"""


def test_fetch_html_prefers_main_content(ctx: ToolContext, web: FakeWeb) -> None:
    web.add_text("https://science.nasa.gov/universe/stars/", PAGE_HTML)

    output = fetch_page({"url": "https://science.nasa.gov/universe/stars/"}, ctx)

    assert "Title: Stars - NASA Science" in output
    assert "Stars are giant balls of hot gas.\n\nMost are mostly hydrogen." in output
    assert "Menu item" not in output and "Missions" not in output and "var x" not in output


def test_fetch_truncates_and_records_exactly_what_the_model_sees(
    http: httpx2.Client, web: FakeWeb
) -> None:
    ctx = ToolContext(settings=Settings(max_page_chars=20), http=http)
    web.add_text("https://science.nasa.gov/universe/stars/", PAGE_HTML)

    output = fetch_page({"url": "https://science.nasa.gov/universe/stars/"}, ctx)

    assert output.endswith("[Page truncated.]")
    assert ctx.fetched[normalize_url("https://science.nasa.gov/universe/stars/")] == (
        "Star Basics\n\nStars a"
    )


def test_fetch_rejects_disallowed_urls_without_a_request(ctx: ToolContext, web: FakeWeb) -> None:
    with pytest.raises(ToolError, match="not allowed"):
        fetch_page({"url": "https://example.com/stars"}, ctx)
    assert web.requests == []


def test_fetch_rejects_redirects_off_the_allow_list(ctx: ToolContext, web: FakeWeb) -> None:
    web.add_redirect("https://www.space.com/moved", "https://tracker.example.com/page")
    web.add_text("https://tracker.example.com/", PAGE_HTML)

    with pytest.raises(ToolError, match="not on the allow-list"):
        fetch_page({"url": "https://www.space.com/moved"}, ctx)
    assert ctx.fetched == {}


def test_fetch_rejects_non_html(ctx: ToolContext, web: FakeWeb) -> None:
    web.add_text("https://www.eso.org/file", "%PDF-1.7", content_type="application/pdf")

    with pytest.raises(ToolError, match="not an HTML page"):
        fetch_page({"url": "https://www.eso.org/file"}, ctx)


# --- arXiv ------------------------------------------------------------------------------------

ARXIV_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2203.04890v2</id>
    <published>2022-03-09T17:05:08Z</published>
    <title>The Low Frequency
      Perspective on Fast Radio Bursts</title>
    <summary>Fast radio bursts are bright millisecond radio flashes.</summary>
    <author><name>Maura Pilia</name></author>
  </entry>
</feed>"""


def test_build_search_query_requires_every_term() -> None:
    assert build_search_query("fast radio bursts!") == (
        "cat:astro-ph* AND all:fast AND all:radio AND all:bursts"
    )
    with pytest.raises(ToolError):
        build_search_query("!!!")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://arxiv.org/abs/2203.04890", "2203.04890"),
        ("https://arxiv.org/abs/2203.04890v3", "2203.04890"),
        ("https://arxiv.org/abs/astro-ph/0601001v1", "astro-ph/0601001"),
        ("https://arxiv.org/pdf/2203.04890", None),
        ("https://en.wikipedia.org/abs/2203.04890", None),
    ],
)
def test_parse_abs_url(url: str, expected: str | None) -> None:
    assert parse_abs_url(url) == expected


def test_search_arxiv_lists_papers_without_recording(ctx: ToolContext, web: FakeWeb) -> None:
    web.add_text("https://export.arxiv.org/api/query", ARXIV_FEED, "application/atom+xml")

    output = search_arxiv({"query": "fast radio bursts"}, ctx)

    assert "The Low Frequency Perspective on Fast Radio Bursts (2022-03-09, Maura Pilia)" in output
    assert "URL: https://arxiv.org/abs/2203.04890\n" in output
    assert ctx.fetched == {}


def test_fetch_arxiv_abstract_records_versionless_url(ctx: ToolContext, web: FakeWeb) -> None:
    web.add_text("https://export.arxiv.org/api/query", ARXIV_FEED, "application/atom+xml")

    output = fetch_page({"url": "https://arxiv.org/abs/2203.04890v2"}, ctx)

    assert output.startswith("URL: https://arxiv.org/abs/2203.04890\n")
    assert "Abstract: Fast radio bursts are bright millisecond radio flashes." in output
    assert normalize_url("https://arxiv.org/abs/2203.04890") in ctx.fetched


# --- Feeds ------------------------------------------------------------------------------------

# The root element reproduces science.nasa.gov's missing space between two xmlns attributes.
BROKEN_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:a="https://a.example/"xmlns:b="https://b.example/"><channel>
<item><title>Hubble &amp; Saturn</title><link>https://esahubble.org/news/heic2612/</link>
<pubDate>Wed, 02 Sep 2026 20:00:00 +0200</pubDate>
<description>&lt;p&gt;A ten-sided wave.&lt;/p&gt;</description></item>
</channel></rss>"""


def test_parse_rss_repairs_missing_attribute_space() -> None:
    items = parse_rss(BROKEN_RSS)

    assert [(i.title, i.link, i.summary) for i in items] == [
        ("Hubble & Saturn", "https://esahubble.org/news/heic2612/", "A ten-sided wave.")
    ]


def test_fetch_feed_lists_leads_without_recording(ctx: ToolContext, web: FakeWeb) -> None:
    web.add_text("https://esahubble.org/news/feed/", BROKEN_RSS, "application/rss+xml")

    output = fetch_feed({"feed": "esa_hubble"}, ctx)

    assert "URL: https://esahubble.org/news/heic2612/" in output
    assert ctx.fetched == {}


def test_fetch_feed_rejects_unknown_feeds(ctx: ToolContext) -> None:
    with pytest.raises(ToolError, match="feed must be one of"):
        fetch_feed({"feed": "random_blog"}, ctx)


# --- NASA -------------------------------------------------------------------------------------

APOD_ARTICLE = (
    "<html><head><title>APOD: New Horizons</title></head><body><main>"
    "<p>Explanation: New Horizons passed Pluto.</p></main></body></html>"
)


def test_apod_old_date_follows_redirect_to_article(ctx: ToolContext, web: FakeWeb) -> None:
    article = "https://science.nasa.gov/image-article/apod-2015-july-14-new-horizons/"
    web.add_redirect("https://apod.nasa.gov/apod/ap150714.html", article)
    web.add_text(article, APOD_ARTICLE)

    output = nasa_apod({"date": "2015-07-14"}, ctx)

    assert output.startswith(f"URL: {article}\n")
    assert normalize_url(article) in ctx.fetched


def test_apod_recent_date_found_from_landing_page(ctx: ToolContext, web: FakeWeb) -> None:
    article = "https://science.nasa.gov/image-article/apod-2024-april-8-comet-tail/"
    landing = f'<html><main><a href="{article}">Comet</a></main></html>'
    web.add_redirect("https://apod.nasa.gov/apod/ap240408.html", "https://science.nasa.gov/apod/")
    web.add_text("https://science.nasa.gov/apod/", landing)
    web.add_text(article, APOD_ARTICLE)

    output = nasa_apod({"date": "2024-04-08"}, ctx)

    assert output.startswith(f"URL: {article}\n")
    assert normalize_url("https://science.nasa.gov/apod/") not in ctx.fetched  # never citable


def test_apod_rejects_dates_before_the_first_entry(ctx: ToolContext) -> None:
    with pytest.raises(ToolError, match="1995-06-16"):
        nasa_apod({"date": "1990-01-01"}, ctx)


def test_nasa_images_records_each_result(ctx: ToolContext, web: FakeWeb) -> None:
    item = {
        "data": [
            {
                "nasa_id": "PIA03606",
                "title": "Most Detailed Image of the Crab Nebula",
                "date_created": "2005-12-01T21:09:21Z",
                "center": "JPL",
                "description": "<b>The Crab Nebula</b> is a supernova remnant.",
            }
        ]
    }
    web.add_json("https://images-api.nasa.gov/search", {"collection": {"items": [item]}})

    output = search_nasa_images({"query": "Crab Nebula"}, ctx)

    url = "https://images.nasa.gov/details/PIA03606"
    assert f"URL: {url}" in output
    assert "The Crab Nebula is a supernova remnant." in ctx.fetched[normalize_url(url)]


def test_wikipedia_extract_drops_empty_brackets() -> None:
    from agent.tools.wikipedia import clean_extract

    text = "The Kuiper belt ( ) is a disc, near Neptune ( ), and beyond (; Latin) too."

    assert (
        clean_extract(text) == "The Kuiper belt is a disc, near Neptune, and beyond (; Latin) too."
    )


def test_arxiv_latex_becomes_plain_text() -> None:
    from agent.tools.arxiv import latex_to_text

    # Built from code points so the test source holds no escape sequences or look-alikes.
    bs, plus_minus, mu, tilde_op, times = chr(92), chr(0xB1), chr(0x3BC), chr(0x223C), chr(0xD7)
    latex = (
        f"a diameter of $51.8 {bs}pm 2.3${bs},{bs}uas (68{bs}% credible), "
        f"{bs}sim 3 Gyr, Fig.~2, 2{bs}times10^3"
    )

    assert latex_to_text(latex) == (
        f"a diameter of 51.8 {plus_minus} 2.3 {mu}as (68% credible), "
        f"{tilde_op} 3 Gyr, Fig. 2, 2{times}10^3"
    )


def test_a_redirected_page_is_one_read_under_two_urls(ctx: ToolContext) -> None:
    ctx.record_fetch("text", "https://nasa.gov/a", "https://www.nasa.gov/a/")
    ctx.record_fetch("other", "https://images.nasa.gov/details/1")

    assert len(ctx.fetched) == 3
    assert len(ctx.reads) == 2 and ctx.reads[0].startswith("https://www.nasa.gov/a")
