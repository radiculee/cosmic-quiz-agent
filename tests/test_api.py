"""The public bank reads, the HTTP adapter and the topics endpoint. No network."""

from __future__ import annotations

import io
import json
from email.message import Message

import httpx2
import pytest

from agent.bank import BankReader, _ItemIndexRow, summarize
from agent.rest import PAGE_SIZE, RestClient, StoreError
from agent.store import SupabaseStore
from agent.web import ApiRequest, ApiResponse, Handle, json_response, make_handler, salted_hash
from api import item, report, reveal, topics
from dev.api_server import dispatch

BASE = "https://example.supabase.co"


def row(name: str, mode: str, difficulty: str, kind: str = "evergreen") -> _ItemIndexRow:
    return _ItemIndexRow.model_validate(
        {"mode": mode, "difficulty": difficulty, "topics": {"name": name, "kind": kind}}
    )


def test_summarize_groups_by_topic_in_a_stable_order() -> None:
    rows = [
        row("quasars", "quiz", "hard"),
        row("Auroras", "learn", "medium"),
        row("quasars", "quiz", "easy"),
        row("Auroras", "learn", "easy"),
        row("quasars", "quiz", "easy"),
    ]

    topics_found = summarize(rows)

    assert [t.name for t in topics_found] == ["Auroras", "quasars"]
    assert topics_found[0].learn == ["easy", "medium"] and topics_found[0].quiz == []
    assert topics_found[1].quiz == ["easy", "hard"]


def test_reads_page_through_more_than_one_reply() -> None:
    offsets: list[str] = []
    full_page = [
        {"mode": "quiz", "difficulty": "easy", "topics": {"name": "Quasars", "kind": "evergreen"}}
    ] * PAGE_SIZE

    def handler(request: httpx2.Request) -> httpx2.Response:
        offsets.append(request.url.params["offset"])
        assert request.headers["apikey"] == "sb_publishable_test"
        return httpx2.Response(200, json=full_page if len(offsets) == 1 else full_page[:3])

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    rest = RestClient(BASE, "sb_publishable_test", client=client, retry_backoff_seconds=0.0)

    found = BankReader(rest).topics()

    assert offsets == ["0", str(PAGE_SIZE)]
    assert [t.name for t in found] == ["Quasars"]


def test_reader_needs_the_publishable_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", BASE)
    monkeypatch.delenv("SUPABASE_PUBLISHABLE_KEY", raising=False)
    with pytest.raises(StoreError, match="SUPABASE_PUBLISHABLE_KEY"):
        BankReader.from_env()


class FakeReader:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def __enter__(self) -> FakeReader:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def topics(self) -> list[object]:
        if self.fail:
            raise StoreError("down")
        return [summarize([row("Quasars", "quiz", "easy")])[0]]


def test_topics_endpoint_answers_with_a_cacheable_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BankReader, "from_env", classmethod(lambda cls: FakeReader()))

    response = topics.handle(ApiRequest(method="GET", path="/api/topics"))

    assert response.status == 200
    assert response.body == {
        "topics": [{"name": "Quasars", "kind": "evergreen", "learn": [], "quiz": ["easy"]}]
    }
    assert response.headers["Cache-Control"] == "public, s-maxage=300"


def test_topics_endpoint_reports_an_unreachable_bank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BankReader, "from_env", classmethod(lambda cls: FakeReader(True)))

    assert topics.handle(ApiRequest(method="GET", path="/api/topics")).status == 503
    assert topics.handle(ApiRequest(method="POST", path="/api/topics")).status == 405


def test_dev_server_routes_and_404s() -> None:
    assert dispatch(ApiRequest(method="GET", path="/api/nope")).status == 404


