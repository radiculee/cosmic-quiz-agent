"""The eval's planted faults and report, on synthetic records: no paid calls."""

from __future__ import annotations

import random
from pathlib import Path

from agent.config import Settings
from agent.schemas import (
    Citation,
    CitationCheck,
    CodeCheck,
    HaikuReport,
    ItemRecord,
    JevCheck,
    JevReport,
    QuizItem,
    RunResult,
    Verification,
)
from agent.verify import code_check
from evals.report import write_report
from evals.seeding import (
    SeededItem,
    SeededResult,
    build_seeded_set,
    plant_fake_quote,
    plant_true_distractor,
    plant_unsupported_claim,
    plant_wrong_number,
)
from tests.conftest import FakeLLM

URL = "https://en.wikipedia.org/wiki/Neutron_star"
PAGE = (
    "A neutron star is the collapsed core of a massive star. Neutron stars have a radius on the "
    "order of 10 kilometres and a mass of about 1.4 solar masses. The first was found in 1967."
)
PAGES = {URL: PAGE}
ITEM = QuizItem(
    question="What is a neutron star?",
    options=("A young planet", "A collapsed stellar core", "A comet", "A gas cloud"),
    correct_index=1,
    explanation=(
        "A neutron star is the collapsed core of a massive star. It is about 10 kilometres "
        "across and has about 1.4 solar masses. The first one was found in 1967."
    ),
    citations=(Citation(url=URL, quote="A neutron star is the collapsed core of a massive star."),),
)


def seeded(item: QuizItem, fault: str = "wrong_number") -> SeededItem:
    return SeededItem.model_validate(
        {
            "id": f"{fault}-01",
            "fault": fault,
            "description": "test",
            "topic": "Neutron stars",
            "difficulty": "easy",
            "item": item.model_dump(),
            "pages": PAGES,
        }
    )


def test_wrong_number_is_caught_by_layer_one() -> None:
    planted = plant_wrong_number(ITEM, PAGES, random.Random(1))

    assert planted is not None
    item, description = planted
    assert item.explanation != ITEM.explanation and "changed to" in description
    check = code_check(item, seeded(item).fetched)
    assert not check.passed and len(check.unsupported_numbers) == 1


def test_wrong_number_needs_a_sourced_number() -> None:
    no_numbers = ITEM.model_copy(update={"explanation": "A neutron star is a collapsed core."})
    assert plant_wrong_number(no_numbers, PAGES, random.Random(1)) is None


def test_fake_quote_is_caught_by_layer_one() -> None:
    planted = plant_fake_quote(ITEM, random.Random(1))

    assert planted is not None
    item, _ = planted
    assert item.citations[0].quote == "A neutron star is not the collapsed core of a massive star."
    check = code_check(item, seeded(item, "fake_quote").fetched)
    assert len(check.citations.misquoted) == 1


def test_unsupported_claim_is_inserted_and_must_avoid_digits(settings: Settings) -> None:
    llm = FakeLLM(json_replies=[{"sentence": "Neutron stars glow faintly green in old age."}])
    planted = plant_unsupported_claim(ITEM, PAGES, llm, settings)

    assert planted is not None
    assert (
        "collapsed core of a massive star. Neutron stars glow faintly green"
        in planted[0].explanation
    )
    with_digits = FakeLLM(json_replies=[{"sentence": "They glow green for 5 years."}])
    assert plant_unsupported_claim(ITEM, PAGES, with_digits, settings) is None


def test_true_distractor_replaces_a_wrong_option(settings: Settings) -> None:
    llm = FakeLLM(json_replies=[{"option": "The remnant core of a massive star"}])
    planted = plant_true_distractor(ITEM, PAGES, llm, settings, random.Random(1))

    assert planted is not None
    item = planted[0]
    assert "The remnant core of a massive star" in item.distractors
    assert item.correct_option == ITEM.correct_option
    duplicate = FakeLLM(json_replies=[{"option": "A comet"}])  # would make options repeat
    assert plant_true_distractor(ITEM, PAGES, duplicate, settings, random.Random(1)) is None


def record(item: QuizItem = ITEM, haiku: str = "pass", jev: str = "pass") -> ItemRecord:
    checks = (
        JevCheck(
            kind="correct_answer",
            claim="x",
            verdict="supports",
            confidence=0.95,
            probabilities={"supports": 0.95, "contradicts": 0.02, "says_nothing": 0.03},
        ),
        JevCheck(
            kind="distractor",
            claim="y",
            verdict="contradicts",
            confidence=0.9,
            probabilities={"supports": 0.05, "contradicts": 0.9, "says_nothing": 0.05},
        ),
    )
    code = CodeCheck(citations=CitationCheck(kept=item.citations))
    run = RunResult(
        mode="quiz",
        topic="Neutron stars",
        difficulty="easy",
        model="claude-haiku-4-5",
        outcome="passed",
        answer=item,
        code_check=code,
        cited_pages=PAGES,
        model_calls=3,
        cost_usd=0.02,
        seconds=12.0,
    )
    verification = Verification(
        code=code,
        haiku=HaikuReport(verdict=haiku, cost_usd=0.006, seconds=3.0),  # type: ignore[arg-type]
        jev=JevReport(verdict=jev, checks=checks, cost_usd=0.0002, seconds=0.3),  # type: ignore[arg-type]
    )
    return ItemRecord(run=run, verification=verification, status="published", rule="all_must_pass")


def test_seeded_set_uses_only_items_that_passed(settings: Settings) -> None:
    failed = record().model_copy(
        update={
            "run": record().run.model_copy(update={"outcome": "failed_checks", "code_check": None})
        }
    )
    # One eligible item, so one model call per model-planted fault type, in this order.
    llm = FakeLLM(
        json_replies=[
            {"sentence": "Neutron stars hum quietly."},
            {"option": "The remnant core of a massive star"},
        ]
    )

    items, _ = build_seeded_set([record(), failed], llm, settings)

    assert {s.fault for s in items} == {
        "wrong_number",
        "fake_quote",
        "unsupported_claim",
        "true_distractor",
    }
    assert all(s.topic == "Neutron stars" for s in items)


def test_report_builds_from_stored_results(tmp_path: Path) -> None:
    items = [record(), record(haiku="borderline"), record(jev="fail")]
    planted = plant_fake_quote(ITEM, random.Random(1))
    assert planted is not None
    entry = seeded(planted[0], "fake_quote")
    results = [
        SeededResult(
            seeded=entry,
            verification=Verification(code=code_check(entry.item, entry.fetched)),
        )
    ]

    path = write_report(tmp_path, items, results)

    report = path.read_text(encoding="utf-8")
    assert "## 3. Planted errors" in report and "fake_quote" in report
    assert "Agreement on pass / not pass: 33% (1/3)" in report
    assert (tmp_path / "summary.json").exists()
    assert "## 1. Neutron stars (easy)" in (tmp_path / "hand_review.md").read_text(encoding="utf-8")
