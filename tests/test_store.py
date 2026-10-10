"""What is stored for each run, and the Supabase REST client against a mock transport."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

import httpx2
import pytest

from agent.llm import Usage
from agent.schemas import (
    Citation,
    CitationCheck,
    CodeCheck,
    DistractorJudgement,
    Explanation,
    HaikuReport,
    ItemRecord,
    JevCheck,
    JevReport,
    RunResult,
    Step,
    Verification,
)
from agent.store import (
    CuratorSummary,
    ItemPayload,
    StoreError,
    SupabaseStore,
    TopicRef,
    build_payload,
    domain,
    job_key,
)
from tests.test_evals import ITEM, PAGES, URL

TOPIC = TopicRef(name="Neutron stars", kind="evergreen")
BASE = "https://example.supabase.co"

STEPS = (
    Step(index=0, kind="model", summary="search_wikipedia", seconds=1.0, usage=Usage()),
    Step(index=1, kind="tool", summary="ok", seconds=0.5, tool="search_wikipedia"),
    Step(index=2, kind="tool", summary="ok", seconds=0.8, tool="fetch_page"),
    Step(index=3, kind="tool", summary="error", seconds=0.2, tool="fetch_page", is_error=True),
)


def quiz_record() -> ItemRecord:
    code = CodeCheck(
        citations=CitationCheck(
            kept=ITEM.citations,
            misquoted=(Citation(url=URL, quote="Not on the page."),),
        )
    )
    run = RunResult(
        mode="quiz",
        topic="Neutron stars",
        difficulty="medium",
        model="claude-haiku-4-5",
        outcome="passed",
        answer=ITEM,
        code_check=code,
        cited_pages=PAGES,
        fetched_urls=(
            URL,
            "https://www.nasa.gov/neutron-stars/",
            "https://en.wikipedia.org/wiki/Pulsar",
        ),
        # A redirect: the NASA page was read once but recorded under two URLs.
        pages_read=(URL, "https://www.nasa.gov/neutron-stars/"),
        steps=STEPS,
        model_calls=3,
        nudges=1,
        usage=Usage(
            input_tokens=5000, output_tokens=400, cache_write_tokens=0, cache_read_tokens=900
        ),
        cost_usd=0.021,
        seconds=14.2,
    )
    haiku = HaikuReport(
        verdict="borderline",
        reasons=("explanation: a small doubt",),
        answer_verdict="supported",
        answer_quote="A neutron star is the collapsed core of a massive star.",
        answer_quote_verbatim=True,
        distractors=tuple(
            DistractorJudgement(option=o, verdict="wrong", reason="no") for o in ITEM.distractors
        ),
        explanation_problems=("a small doubt",),
        usage=Usage(input_tokens=3000, output_tokens=200),
        cost_usd=0.004,
        seconds=3.1,
    )
    jev = JevReport(
        verdict="pass",
        model="jev-1.13.0",
        criteria="astro-1",
        checks=(
            JevCheck(
                kind="correct_answer",
                claim="The answer is: A collapsed stellar core",
                verdict="supports",
                confidence=0.99,
                probabilities={"supports": 0.99, "contradicts": 0.0, "says_nothing": 0.01},
            ),
        ),
        input_tokens=2000,
        cost_usd=0.000084,
        seconds=0.3,
    )
    verification = Verification(code=code, haiku=haiku, jev=jev)
    return ItemRecord(run=run, verification=verification, status="review", rule="all_must_pass")


def test_payload_holds_the_run_metrics_for_analytics() -> None:
    payload = build_payload(quiz_record(), TOPIC, "curator", curator_run_id=7)
    run = payload.run

    assert run.curator_run_id == 7 and run.source == "curator"
    assert run.tool_calls == {"search_wikipedia": 1, "fetch_page": 2}
    assert run.tool_errors == 1
    assert run.pages_by_domain == {"en.wikipedia.org": 1, "nasa.gov": 1}
    assert run.nudges == 1 and run.budget_reason is None
    assert run.cache_read_tokens == 900
    assert run.verifier_input_tokens == 3000 and run.verifier_cost_usd == 0.004
    assert run.jev_input_tokens == 2000 and run.jev_cost_usd == pytest.approx(0.000084)
    # Page text is stored once, in cited_pages, not again inside the record.
    assert run.record["run"]["cited_pages"] == {}
    assert [(p.url, p.page_text) for p in payload.cited_pages] == list(PAGES.items())


def test_quiz_item_row_has_every_layer_per_claim() -> None:
    item = build_payload(quiz_record(), TOPIC, "curator").item

    assert item is not None
    assert item.status == "review" and item.gate_rule == "all_must_pass"
    assert item.options == list(ITEM.options) and item.correct_index == ITEM.correct_index
    assert item.haiku_verdict == "borderline" and item.jev_verdict == "pass"
    assert item.jev_criteria == "astro-1" and item.jev_threshold == 0.8
    assert [(s.ordinal, s.url) for s in item.sources] == [(0, URL)]
    layers = [(c.layer, c.kind, c.verdict) for c in item.claim_checks]
    assert ("code", "citation", "kept") in layers
    assert ("code", "citation", "misquoted") in layers
    assert ("haiku", "correct_answer", "supported") in layers
    assert layers.count(("haiku", "distractor", "wrong")) == 3
    assert ("haiku", "explanation", "problem") in layers
    jev = [c for c in item.claim_checks if c.layer == "jev"]
    assert jev[0].confidence == 0.99 and jev[0].model == "jev-1.13.0"


def test_learn_item_has_no_question_fields() -> None:
    record = quiz_record()
    explanation = Explanation(
        explanation="A neutron star is a collapsed core.", citations=ITEM.citations
    )
    learn = record.model_copy(
        update={"run": record.run.model_copy(update={"mode": "learn", "answer": explanation})}
    )

    item = build_payload(learn, TOPIC, "curator").item

    assert item is not None
    assert item.mode == "learn" and item.question is None and item.options is None
    assert item.correct_index is None


def test_failed_and_empty_runs() -> None:
    record = quiz_record()
    failed_code = CodeCheck(citations=CitationCheck(kept=(), unfetched=ITEM.citations))
    failed = ItemRecord(
        run=record.run.model_copy(update={"outcome": "failed_checks", "code_check": failed_code}),
        status="discarded",
        rule="all_must_pass",
    )
    empty = ItemRecord(
        run=record.run.model_copy(
            update={"outcome": "budget_exceeded", "detail": "step budget", "answer": None}
        )
    )

    failed_item = build_payload(failed, TOPIC, "curator").item
    empty_payload = build_payload(empty, TOPIC, "curator")

    assert failed_item is not None
    assert failed_item.status == "discarded" and not failed_item.code_passed
    assert failed_item.haiku_verdict is None
    # Citation rule: a URL that was not read is never stored where a player could see it.
    assert failed_item.sources == []
    assert all(URL not in problem for problem in failed_item.code_problems)
    assert failed_item.code_problems[0] == "1 cited URL(s) not read in this run, dropped"
    unfetched = [c for c in failed_item.claim_checks if c.verdict == "unfetched"]
    assert len(unfetched) == 1 and unfetched[0].source_url is None
    assert {c.layer for c in failed_item.claim_checks} == {"code"}
    assert empty_payload.item is None
    assert empty_payload.run.budget_reason == "step budget"


def test_payload_round_trips_through_json_for_the_pending_folder() -> None:
    payload = build_payload(quiz_record(), TOPIC, "curator", 3)
    assert ItemPayload.model_validate_json(payload.model_dump_json()) == payload


def test_job_keys_and_domains_ignore_case_and_www() -> None:
    assert job_key(" Neutron Stars ", "quiz", "easy") == job_key("neutron stars", "quiz", "easy")
    assert domain("https://WWW.esa.int/Science") == "esa.int"


# --- SupabaseStore over a mock transport --------------------------------------------------------


Handler = Callable[[httpx2.Request], httpx2.Response]


def store_with(handler: Handler) -> SupabaseStore:
    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    return SupabaseStore(BASE, "sb_secret_test", client=client, retry_backoff_seconds=0.0)


def test_record_item_calls_the_rpc_with_the_secret_key() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json={"topic_id": 1, "run_id": 2, "item_id": 3})

    ids = store_with(handler).record_item(build_payload(quiz_record(), TOPIC, "curator"))

    assert (ids.topic_id, ids.run_id, ids.item_id) == (1, 2, 3)
    request = seen[0]
    assert str(request.url) == f"{BASE}/rest/v1/rpc/record_item"
    assert request.headers["apikey"] == "sb_secret_test"
    body = json.loads(request.content)
    assert body["payload"]["topic"]["name"] == "Neutron stars"


def test_reads_retry_server_errors_but_creating_a_run_row_does_not() -> None:
    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx2.Response(503, text="busy")
        return httpx2.Response(
            200, json=[{"topic": "Quasars", "mode": "quiz", "difficulty": "hard"}]
        )

    jobs = store_with(handler).attempted_jobs(["Quasars"])
    assert jobs == {job_key("quasars", "quiz", "hard")}
    assert len(calls) == 2

    def busy(_request: httpx2.Request) -> httpx2.Response:
        calls.append("write")
        return httpx2.Response(503, text="busy")

    calls.clear()
    with pytest.raises(StoreError, match="503") as raised:
        store_with(busy).start_curator_run("build", ["Quasars"], 6.0)
    assert calls == ["write"]  # creating a run row is sent once
    assert not raised.value.permanent


def test_unexpected_replies_and_client_errors_raise_store_errors() -> None:
    def bad_reply(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"unexpected": True})

    def not_found(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(404, json={"message": "Could not find the function"})

    with pytest.raises(StoreError, match="unexpected reply"):
        store_with(bad_reply).retire_stale()
    with pytest.raises(StoreError, match="404"):
        store_with(not_found).topics()


def test_curator_run_rows_are_created_and_finished() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.method == "POST":
            return httpx2.Response(201, json=[{"id": 42}])
        return httpx2.Response(204)

    store = store_with(handler)
    run_id = store.start_curator_run("build", ["Quasars"], 6.0)
    store.finish_curator_run(run_id, CuratorSummary(published=2, log=("hello",)))

    assert run_id == 42
    assert seen[0].headers["prefer"] == "return=representation"
    patch = seen[1]
    assert patch.method == "PATCH" and patch.url.params["id"] == "eq.42"
    body = json.loads(patch.content)
    assert body["published"] == 2 and body["log"] == ["hello"] and body["finished_at"]


def test_from_env_requires_the_url_and_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "x")
    with pytest.raises(StoreError, match="SUPABASE_URL"):
        SupabaseStore.from_env()


def test_a_shared_client_never_carries_the_secret_key_and_stays_open() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=[])

    shared = httpx2.Client(transport=httpx2.MockTransport(handler))
    with SupabaseStore(BASE, "sb_secret_test", client=shared) as store:
        store.topics()

    assert seen[0].headers["apikey"] == "sb_secret_test"
    assert "apikey" not in shared.headers
    assert not shared.is_closed
    shared.close()


def test_a_re_sent_payload_is_reported_as_a_duplicate() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200, json={"topic_id": 1, "run_id": 2, "item_id": 3, "duplicate": True}
        )

    ids = store_with(handler).record_item(build_payload(quiz_record(), TOPIC, "curator"))

    assert ids.duplicate


def test_a_reply_that_is_not_json_is_a_store_error() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, text="<html>gateway</html>")

    with pytest.raises(StoreError, match="not JSON"):
        store_with(handler).topics()


def test_record_item_is_retried_because_the_bank_stores_a_payload_once() -> None:
    calls: list[str] = []

    def flaky(_request: httpx2.Request) -> httpx2.Response:
        calls.append("write")
        if len(calls) < 3:
            return httpx2.Response(503, text="busy")
        return httpx2.Response(200, json={"topic_id": 1, "run_id": 2, "item_id": None})

    ids = store_with(flaky).record_item(build_payload(quiz_record(), TOPIC, "curator"))

    assert ids.run_id == 2 and len(calls) == 3


def test_a_refused_request_is_permanent_and_nul_characters_are_never_sent() -> None:
    sent: list[bytes] = []

    def refuse(request: httpx2.Request) -> httpx2.Response:
        sent.append(request.content)
        return httpx2.Response(400, json={"message": "violates check constraint"})

    record = quiz_record()
    nul = chr(0)
    with_nul = record.model_copy(
        update={"run": record.run.model_copy(update={"cited_pages": {URL: f"text{nul}more"}})}
    )
    with pytest.raises(StoreError) as raised:
        store_with(refuse).record_item(build_payload(with_nul, TOPIC, "curator"))

    assert raised.value.permanent and raised.value.status == 400
    assert len(sent) == 1  # a refusal is not retried
    assert json.loads(sent[0])["payload"]["cited_pages"][0]["page_text"] == "textmore"


def test_topics_are_read_with_their_news_articles() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.params["select"] == "name,kind,lead_url,retire_after"
        return httpx2.Response(
            200,
            json=[
                {
                    "name": "The Cat's Paw Nebula",
                    "kind": "news",
                    "lead_url": "https://science.nasa.gov/x/",
                    "retire_after": "2027-01-01T00:00:00+00:00",
                },
                {"name": "Quasars", "kind": "evergreen", "lead_url": None, "retire_after": None},
            ],
        )

    topics = store_with(handler).topics()

    assert [t.kind for t in topics] == ["news", "evergreen"]
    assert topics[0].lead_url == "https://science.nasa.gov/x/"


def test_reports_today_counts_the_visitor_since_midnight_utc() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=[{"id": 1}, {"id": 2}])

    now = datetime(2026, 10, 9, 15, 30, tzinfo=UTC)
    count = store_with(handler).reports_today("abc", now)

    assert count == 2
    params = seen[0].url.params
    assert seen[0].url.path == "/rest/v1/reports"
    assert params["user_hash"] == "eq.abc"
    assert params["created_at"] == "gte.2026-10-09T00:00:00+00:00"
    assert params["select"] == "id"  # never the hashes themselves


def test_purge_visitor_hashes_calls_the_rpc_and_reads_its_counts() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if len(seen) == 1:
            return httpx2.Response(503)  # safe to repeat, so retried
        return httpx2.Response(200, json={"runs": 3, "rate_limit_windows": 12, "reports": 0})

    purged = store_with(handler).purge_visitor_hashes()

    assert (purged.runs, purged.rate_limit_windows, purged.reports) == (3, 12, 0)
    assert seen[-1].method == "POST" and seen[-1].url.path == "/rest/v1/rpc/purge_visitor_hashes"
    with pytest.raises(StoreError):
        store_with(lambda _r: httpx2.Response(200, json={"runs": -1})).purge_visitor_hashes()
