"""Layer 1 of the publish gate: deterministic checks on agent output, enforced in code.

- A source may only be a URL that was actually read during the run.
- Every quote must appear word for word (ignoring case and spacing) on the page it cites.
- Every number in the question, the correct answer and the explanation must appear in a cited page.

Numbers are compared as written in digits ("1,000" and "1000" match). Numbers written in words
("a billionth") cannot be checked here, which is why the prompt asks for numbers as the source
writes them and the verifiers check claims as well.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from urllib.parse import unquote, urlsplit, urlunsplit

from agent.schemas import Answer, Citation, CitationCheck, CodeCheck, QuizItem

_WHITESPACE = re.compile(r"\s+")
# Typographic variants that should not decide whether a quote is genuine: dashes and minus signs,
# curly quotes, non-breaking spaces, and invisible characters (zero-width spaces and joiners,
# soft hyphens). Found on real pages in the Session 3 eval.
_EQUIVALENT_CHARACTERS = str.maketrans(
    {
        "\u2010": "-",  # hyphen
        "\u2011": "-",  # non-breaking hyphen
        "\u2012": "-",  # figure dash
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2212": "-",  # minus sign
        "\u2018": "'",  # left single quote
        "\u2019": "'",  # right single quote
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
        "\u00a0": " ",  # non-breaking space
        "\u200b": None,  # zero-width space
        "\u200c": None,  # zero-width non-joiner
        "\u200d": None,  # zero-width joiner
        "\u2060": None,  # word joiner
        "\ufeff": None,  # byte order mark
        "\u00ad": None,  # soft hyphen
    }
)
# Digits with optional thousands separators and decimals; minus signs are ignored.
_NUMBER = re.compile(
    r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?!\.?\w)"  # 1,000 or 12,345.6
    r"|(?<![\w.,])\d+(?:\.\d+)?(?!\.?\w)"  # 1000, 16.35; never part of "v2.0" or "3.5x"
)


def normalize_url(url: str) -> str:
    """Canonical form for comparing URLs.

    Lower-cases the scheme and host, drops the fragment and any trailing slash, decodes
    percent-escapes in the path, and treats spaces and underscores in paths as the same
    (Wikipedia uses both for article titles).
    """
    parts = urlsplit(url.strip())
    path = unquote(parts.path).replace(" ", "_").rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def normalize_text(text: str) -> str:
    """Form used for quote matching: ignores case, spacing and typographic variants."""
    return _WHITESPACE.sub(" ", text.translate(_EQUIVALENT_CHARACTERS)).strip().casefold()


def quote_on_page(quote: str, page_text: str) -> bool:
    return normalize_text(quote) in normalize_text(page_text)


def check_citations(citations: Iterable[Citation], fetched: Mapping[str, str]) -> CitationCheck:
    """Keep only citations whose URL was read in this run and whose quote is on that page.

    `fetched` maps normalized URL to the page text the tool returned to the model.
    """
    kept: list[Citation] = []
    unfetched: list[Citation] = []
    misquoted: list[Citation] = []
    for citation in citations:
        page_text = fetched.get(normalize_url(citation.url))
        if page_text is None:
            unfetched.append(citation)
        elif not quote_on_page(citation.quote, page_text):
            misquoted.append(citation)
        else:
            kept.append(citation)
    return CitationCheck(kept=tuple(kept), unfetched=tuple(unfetched), misquoted=tuple(misquoted))


def numbers_in(text: str) -> list[str]:
    """Numbers written in digits, normalized by removing thousands separators."""
    return [match.replace(",", "") for match in _NUMBER.findall(text)]


def check_numbers(texts: Iterable[str], pages: Iterable[str]) -> tuple[str, ...]:
    """Numbers in `texts` that appear in none of `pages`, in first-seen order."""
    available = {number for page in pages for number in numbers_in(page)}
    missing: list[str] = []
    for text in texts:
        for number in numbers_in(text):
            if number not in available and number not in missing:
                missing.append(number)
    return tuple(missing)


def checked_texts(answer: Answer) -> list[str]:
    """The parts of an answer that state facts: distractors are wrong on purpose and excluded."""
    if isinstance(answer, QuizItem):
        return [answer.question, answer.correct_option, answer.explanation]
    return [answer.explanation]


def cited_pages(citations: Iterable[Citation], fetched: Mapping[str, str]) -> dict[str, str]:
    """URL to page text for each distinct cited URL that was read in the run."""
    pages: dict[str, str] = {}
    for citation in citations:
        text = fetched.get(normalize_url(citation.url))
        if text is not None and citation.url not in pages:
            pages[citation.url] = text
    return pages


def code_check(answer: Answer, fetched: Mapping[str, str]) -> CodeCheck:
    """Run every layer 1 check. Numbers are matched against the cited pages that were read."""
    citations = check_citations(answer.citations, fetched)
    # Every cited page the agent read counts, even if its quote was wrong: otherwise one bad
    # quote makes every number on that page look unsupported.
    pages = cited_pages(answer.citations, fetched).values()
    return CodeCheck(
        citations=citations,
        unsupported_numbers=check_numbers(checked_texts(answer), pages),
    )
