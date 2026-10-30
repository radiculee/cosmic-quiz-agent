"""The site's own files as the tests read them: src/brand.ts, and index.html with its
{{brand.x}} tokens filled in the way vite.config.ts fills them."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_CONSTANT = re.compile(r'export const (?P<name>[A-Z_]+) =\s*"(?P<value>[^"]*)";')


def brand() -> dict[str, str]:
    """The string constants of src/brand.ts, by name (TITLE, ORIGIN and so on)."""
    text = (ROOT / "src" / "brand.ts").read_text(encoding="utf-8")
    return {match["name"]: match["value"] for match in _CONSTANT.finditer(text)}


# The token names index.html uses, and the brand.ts constant each one is.
TOKENS = {
    "name": "NAME",
    "title": "TITLE",
    "description": "DESCRIPTION",
    "origin": "ORIGIN",
    "socialImage": "SOCIAL_IMAGE",
    "socialImageAlt": "SOCIAL_IMAGE_ALT",
    "themeColor": "THEME_COLOR",
}


def index_html() -> str:
    """index.html with every {{brand.x}} filled, on one line so wrapped tags still match."""
    values = brand()
    text = (ROOT / "index.html").read_text(encoding="utf-8")
    filled = re.sub(r"\{\{brand\.(\w+)\}\}", lambda match: values[TOKENS[match[1]]], text)
    return " ".join(filled.split())


def meta_tags() -> dict[str, str]:
    """The page's <meta property|name content> pairs."""
    return dict(re.findall(r'<meta (?:property|name)="([^"]+)" content="([^"]+)"', index_html()))
