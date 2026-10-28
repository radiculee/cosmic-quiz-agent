"""The public bank reads, the HTTP adapter and the topics endpoint. No network."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from wsgiref.types import WSGIApplication
from wsgiref.util import setup_testing_defaults

import httpx2
import pytest

from agent.bank import BankReader, BankTopic, _ItemIndexRow, summarize
from agent.limits import LIMITS, REPORTS_MESSAGE, RequestCount
from agent.rest import PAGE_SIZE, RestClient, StoreError
from agent.store import SupabaseStore
from agent.web import (
    ApiRequest,
    ApiResponse,
    StreamResponse,
    json_response,
    make_app,
    salted_hash,
    sign,
    verify_signature,
    visitor_address,
)
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


def test_topic_names_reads_every_visible_topic_whatever_its_levels() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200, json=[{"name": "Wormholes", "kind": "custom"}, {"name": "Auroras", "kind": "news"}]
        )

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    rest = RestClient(BASE, "sb_publishable_test", client=client, retry_backoff_seconds=0.0)

    names = BankReader(rest).topic_names()

    assert names == [("Wormholes", "custom"), ("Auroras", "news")]
    assert seen[0].url.path == "/rest/v1/topics"
    assert seen[0].url.params["select"] == "name,kind"


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

    def topics(self) -> list[BankTopic]:
        if self.fail:
            raise StoreError("down")
        return summarize([*EVERY_LEVEL, row("Quasars", "quiz", "easy")])


LEVELS = ("easy", "medium", "hard")
EVERY_LEVEL = [row("Auroras", mode, level) for mode in ("learn", "quiz") for level in LEVELS]


def test_a_topic_is_complete_only_with_both_modes_at_every_level() -> None:
    assert summarize(EVERY_LEVEL)[0].complete
    for missing in range(len(EVERY_LEVEL)):
        rows = EVERY_LEVEL[:missing] + EVERY_LEVEL[missing + 1 :]
        assert not summarize(rows)[0].complete


def test_topics_endpoint_lists_complete_topics_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BankReader, "from_env", classmethod(lambda cls: FakeReader()))

    response = topics.handle(ApiRequest(method="GET", path="/api/topics"))

    assert response.status == 200
    assert response.body == {
        "topics": [
            {"name": "Auroras", "kind": "evergreen", "learn": list(LEVELS), "quiz": list(LEVELS)}
        ]
    }
    assert response.headers["Cache-Control"] == "public, s-maxage=300"


def test_topics_endpoint_reports_an_unreachable_bank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BankReader, "from_env", classmethod(lambda cls: FakeReader(True)))

    assert topics.handle(ApiRequest(method="GET", path="/api/topics")).status == 503
    assert topics.handle(ApiRequest(method="POST", path="/api/topics")).status == 405


def call(
    app: WSGIApplication,
    path: str,
    *,
    method: str = "GET",
    query: str = "",
    body: bytes = b"",
    headers: dict[str, str] | None = None,
    remote: str = "10.0.0.1",
) -> tuple[str, dict[str, str], bytes]:
    """Run one request through a WSGI app without a socket: (status, headers, body)."""
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ.update(
        {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "REMOTE_ADDR": remote,
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": io.BytesIO(body),
        }
    )
    for name, value in (headers or {}).items():
        key = name.upper().replace("-", "_")
        # WSGI passes Content-Type without the HTTP_ prefix.
        environ[key if key == "CONTENT_TYPE" else "HTTP_" + key] = value
    started: dict[str, object] = {}

    def start_response(status: str, response_headers: list[tuple[str, str]], *_: object) -> None:
        started["status"], started["headers"] = status, dict(response_headers)

    chunks = list(app(environ, start_response))  # type: ignore[arg-type]
    return str(started["status"]), started["headers"], b"".join(chunks)  # type: ignore[return-value]


def test_dev_server_routes_and_404s() -> None:
    status, _, body = call(dispatch, "/api/nope")
    assert status.startswith("404") and json.loads(body) == {"error": "No API route /api/nope."}


def test_adapter_passes_query_and_last_forwarded_address_and_hides_crashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IP_HASH_SALT", "pepper")
    seen: list[ApiRequest] = []

    def echo(request: ApiRequest) -> ApiResponse:
        seen.append(request)
        return json_response({"ok": True})

    app = make_app(echo, counter=None)
    # A client can put anything in X-Forwarded-For; the proxy appends the real address last.
    status, headers, body = call(
        app, "/api/x", query="mode=quiz", headers={"X-Forwarded-For": "1.1.1.1, 203.0.113.9"}
    )

    assert status.startswith("200") and headers["Cache-Control"] == "no-store"
    assert json.loads(body) == {"ok": True}
    assert seen[0].query == {"mode": "quiz"} and seen[0].client_ip == "203.0.113.9"
    assert seen[0].visitor == salted_hash("203.0.113.9", "pepper")
    assert call(app, "/api/x")[0].startswith("200") and seen[1].client_ip == "10.0.0.1"

    def crash(_request: ApiRequest) -> ApiResponse:
        raise RuntimeError("secret detail")

    status, _, body = call(make_app(crash, counter=None), "/api/x")
    assert status.startswith("500")
    assert b"secret detail" not in body


def test_adapter_refuses_a_visitor_over_the_hourly_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IP_HASH_SALT", "pepper")
    counted: list[str] = []

    def counter(visitor: str) -> RequestCount | None:
        counted.append(visitor)
        return RequestCount(allowed=len(counted) <= 2, count=len(counted), retry_after=1500)

    app = make_app(lambda _request: json_response({"ok": True}), counter=counter)
    statuses = [call(app, "/api/x")[0][:3] for _ in range(3)]
    status, headers, body = call(app, "/api/x")

    assert statuses == ["200", "200", "429"]
    assert status.startswith("429") and headers["Retry-After"] == "1500"
    assert json.loads(body)["error"] == "Too many requests this hour. Try again in 25 minutes."

    # A store that cannot count (None) never blocks, and nothing is counted without a salt.
    assert (
        call(make_app(lambda _r: json_response({}), counter=lambda _v: None), "/x")[0][:3] == "200"
    )
    monkeypatch.delenv("IP_HASH_SALT")
    before = len(counted)
    call(app, "/api/x")
    assert len(counted) == before


def test_adapter_refuses_requests_another_site_could_make_a_browser_send() -> None:
    handled: list[ApiRequest] = []

    def handle(request: ApiRequest) -> ApiResponse:
        handled.append(request)
        return json_response({"ok": True})

    counted: list[str] = []

    def counter(visitor: str) -> RequestCount:
        counted.append(visitor)
        return RequestCount(allowed=True, count=len(counted), retry_after=60)

    app = make_app(handle, counter=counter)
    body = b'{"id": 7}'

    def post(headers: dict[str, str]) -> str:
        return call(app, "/api/report", method="POST", body=body, headers=headers)[0][:3]

    # A page on another site can send plain text or a form without a preflight: refused.
    assert post({"Content-Type": "text/plain"}) == "415"
    assert post({"Content-Type": "application/x-www-form-urlencoded"}) == "415"
    assert post({}) == "415"
    # The browser marks a request from another site's page, whatever its method or body.
    assert post({"Content-Type": "application/json", "Sec-Fetch-Site": "cross-site"}) == "403"
    assert call(app, "/api/item", headers={"Sec-Fetch-Site": "cross-site"})[0][:3] == "403"
    assert handled == [] and counted == []

    # The site's own pages, and clients that send no Sec-Fetch-Site, are served.
    assert post({"Content-Type": "application/json", "Sec-Fetch-Site": "same-origin"}) == "200"
    assert post({"Content-Type": "Application/JSON; charset=utf-8"}) == "200"
    assert call(app, "/api/item", headers={"Sec-Fetch-Site": "same-origin"})[0][:3] == "200"
    assert call(app, "/api/item", headers={"Sec-Fetch-Site": "none"})[0][:3] == "200"
    assert len(handled) == 4
    assert handled[0].content_type == "application/json"
    assert handled[0].fetch_site == "same-origin"


def test_ipv6_visitors_are_counted_by_their_64_network(monkeypatch: pytest.MonkeyPatch) -> None:
    assert visitor_address("203.0.113.9") == "203.0.113.9"
    assert visitor_address("2001:db8:1:2:aaaa::1") == "2001:db8:1:2::/64"
    assert visitor_address("2001:db8:1:2:ffff:ffff:ffff:ffff") == "2001:db8:1:2::/64"
    assert visitor_address("2001:db8:1:3::1") == "2001:db8:1:3::/64"
    assert visitor_address("::ffff:203.0.113.9") == "203.0.113.9"
    assert visitor_address("not an address") == "not an address"

    monkeypatch.setenv("IP_HASH_SALT", "pepper")
    seen: list[ApiRequest] = []

    def remember(request: ApiRequest) -> ApiResponse:
        seen.append(request)
        return json_response({})

    app = make_app(remember, counter=None)
    for address in ("2001:db8:1:2::1", "2001:db8:1:2::abcd", "2001:db8:9::1"):
        call(app, "/api/x", headers={"X-Forwarded-For": address})

    assert seen[0].visitor == seen[1].visitor != seen[2].visitor
    assert seen[0].client_ip == "2001:db8:1:2::1"  # the request keeps the address it came from


def test_adapter_streams_events_as_lines_and_ends_a_broken_stream_cleanly() -> None:
    def events() -> Iterator[object]:
        yield {"type": "log", "label": "one"}
        yield {"type": "log", "label": "two"}
        raise RuntimeError("secret detail")

    app = make_app(lambda _request: StreamResponse(events()), counter=None)
    status, headers, body = call(
        app, "/api/research", method="POST", headers={"Content-Type": "application/json"}
    )

    lines = [json.loads(line) for line in body.decode().splitlines()]
    assert status.startswith("200")
    assert headers["Content-Type"].startswith("application/x-ndjson")
    assert [line.get("label") for line in lines[:2]] == ["one", "two"]
    assert lines[2]["type"] == "error" and "secret" not in body.decode()


def test_closing_a_stream_early_closes_the_events_it_was_sending() -> None:
    finished: list[str] = []

    def events() -> Iterator[object]:
        try:
            yield {"type": "log", "label": "one"}
            yield {"type": "log", "label": "two"}
        finally:
            finished.append("closed")

    app = make_app(lambda _request: StreamResponse(events()), counter=None)
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    body = app(environ, lambda *_: None)  # type: ignore[arg-type]
    chunks = iter(body)
    first = next(chunks)
    body.close()  # type: ignore[attr-defined]  # the client left: the server closes the body

    assert json.loads(first)["label"] == "one"
    assert finished == ["closed"]


def test_signed_tokens_need_the_salt_and_the_same_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IP_HASH_SALT", "pepper")
    token = sign("reveal", "7")
    assert verify_signature("reveal", "7", token)
    assert not verify_signature("reveal", "8", token)
    assert not verify_signature("report", "7", token)
    monkeypatch.setenv("IP_HASH_SALT", "other")
    assert not verify_signature("reveal", "7", token)
    monkeypatch.delenv("IP_HASH_SALT")
    assert not verify_signature("reveal", "7", token)


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

        def reports_today(self, user_hash: str, now: object) -> int:
            return 0

        def add_report(self, item_id: int, user_hash: str, reason: str | None) -> bool:
            stored.append((item_id, user_hash, reason))
            return len(stored) == 1

    monkeypatch.setattr(SupabaseStore, "from_env", classmethod(lambda cls: FakeStore()))
    body = json.dumps({"id": 7, "reason": "  wrong date  "}).encode()

    visitor = salted_hash("203.0.113.9", "pepper")
    first = report.handle(ApiRequest("POST", "/api/report", body=body, visitor=visitor))
    second = report.handle(ApiRequest("POST", "/api/report", body=body, visitor=visitor))

    assert first.body == {"reported": True, "already": False}
    assert second.body == {"reported": True, "already": True}
    assert stored[0] == (7, visitor, "wrong date")
    assert report.handle(ApiRequest("POST", "/api/report", body=b"{bad", visitor="v")).status == 400
    # Without a salt the adapter cannot tell visitors apart, so reports are refused.
    assert report.handle(ApiRequest("POST", "/api/report", body=body, visitor="")).status == 503


def test_salted_hash_depends_on_the_salt() -> None:
    assert salted_hash("1.2.3.4", "a") != salted_hash("1.2.3.4", "b")
    assert len(salted_hash("1.2.3.4", "a")) == 64


def test_a_visitor_can_send_ten_reports_a_day(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_reader(monkeypatch, items_client([{"id": 7}]))
    sent: dict[str, int] = {}

    class CountingStore:
        def __enter__(self) -> CountingStore:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def reports_today(self, user_hash: str, now: object) -> int:
            return sent.get(user_hash, 0)

        def add_report(self, item_id: int, user_hash: str, reason: str | None) -> bool:
            sent[user_hash] = sent.get(user_hash, 0) + 1
            return True

    monkeypatch.setattr(SupabaseStore, "from_env", classmethod(lambda cls: CountingStore()))
    body = json.dumps({"id": 7}).encode()

    def send(visitor: str) -> ApiResponse:
        return report.handle(ApiRequest("POST", "/api/report", body=body, visitor=visitor))

    statuses = [send("a").status for _ in range(LIMITS.reports_per_day + 1)]
    refused = send("a")

    assert statuses == [200] * LIMITS.reports_per_day + [429]
    assert refused.status == 429 and sent["a"] == LIMITS.reports_per_day
    assert refused.body == {"error": REPORTS_MESSAGE}
    assert 0 < int(refused.headers["Retry-After"]) <= 86_400
    assert send("b").status == 200  # another visitor is not affected
