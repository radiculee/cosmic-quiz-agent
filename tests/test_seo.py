"""What search engines, browsers and link previews read: the page's head, the web manifest,
robots.txt and the icon set. The name and wording come from src/brand.ts."""

from __future__ import annotations

import json
import re
import struct
from typing import Any

from tests.site_files import ROOT, SUPABASE_ORIGIN, TOKENS, brand, index_html, meta_tags

PUBLIC = ROOT / "public"
PNG_START = b"\x89PNG\r\n\x1a\n"


def _png_size(data: bytes) -> tuple[int, int]:
    assert data.startswith(PNG_START), "not a PNG"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_every_brand_token_in_the_page_has_a_value() -> None:
    text = (ROOT / "index.html").read_text(encoding="utf-8")
    values = brand()

    used = set(re.findall(r"\{\{brand\.(\w+)\}\}", text))
    assert used and used <= set(TOKENS), used - set(TOKENS)
    assert all(TOKENS[token] in values for token in used)
    assert "{{" not in index_html()


def test_the_title_is_short_and_says_what_the_site_is() -> None:
    title = brand()["TITLE"]

    assert brand()["NAME"] in title and "astronomy" in title.lower()
    assert len(title) <= 65, "search results cut a longer title"
    assert f"<title>{title}</title>" in index_html()
    description = brand()["DESCRIPTION"]
    assert 70 <= len(description) <= 160
    assert {"astronomy", "space"} <= set(description.lower().split())


def test_the_page_names_its_canonical_site_and_no_other_address() -> None:
    meta = meta_tags()
    origin = brand()["ORIGIN"]

    assert meta["og:url"] == f"{origin}/" and meta["og:site_name"] == brand()["NAME"]
    assert "cosmic" not in index_html().lower().replace("cosmic quiz and the tagline", "")


def test_the_icons_the_page_links_exist_at_their_sizes() -> None:
    html = index_html()
    for link in ("/favicon.ico", "/favicon.svg", "/apple-touch-icon.png", "/site.webmanifest"):
        assert f'href="{link}"' in html and (PUBLIC / link.lstrip("/")).is_file(), link

    assert _png_size((PUBLIC / "apple-touch-icon.png").read_bytes()) == (180, 180)
    assert _png_size((PUBLIC / "icon-192.png").read_bytes()) == (192, 192)
    assert _png_size((PUBLIC / "icon-512.png").read_bytes()) == (512, 512)
    ico = (PUBLIC / "favicon.ico").read_bytes()
    assert ico[:4] == b"\x00\x00\x01\x00" and ico[22:30] == PNG_START
    assert (PUBLIC / "favicon.svg").read_text(encoding="utf-8").startswith("<svg")


def test_the_web_manifest_matches_the_brand_and_its_icons_exist() -> None:
    manifest = json.loads((PUBLIC / "site.webmanifest").read_text(encoding="utf-8"))
    site = brand()

    assert manifest["name"] == manifest["short_name"] == site["NAME"]
    assert manifest["description"] == site["DESCRIPTION"]
    assert manifest["theme_color"] == site["THEME_COLOR"]
    assert manifest["start_url"] == "/"
    for icon in manifest["icons"]:
        width, height = _png_size((PUBLIC / icon["src"].lstrip("/")).read_bytes())
        assert icon["sizes"] == f"{width}x{height}"


def test_robots_lets_crawlers_in_and_keeps_them_off_the_api() -> None:
    lines = (PUBLIC / "robots.txt").read_text(encoding="utf-8").splitlines()

    assert "User-agent: *" in lines and "Allow: /" in lines and "Disallow: /api/" in lines
    assert not any(line.strip() == "Disallow: /" for line in lines)


def _config() -> dict[str, Any]:
    result: dict[str, Any] = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    return result


def test_media_is_served_from_the_sites_own_address_ahead_of_the_catch_all() -> None:
    rewrites = _config()["rewrites"]
    [media] = [rule for rule in rewrites if rule["source"].startswith("/media/")]

    assert media["source"] == "/media/:path(.*)"  # strict, like the redirects
    assert media["destination"] == f"{SUPABASE_ORIGIN}/storage/v1/object/public/topic-images/:path"
    assert rewrites.index(media) < [r["destination"] for r in rewrites].index("/index.html")


def test_the_policy_still_loads_images_only_from_this_site() -> None:
    policy = next(
        header["value"]
        for rule in _config()["headers"]
        if rule["source"] == "/(.*)"
        for header in rule["headers"]
        if header["key"] == "Content-Security-Policy"
    )
    directives = {part.split()[0]: part.split()[1:] for part in policy.split("; ")}

    assert directives["img-src"] == ["'self'"]  # images come through /media/*
    assert directives["connect-src"] == ["'self'", SUPABASE_ORIGIN]
    assert SUPABASE_ORIGIN not in policy.replace(f"connect-src 'self' {SUPABASE_ORIGIN}", "")
