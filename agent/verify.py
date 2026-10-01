"""Code-enforced checks on agent output.

The citation rule lives here, not in the prompt: a source may only be a URL that was actually
fetched during the run. Any other URL is dropped, whatever the model claims.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import unquote, urlsplit, urlunsplit

from agent.schemas import Citation, CitationCheck

_WHITESPACE = re.compile(r"\s+")


def normalize_url(url: str) -> str:
    """Canonical form for comparing URLs.

    Lower-cases the scheme and host, drops the fragment and any trailing slash, decodes
    percent-escapes in the path, and treats spaces and underscores in paths as the same
    (Wikipedia uses both for article titles).
    """
    parts = urlsplit(url.strip())
    path = unquote(parts.path).replace(" ", "_").rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _normalize_text(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


def check_citations(citations: tuple[Citation, ...], fetched: Mapping[str, str]) -> CitationCheck:
    """Keep only citations whose URL was fetched in this run.

    `fetched` maps normalized URL to the page text the tool returned. Quotes are not yet a gate
    (the verifier pass arrives in Session 3), but we count verbatim matches so the spike can
    measure how often the model quotes accurately.
    """
    kept: list[Citation] = []
    dropped: list[Citation] = []
    quotes_found = 0
    for citation in citations:
        page_text = fetched.get(normalize_url(citation.url))
        if page_text is None:
            dropped.append(citation)
            continue
        kept.append(citation)
        if _normalize_text(citation.quote) in _normalize_text(page_text):
            quotes_found += 1
    return CitationCheck(kept=tuple(kept), dropped=tuple(dropped), quotes_found=quotes_found)