def serve(handle: Handle, path: str, headers: dict[str, str] | None = None) -> tuple[str, bytes]:
    """Run one GET through the adapter class without a socket."""
    handler_class = make_handler(handle)
    handler = handler_class.__new__(handler_class)
    handler.command, handler.path, handler.request_version = "GET", path, "HTTP/1.1"
    message = Message()
    for name, value in (headers or {}).items():
        message[name] = value
    handler.headers = message
    handler.rfile, handler.wfile = io.BytesIO(b""), io.BytesIO()
    handler.client_address = ("10.0.0.1", 5000)
    handler.requestline = f"GET {path} HTTP/1.1"
    handler.do_GET()
    raw = handler.wfile.getvalue()
    head, _, body = raw.partition(b"\r\n\r\n")
    return head.decode(), body


def test_adapter_passes_query_and_forwarded_address_and_hides_crashes() -> None:
    seen: list[ApiRequest] = []

    def echo(request: ApiRequest) -> ApiResponse:
        seen.append(request)
        return json_response({"ok": True})

    head, body = serve(echo, "/api/x?mode=quiz", {"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})

    assert "200" in head.splitlines()[0] and "Cache-Control: no-store" in head
    assert json.loads(body) == {"ok": True}
    assert seen[0].query == {"mode": "quiz"} and seen[0].client_ip == "203.0.113.9"

    def crash(_request: ApiRequest) -> ApiResponse:
        raise RuntimeError("secret detail")

    head, body = serve(crash, "/api/x")
    assert "500" in head.splitlines()[0]
    assert b"secret detail" not in body


# --- Items, answers and reports ------------------------------------------------------------------

QUIZ_ROW = {
    "id": 7,
    "mode": "quiz",
    "difficulty": "easy",
    "question": "What powers a quasar?",
    "options": ["Fusion", "Decay", "A black hole", "Collisions"],
    "correct_index": 2,
    "explanation": "Gas falls into a supermassive black hole.",
    "topics": {"name": "Quasars", "kind": "evergreen"},
    "sources": [
        {"ordinal": 1, "url": "https://www.nasa.gov/b", "quote": "Second."},
        {"ordinal": 0, "url": "https://en.wikipedia.org/wiki/Quasar", "quote": "First."},
    ],
    "claim_checks": [
        {
            "kind": "correct_answer",
            "claim": 'The answer to "Q" is: A black hole',
            "verdict": "supports",
            "confidence": 0.99,
        },
        {
            "kind": "distractor",
            "claim": 'The answer to "Q" is: fusion',
            "verdict": "contradicts",
            "confidence": 0.9,
        },
        {
            "kind": "distractor",
            "claim": 'The answer to "Q" is: Something else',
            "verdict": "contradicts",
            "confidence": 0.8,
        },
        {"kind": "sentence", "claim": "Gas falls in.", "verdict": "supports", "confidence": 0.95},
        {"kind": "sentence", "claim": "Bright.", "verdict": "says_nothing", "confidence": 0.7},
    ],
}


def items_client(
    rows: list[dict[str, object]], seen: list[httpx2.Request] | None = None
) -> BankReader:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        return httpx2.Response(200, json=rows)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    return BankReader(
        RestClient(BASE, "sb_publishable_test", client=client, retry_backoff_seconds=0.0)
    )


def test_a_quiz_question_never_carries_its_answer() -> None:
    seen: list[httpx2.Request] = []
    question = items_client([QUIZ_ROW], seen).random_item("Quasars", "quiz", "easy")

    assert question is not None and question.mode == "quiz"
    body = question.model_dump()
    assert "correct_index" not in body and "explanation" not in body and "sources" not in body
    params = seen[0].url.params
    assert params["topics.name"] == "eq.Quasars" and params["claim_checks.layer"] == "eq.jev"


def test_reveal_orders_sources_and_matches_checks_to_options() -> None:
    answer = items_client([QUIZ_ROW]).reveal(7)

    assert answer is not None and answer.correct_index == 2
    assert [s.quote for s in answer.sources] == ["First.", "Second."]
    assert answer.sources[1].site == "nasa.gov"
    check = answer.source_check
    # Matched by option text, ignoring case; a claim matching no option is left out.
    assert [(c.option, c.verdict) for c in check.options] == [(0, "contradicts"), (2, "supports")]
    assert (check.sentences_supported, check.sentences) == (1, 2)


def test_random_item_avoids_recent_items_while_it_can() -> None:
    other = {**QUIZ_ROW, "id": 8}
    reader = items_client([QUIZ_ROW, other])

    picks = {reader.random_item("Quasars", "quiz", "easy", frozenset({7})).id for _ in range(5)}  # type: ignore[union-attr]
    only = items_client([QUIZ_ROW]).random_item("Quasars", "quiz", "easy", frozenset({7}))

    assert picks == {8}
    assert only is not None and only.id == 7
    assert items_client([]).random_item("Quasars", "quiz", "easy") is None


def fake_reader(monkeypatch: pytest.MonkeyPatch, reader: BankReader) -> None:
    class Wrapped:
        def __enter__(self) -> BankReader:
            return reader

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(BankReader, "from_env", classmethod(lambda cls: Wrapped()))


def test_item_and_reveal_endpoints_validate_their_input(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_reader(monkeypatch, items_client([QUIZ_ROW]))

    ok = item.handle(
        ApiRequest(
            "GET",
            "/api/item",
            {"topic": "Quasars", "mode": "quiz", "difficulty": "easy", "exclude": "1,x,2"},
        )
    )
    assert ok.status == 200 and ok.body["question"] == "What powers a quasar?"  # type: ignore[index]
    assert item.handle(ApiRequest("GET", "/api/item", {"mode": "quiz"})).status == 400
    assert (
        item.handle(
            ApiRequest("GET", "/api/item", {"topic": "Q", "mode": "chess", "difficulty": "easy"})
        ).status
        == 400
    )
    many = ",".join(str(n) for n in range(600))
    assert (
        item.handle(
            ApiRequest(
                "GET",
                "/api/item",
                {"topic": "Q", "mode": "quiz", "difficulty": "easy", "exclude": many},
            )
        ).status
        == 400
    )

    revealed = reveal.handle(ApiRequest("GET", "/api/reveal", {"id": "7"}))
    assert revealed.status == 200 and revealed.headers["Cache-Control"] == "public, s-maxage=300"
    assert reveal.handle(ApiRequest("GET", "/api/reveal", {"id": "-1"})).status == 400


def test_report_hashes_the_visitor_and_needs_a_published_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_reader(monkeypatch, items_client([{"id": 7}]))
    stored: list[tuple[int, str, str | None]] = []

    class FakeStore:
        def __enter__(self) -> FakeStore:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def add_report(self, item_id: int, user_hash: str, reason: str | None) -> bool:
            stored.append((item_id, user_hash, reason))
            return len(stored) == 1

    monkeypatch.setattr(SupabaseStore, "from_env", classmethod(lambda cls: FakeStore()))
    monkeypatch.setenv("IP_HASH_SALT", "pepper")
    body = json.dumps({"id": 7, "reason": "  wrong date  "}).encode()

    first = report.handle(ApiRequest("POST", "/api/report", body=body, client_ip="203.0.113.9"))
    second = report.handle(ApiRequest("POST", "/api/report", body=body, client_ip="203.0.113.9"))

    assert first.body == {"reported": True, "already": False}
    assert second.body == {"reported": True, "already": True}
    assert stored[0] == (7, salted_hash("203.0.113.9", "pepper"), "wrong date")
    assert "203.0.113.9" not in stored[0][1]
    assert (
        report.handle(ApiRequest("POST", "/api/report", body=b"{bad", client_ip="1.2.3.4")).status
        == 400
    )

    monkeypatch.delenv("IP_HASH_SALT")
    assert (
        report.handle(ApiRequest("POST", "/api/report", body=body, client_ip="1.2.3.4")).status
        == 503
    )


def test_salted_hash_depends_on_the_salt() -> None:
    assert salted_hash("1.2.3.4", "a") != salted_hash("1.2.3.4", "b")
    assert len(salted_hash("1.2.3.4", "a")) == 64
