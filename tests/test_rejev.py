"""The Jev-only re-check of stored eval items, with a fake Jev: no paid calls."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

from agent.config import JevCriteria, Settings
from agent.schemas import JevVerdict
from agent.verifiers.jev import CRITERIA
from evals import rejev
from evals.seeding import SeededResult
from tests.test_evals import ITEM, record, seeded
from tests.test_verifiers import FakeJev

SUPPORTED = {"supports": 0.95, "contradicts": 0.02, "says_nothing": 0.03}


def test_every_criteria_version_defines_every_verdict() -> None:
    assert set(CRITERIA) == set(get_args(JevCriteria))
    for wording in CRITERIA.values():
        assert set(wording) == set(get_args(JevVerdict))


def test_recheck_item_records_the_criteria_and_recomputes_the_status(settings: Settings) -> None:
    astro = settings.model_copy(update={"jev_criteria": "astro-1"})
    stored = record()

    unchanged = rejev.recheck_item(stored, FakeJev(), astro)
    supported_distractor = rejev.recheck_item(stored, FakeJev({"distractor_0": SUPPORTED}), astro)

    assert unchanged.verification is not None and unchanged.verification.jev is not None
    assert unchanged.verification.jev.criteria == "astro-1"
    assert unchanged.verification.haiku == stored.verification.haiku  # type: ignore[union-attr]
    assert unchanged.status == "published"
    assert supported_distractor.status == "discarded"


def test_recheck_seeded_keeps_the_planted_item_and_logs_the_cost(settings: Settings) -> None:
    verification = record().verification
    assert verification is not None
    stored = SeededResult(seeded=seeded(ITEM), verification=verification)

    result = rejev.recheck_seeded(stored, FakeJev(), settings)

    assert result.seeded == stored.seeded
    assert result.typesafe_cost_usd > 0


def test_comparison_counts_changes_and_marks_hand_reviewed_items(
    tmp_path: Path, settings: Settings
) -> None:
    (tmp_path / rejev.HAND_REVIEW_FILE).write_text(
        "# Hand review\n\n## 1. Neutron stars (easy): published\n", encoding="utf-8"
    )
    old = [record()]
    new = [rejev.recheck_item(old[0], FakeJev({"distractor_0": SUPPORTED}), settings)]

    path = rejev.write_comparison(tmp_path, "astro-1", "generic-1", old, new, [], [])

    text = path.read_text(encoding="utf-8")
    assert path.name == "rejev_astro-1.md"
    assert "| published | 1 | 0 |" in text
    assert "| discarded | 0 | 1 |" in text
    assert "Neutron stars (easy) [hand-reviewed]" in text
    assert "pass -> fail" in text
    assert rejev.stored_criteria(old) == "generic-1"
