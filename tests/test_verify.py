from __future__ import annotations

import pytest

from agent.schemas import Citation
from agent.verify import check_citations, normalize_url


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (
            "https://en.wikipedia.org/wiki/Neutron_star",
            "https://EN.Wikipedia.org/wiki/Neutron_star",
        ),
        (
            "https://en.wikipedia.org/wiki/Neutron_star",
            "https://en.wikipedia.org/wiki/Neutron%20star",
        ),
        (
            "https://en.wikipedia.org/wiki/Neutron_star",
            "https://en.wikipedia.org/wiki/Neutron star",
        ),
        (
            "https://en.wikipedia.org/wiki/Neutron_star",
            "https://en.wikipedia.org/wiki/Neutron_star#History",
        ),
        ("https://science.nasa.gov/universe/stars/", "https://science.nasa.gov/universe/stars"),
    ],
)
def test_equivalent_urls_normalize_the_same(a: str, b: str) -> None:
    assert normalize_url(a) == normalize_url(b)


def test_query_strings_are_kept_distinct() -> None:
    assert normalize_url("https://example.org/page?id=1") != normalize_url(
        "https://example.org/page?id=2"
    )


def test_only_fetched_urls_are_kept() -> None:
    fetched = {
        normalize_url("https://en.wikipedia.org/wiki/Neutron_star"): "A neutron star is dense."
    }
    citations = (
        Citation(
            url="https://en.wikipedia.org/wiki/Neutron%20star", quote="A neutron star is dense."
        ),
        Citation(url="https://en.wikipedia.org/wiki/Pulsar", quote="Pulsars spin."),
    )

    check = check_citations(citations, fetched)

    assert [c.url for c in check.kept] == ["https://en.wikipedia.org/wiki/Neutron%20star"]
    assert [c.url for c in check.dropped] == ["https://en.wikipedia.org/wiki/Pulsar"]
    assert check.passed


def test_no_fetched_citations_fails() -> None:
    check = check_citations((Citation(url="https://example.org/x", quote="q"),), {})
    assert not check.passed
    assert check.quotes_found == 0


def test_quotes_match_ignoring_case_and_whitespace_only() -> None:
    url = "https://en.wikipedia.org/wiki/Moon"
    fetched = {normalize_url(url): "The Moon is Earth's only\n natural satellite."}
    citations = (
        Citation(url=url, quote="the moon is EARTH'S only natural   satellite."),
        Citation(url=url, quote="The Moon is Earth's natural satellite."),  # paraphrased
    )

    check = check_citations(citations, fetched)

    assert len(check.kept) == 2
    assert check.quotes_found == 1
