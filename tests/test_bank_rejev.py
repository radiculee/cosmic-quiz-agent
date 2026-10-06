"""Re-checking items whose Jev check failed: reading them back, re-running Jev, re-deciding.

`tests/test_rejev.py` covers the eval command of the same name; this file covers the
Curator's bank command (`python -m curator rejev`). Nothing touches the network.
"""

from __future__ import annotations

import argparse
import json

import httpx2
import pytest

import curator.__main__ as cli
from agent.config import Settings
from agent.schemas import ItemRecord, JevCheck, JevReport, Status
from agent.store import JevRecheck, SupabaseStore
from tests.test_evals import PAGES
from tests.test_store import BASE, quiz_record, store_with


def failed_jev(record: ItemRecord, haiku: str = "pass") -> ItemRecord:
    """The stored record of a run whose Jev check could not be made."""
    verification = record.verification
    assert verification is not None and verification.haiku is not None
    return record.model_copy(
        update={
            "status": "review",
            "verification": verification.model_copy(
                update={
                    "haiku": verification.haiku.model_copy(
                        update={"verdict": haiku, "reasons": ()}
                    ),
                    "jev": JevReport(
                        verdict="error", reasons=("TypeSafeAuthenticationError: 401",)
                    ),
                }
            ),
        }
    )


def jev_report(verdict: str = "pass") -> JevReport:
    return JevReport.model_validate(
        {
            "verdict": verdict,
            "model": "jev-1.13.0",
            "criteria": "astro-1",
            "threshold": 0.8,
            "checks": [
                JevCheck(
                    kind="correct_answer",
                    claim="The answer is: A collapsed stellar core",
                    verdict="supports",
                    confidence=0.99,
                    probabilities={"supports": 0.99, "contradicts": 0.0, "says_nothing": 0.01},
                ).model_dump()
            ],
            "input_tokens": 3000,
            "cost_usd": 0.000126,
            "seconds": 0.4,
        }
    )


# --- The store -------------------------------------------------------------------------------


def test_targets_are_review_items_with_a_failed_jev_check_and_their_pages() -> None:
    seen: list[httpx2.Request] = []
    record = failed_jev(quiz_record())

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.url.path.endswith("/items"):
            row = {"id": 41, "run_id": 7, "topics": {"name": "Neutron stars"}}
            return httpx2.Response(
                200, json=[{**row, "runs": {"record": record.model_dump(mode="json")}}]
            )
        pages = [{"run_id": 7, "url": url, "page_text": text} for url, text in PAGES.items()]
        return httpx2.Response(200, json=pages)

    targets = store_with(handler).jev_recheck_targets()

    params = seen[0].url.params
    assert params["status"] == "eq.review" and params["jev_verdict"] == "eq.error"
    assert seen[1].url.params["run_id"] == "in.(7)"
    assert [(t.item_id, t.topic) for t in targets] == [(41, "Neutron stars")]
    assert targets[0].pages == PAGES
    assert targets[0].record.run.answer == record.run.answer


def test_a_recheck_is_stored_with_one_rpc_call() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(204)

    store_with(handler).apply_jev_recheck(41, "published", jev_report())

    assert str(seen[0].url) == f"{BASE}/rest/v1/rpc/apply_jev_recheck"
    body = json.loads(seen[0].content)
    assert body["p_item_id"] == 41 and body["p_status"] == "published"
    jev = body["p_jev"]
    assert jev["verdict"] == "pass" and jev["criteria"] == "astro-1" and jev["input_tokens"] == 3000
    assert jev["checks"][0]["layer"] == "jev" and jev["checks"][0]["model"] == "jev-1.13.0"


# --- The command -----------------------------------------------------------------------------


class FakeStore:
    def __init__(self, targets: list[JevRecheck]) -> None:
        self.targets = targets
        self.applied: list[tuple[int, Status, JevReport]] = []

    def jev_recheck_targets(self) -> list[JevRecheck]:
        return self.targets

    def apply_jev_recheck(self, item_id: int, status: Status, jev: JevReport) -> None:
        self.applied.append((item_id, status, jev))


def run_command(monkeypatch: pytest.MonkeyPatch, store: FakeStore, reports: list[JevReport]) -> int:
    monkeypatch.setattr(cli, "make_jev", lambda settings: object())
    monkeypatch.setattr(cli, "verify_with_jev", lambda *_args: reports.pop(0))
    args = argparse.Namespace(yes=True)
    return cli.command_rejev(args, Settings(), store)  # type: ignore[arg-type]


def target(item_id: int, haiku: str = "pass") -> JevRecheck:
    return JevRecheck(
        item_id=item_id,
        topic="Neutron stars",
        record=failed_jev(quiz_record(), haiku),
        pages=PAGES,
    )


def test_rejev_applies_the_gate_again_with_the_new_jev_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore([target(41), target(42, haiku="borderline")])

    status = run_command(monkeypatch, store, [jev_report("pass"), jev_report("pass")])

    assert status == 0
    # Both layers pass: published. A Haiku doubt still sends the item to review.
    assert [(item_id, decided) for item_id, decided, _ in store.applied] == [
        (41, "published"),
        (42, "review"),
    ]


def test_a_jev_failure_changes_nothing_and_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore([target(41)])

    status = run_command(monkeypatch, store, [JevReport(verdict="error", reasons=("401 again",))])

    assert status == 1  # a scheduled or manual run shows as failed, so a bad key is noticed
    assert store.applied == []


def test_nothing_to_recheck_costs_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store = FakeStore([])

    assert run_command(monkeypatch, store, []) == 0
    assert "No item is waiting" in capsys.readouterr().out


def test_the_store_is_a_supabase_store() -> None:
    # The command is typed against the real store; the fake above mirrors its two methods.
    assert hasattr(SupabaseStore, "jev_recheck_targets")
    assert hasattr(SupabaseStore, "apply_jev_recheck")
