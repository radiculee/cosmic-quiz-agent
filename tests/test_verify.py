from __future__ import annotations

import pytest

from agent.schemas import Citation, Explanation, QuizItem
from agent.verify import (
    check_citations,
    check_numbers,
    checked_texts,
    code_check,
    normalize_url,
    numbers_in,
)

MOON = "https://en.wikipedia.org/wiki/Moon"
MOON_TEXT = "The Moon is Earth's only\n natural satellite. It orbits at 384,399 km every 27.3 days."


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


def test_citations_are_sorted_into_kept_unfetched_and_misquoted() -> None:
    fetched = {normalize_url(MOON): MOON_TEXT}
    citations = (
        Citation(url=MOON, quote="the moon is EARTH'S only natural   satellite."),
        Citation(url=MOON, quote="The Moon is Earth's natural satellite."),  # paraphrased
        Citation(url="https://en.wikipedia.org/wiki/Mars", quote="Mars is red."),
    )

    check = check_citations(citations, fetched)

    assert [c.quote for c in check.kept] == ["the moon is EARTH'S only natural   satellite."]
    assert [c.quote for c in check.misquoted] == ["The Moon is Earth's natural satellite."]
    assert [c.url for c in check.unfetched] == ["https://en.wikipedia.org/wiki/Mars"]
    assert check.passed


def test_no_valid_citations_fails() -> None:
    check = check_citations((Citation(url="https://example.org/x", quote="q"),), {})
    assert not check.passed


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("about 1,000 times less.", ["1000"]),
        ("16.35 days and 500 FRBs in 2007.", ["16.35", "500", "2007"]),
        ("2.72548 K", ["2.72548"]),
        ("radius of 10 kilometers (6 miles)", ["10", "6"]),
        ("v2.0 at 3.5x", []),  # never part of a word
        ("a billionth of a second", []),  # words cannot be checked
    ],
)
def test_numbers_in(text: str, expected: list[str]) -> None:
    assert numbers_in(text) == expected


def test_numbers_must_appear_in_a_page() -> None:
    pages = ["Webb launched in 2021 with a 6.5-metre mirror weighing 1000 kg."]

    missing = check_numbers(
        ["Launched in 2021, it has a 6.5 m mirror and 1,000 kg, at 50 K."], pages
    )

    assert missing == ("50",)


def test_quiz_numbers_skip_distractors() -> None:
    item = QuizItem(
        question="How far away is the Moon on average?",
        options=("384,399 km", "150 million km", "1 million km", "42,000 km"),
        correct_index=0,
        explanation="The Moon orbits at 384,399 km.",
        citations=(Citation(url=MOON, quote="It orbits at 384,399 km"),),
    )

    assert "150 million km" not in " ".join(checked_texts(item))
    check = code_check(item, {normalize_url(MOON): MOON_TEXT})
    assert check.passed and check.unsupported_numbers == ()


def test_code_check_reports_every_problem() -> None:
    answer = Explanation(
        explanation="The Moon orbits every 29.5 days.",
        citations=(
            Citation(url=MOON, quote="It orbits every 29.5 days."),
            Citation(url="https://en.wikipedia.org/wiki/Sun", quote="The Sun is a star."),
        ),
    )

    check = code_check(answer, {normalize_url(MOON): MOON_TEXT})

    assert not check.passed
    assert len(check.problems) == 3  # misquoted, not read, and 29.5 is not on the page
    assert any("not word for word" in p for p in check.problems)
    assert any("not read" in p for p in check.problems)
    assert check.unsupported_numbers == ("29.5",)


# Typographic characters, by code point, so the test source stays plain ASCII.
EN_DASH, MINUS, ZWJ, NBSP = chr(0x2013), chr(0x2212), chr(0x200D), chr(0x00A0)
LEFT_QUOTE, RIGHT_QUOTE = chr(0x2018), chr(0x2019)


@pytest.mark.parametrize(
    ("quote", "page"),
    [
        ("mass-energy content", f"mass{EN_DASH}energy content"),
        ("speed of 0.24c", f"speed of 0.24{ZWJ}c"),
        ("PSR J1748-2446ad", f"PSR J1748{MINUS}2446ad"),
        ("it's a 'disc'", f"it{RIGHT_QUOTE}s a {LEFT_QUOTE}disc{RIGHT_QUOTE}"),
        ("a radius of 10 km", f"a radius of{NBSP}10 km"),
    ],
)
def test_quotes_match_across_typographic_variants(quote: str, page: str) -> None:
    from agent.verify import quote_on_page

    assert quote_on_page(quote, page)


def test_numbers_are_checked_against_pages_with_misquoted_citations() -> None:
    answer = Explanation(
        explanation="The Moon orbits at 384,399 km.",
        citations=(Citation(url=MOON, quote="The Moon orbits at 384,399 km."),),  # paraphrase
    )

    check = code_check(answer, {normalize_url(MOON): MOON_TEXT})

    assert len(check.citations.misquoted) == 1
    assert check.unsupported_numbers == ()  # 384,399 is on the page the agent read
