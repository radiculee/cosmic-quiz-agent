"""The visitor's live-search quota: the pure rule, the store's reads and writes, and GET /api/quota.
No network."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest

from agent.limits import (
    LAUNCH_ENDS,
    LAUNCH_LIMITS,
    LAUNCH_STARTS,
    LIMITS,
    NOVEMBER_ENDS,
    NOVEMBER_LIMITS,
    NOVEMBER_STARTS,
    LimitSettings,
    OnDemandUsage,
    day_start,
    limits_at,
    month_start,
    quota,
)
from agent.rest import StoreError
from agent.schemas import Difficulty, Mode
from agent.store import SupabaseStore
from agent.web import ApiRequest, salted_hash
from api import quota as quota_api
from dev.api_server import ROUTES

BASE = "https://example.supabase.co"
NOW = datetime(2026, 10, 8, 14, 30, tzinfo=UTC)
RESERVE = 0.17


def usage(
    visitor: int = 0, searches: int = 0, usd_today: float = 0.0, usd_month: float = 0.0
) -> OnDemandUsage:
    return OnDemandUsage(
        visitor_searches_today=visitor,
        searches_today=searches,
        usd_today=usd_today,
        usd_this_month=usd_month,
    )


def test_days_and_months_start_at_midnight_utc() -> None:
    evening_in_dublin = datetime.fromisoformat("2026-10-08T23:30:00-01:00")  # 00:30 UTC on the 9th

    assert day_start(NOW) == datetime(2026, 10, 8, tzinfo=UTC)
    assert day_start(evening_in_dublin) == datetime(2026, 10, 9, tzinfo=UTC)
    assert month_start(NOW) == datetime(2026, 10, 1, tzinfo=UTC)


def test_quota_counts_down_the_visitors_searches_and_resets_at_the_next_midnight_utc() -> None:
    fresh = quota(usage(), LIMITS, RESERVE, NOW)
    used = quota(usage(visitor=1), LIMITS, RESERVE, NOW)
    over = quota(usage(visitor=5), LIMITS, RESERVE, NOW)

    assert (fresh.remaining, fresh.limit, fresh.global_open) == (2, 2, True)
    assert used.remaining == 1
    assert over.remaining == 0
    assert fresh.resets_at == datetime(2026, 10, 9, tzinfo=UTC)


def test_global_caps_close_exactly_where_the_database_refuses_a_search() -> None:
    limits = LimitSettings(searches_per_day=4, usd_per_day=0.50, usd_per_month=4.00)

    assert not quota(usage(searches=4), limits, RESERVE, NOW).global_open
    assert quota(usage(searches=3), limits, RESERVE, NOW).global_open
    # The day's budget must hold one more reservation: 0.33 + 0.17 fits, 0.34 + 0.17 does not.
    assert quota(usage(usd_today=0.33, usd_month=0.33), limits, RESERVE, NOW).global_open
    assert not quota(usage(usd_today=0.34, usd_month=0.34), limits, RESERVE, NOW).global_open
    assert not quota(usage(usd_month=3.90), limits, RESERVE, NOW).global_open


def test_the_launch_week_runs_from_3_to_9_november_utc_and_ends_by_itself() -> None:
    assert datetime(2026, 11, 3, tzinfo=UTC) == LAUNCH_STARTS
    assert datetime(2026, 11, 10, tzinfo=UTC) == LAUNCH_ENDS
    assert limits_at(datetime(2026, 11, 2, 23, 59, 59, tzinfo=UTC)) == NOVEMBER_LIMITS
    assert limits_at(LAUNCH_STARTS) == LAUNCH_LIMITS
    assert limits_at(datetime(2026, 11, 9, 23, 59, 59, tzinfo=UTC)) == LAUNCH_LIMITS
    assert limits_at(LAUNCH_ENDS) == NOVEMBER_LIMITS


def test_november_has_its_own_month_cap_for_the_calendar_month_and_ends_by_itself() -> None:
    assert datetime(2026, 11, 1, tzinfo=UTC) == NOVEMBER_STARTS
    assert datetime(2026, 12, 1, tzinfo=UTC) == NOVEMBER_ENDS
    assert limits_at(datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC)) == LIMITS
    assert limits_at(NOVEMBER_STARTS) == NOVEMBER_LIMITS
    # After the launch week the usual daily numbers return, under November's month cap.
    assert limits_at(datetime(2026, 11, 20, 12, tzinfo=UTC)) == NOVEMBER_LIMITS
    assert limits_at(datetime(2026, 11, 30, 23, 59, 59, tzinfo=UTC)) == NOVEMBER_LIMITS
    # From 1 December the usual $4 again, with no deploy.
    assert limits_at(NOVEMBER_ENDS) == LIMITS
    assert limits_at(NOVEMBER_ENDS).usd_per_month == 4.00
    assert limits_at(NOW) == LIMITS


def test_november_changes_only_the_month_cap() -> None:
    assert NOVEMBER_LIMITS.usd_per_month > LIMITS.usd_per_month
    other = {"usd_per_month"}
    assert NOVEMBER_LIMITS.model_dump(exclude=other) == LIMITS.model_dump(exclude=other)


def test_the_launch_raises_only_the_daily_numbers_under_novembers_month_cap() -> None:
    raised = ("user_searches_per_day", "searches_per_day", "usd_per_day")
    for name in raised:
        assert getattr(LAUNCH_LIMITS, name) > getattr(NOVEMBER_LIMITS, name), name
    assert LAUNCH_LIMITS.model_dump(exclude=set(raised)) == NOVEMBER_LIMITS.model_dump(
        exclude=set(raised)
    )


def test_every_search_of_the_launch_week_at_a_typical_cost_fits_novembers_month_cap() -> None:
    # The decision's sum (2026-10-28): every search allowed on 1 and 2 November and on each
    # launch day, at about $0.17 a search (six items at a median $0.027 each, plus the
    # verifier), comes to $18.02. Not a ceiling: a day of unusually costly searches could reach
    # the $3.25 daily cap, and then the month cap could be met on the launch's last day.
    typical_search = 0.17
    launch_days = (LAUNCH_ENDS - LAUNCH_STARTS).days
    launch = launch_days * LAUNCH_LIMITS.searches_per_day * typical_search
    before = 2 * NOVEMBER_LIMITS.searches_per_day * typical_search

    assert before + launch <= NOVEMBER_LIMITS.usd_per_month


def test_in_the_launch_week_the_quota_offers_five_searches() -> None:
    launch_day = datetime(2026, 11, 3, 9, 30, tzinfo=UTC)

    offered = quota(usage(visitor=2, searches=4), limits_at(launch_day), RESERVE, launch_day)

    assert (offered.remaining, offered.limit, offered.global_open) == (3, 5, True)


def test_quota_serialises_its_reset_time_as_iso_utc() -> None:
    body = quota(usage(visitor=1), LIMITS, RESERVE, NOW).model_dump(mode="json")

    assert body == {
        "remaining": 1,
        "limit": 2,
        "resets_at": "2026-10-09T00:00:00Z",
        "global_open": True,
    }


def test_store_reads_the_visitors_searches_and_sums_the_month_without_other_hashes() -> None:
    seen: list[dict[str, str]] = []
    month_rows = [
        # Yesterday, ended: counts its real cost for the month only.
        {
            "id": 1,
            "started_at": "2026-10-07T20:00:00+00:00",
            "reserved_usd": 0.17,
            "spent_usd": 0.03,
            "outcome": "published",
            "search_id": None,
        },
        # Today: a search's first run, ended.
        {
            "id": 2,
            "started_at": "2026-10-08T09:00:00+00:00",
            "reserved_usd": 0.17,
            "spent_usd": 0.02,
            "outcome": "published",
            "search_id": None,
        },
        # Today: a later run of that search, still running. It counts its reservation, but not
        # as another search.
        {
            "id": 3,
            "started_at": "2026-10-08T09:01:00+00:00",
            "reserved_usd": 0.17,
            "spent_usd": None,
            "outcome": None,
            "search_id": 2,
        },
    ]

    def handler(request: httpx2.Request) -> httpx2.Response:
        params = dict(request.url.params)
        seen.append(params)
        assert request.headers["apikey"] == "sb_secret_test"
        if "user_hash" in params:
            return httpx2.Response(200, json=[{"id": 2}])
        return httpx2.Response(200, json=month_rows)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    store = SupabaseStore(BASE, "sb_secret_test", client=client, retry_backoff_seconds=0.0)

    found = store.on_demand_usage("abc123", NOW)

    assert found.visitor_searches_today == 1
    assert found.searches_today == 1
    assert found.usd_today == pytest.approx(0.19)
    assert found.usd_this_month == pytest.approx(0.22)
    mine, month = seen
    assert mine == {
        "select": "id",
        "user_hash": "eq.abc123",
        "started_at": "gte.2026-10-08T00:00:00+00:00",
        "search_id": "is.null",  # the runs that opened a search
    }
    assert month["select"] == "id,started_at,reserved_usd,spent_usd,outcome,search_id"
    assert month["started_at"] == "gte.2026-10-01T00:00:00+00:00"
    assert "user_hash" not in month


def usage_row(
    run_id: int,
    spent_usd: float | None = None,
    outcome: str | None = None,
    search_id: int | None = None,
) -> dict[str, object]:
    return {
        "id": run_id,
        "started_at": "2026-10-08T09:00:00+00:00",
        "reserved_usd": 0.17,
        "spent_usd": spent_usd,
        "outcome": outcome,
        "search_id": search_id,
    }


def usage_of(rows: list[dict[str, object]], mine: list[int]) -> OnDemandUsage:
    """What `on_demand_usage` counts from these runs, with `mine` the visitor's searches."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        if "user_hash" in dict(request.url.params):
            return httpx2.Response(200, json=[{"id": run_id} for run_id in mine])
        return httpx2.Response(200, json=rows)

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    store = SupabaseStore(BASE, "sb_secret_test", client=client, retry_backoff_seconds=0.0)
    return store.on_demand_usage("abc123", NOW)


def test_a_search_that_failed_whole_with_no_spend_does_not_count() -> None:
    rows = [
        usage_row(74, 0.0, "failed"),
        usage_row(75, 0.0, "failed", search_id=74),
        usage_row(76, 0.0, "failed", search_id=74),
    ]

    found = usage_of(rows, mine=[74])

    assert found.visitor_searches_today == 0 and found.searches_today == 0
    assert found.usd_today == 0 and found.usd_this_month == 0


@pytest.mark.parametrize(
    ("first", "second"),
    [
        # Still running: the opening run has ended, another has not, so it counts its reservation.
        (usage_row(74, 0.0, "failed"), usage_row(75, search_id=74)),
        # The opening run is the one still going.
        (usage_row(74), usage_row(75, 0.0, "failed", search_id=74)),
        # One run was billed, so the model was reached.
        (usage_row(74, 0.0, "failed"), usage_row(75, 0.02, "failed", search_id=74)),
        # One run made an item.
        (usage_row(74, 0.0, "failed"), usage_row(75, 0.02, "published", search_id=74)),
        # A run ended with another outcome and no recorded spend: not a failed run.
        (usage_row(74, 0.0, "failed"), usage_row(75, 0.0, "discarded", search_id=74)),
    ],
)
def test_a_search_counts_unless_every_run_ended_failed_with_no_spend(
    first: dict[str, object], second: dict[str, object]
) -> None:
    found = usage_of([first, second], mine=[74])

    assert found.visitor_searches_today == 1 and found.searches_today == 1


def test_only_the_free_search_is_left_out_and_the_money_still_counts_every_run() -> None:
    rows = [
        usage_row(74, 0.0, "failed"),  # free
        usage_row(75, 0.0, "failed", search_id=74),
        usage_row(80, 0.03, "published"),  # counts
        usage_row(81),  # another visitor's, still running: counts at its reservation
    ]

    found = usage_of(rows, mine=[74, 80])

    assert found.visitor_searches_today == 1
    assert found.searches_today == 2
    assert found.usd_today == pytest.approx(0.03 + 0.17)


def test_the_migration_and_the_schema_have_the_same_counting_functions() -> None:
    root = Path(__file__).parent.parent / "supabase"
    schema = (root / "schema.sql").read_text(encoding="utf-8")
    migration = (root / "migrations" / "013_free_failed_searches.sql").read_text(encoding="utf-8")

    def function(sql: str, name: str) -> str:
        start = sql.index(f"create or replace function public.{name}(")
        return sql[start : sql.index("$$;", start)]

    for name in ("on_demand_search_counts", "begin_on_demand_search"):
        assert function(migration, name) == function(schema, name)
    begin = function(schema, "begin_on_demand_search")
    assert begin.count("public.on_demand_search_counts(id)") == 2


def test_a_search_reserves_its_items_in_plan_order_with_the_limits_in_force() -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path.endswith("/rpc/begin_on_demand_search")
        sent.append(json.loads(request.content))
        return httpx2.Response(200, json={"ok": True, "ids": [13, 14, 15], "limit": "day_usd"})

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    store = SupabaseStore(BASE, "sb_secret_test", client=client, retry_backoff_seconds=0.0)
    items: list[tuple[Mode, Difficulty]] = [
        ("quiz", "easy"),
        ("quiz", "hard"),
        ("learn", "easy"),
        ("learn", "hard"),
    ]

    slots = store.begin_on_demand_search("abc123", "Pulsars", items, RESERVE, LIMITS)

    # A partial fit: the first three items, and the cap that refused the fourth.
    assert slots.ok and slots.ids == (13, 14, 15) and slots.limit == "day_usd"
    assert sent == [
        {
            "p_user_hash": "abc123",
            "p_topic": "Pulsars",
            "p_items": [
                {"mode": "quiz", "difficulty": "easy"},
                {"mode": "quiz", "difficulty": "hard"},
                {"mode": "learn", "difficulty": "easy"},
                {"mode": "learn", "difficulty": "hard"},
            ],
            "p_reserve_usd": 0.17,
            "p_user_day_searches": LIMITS.user_searches_per_day,
            "p_day_searches": LIMITS.searches_per_day,
            "p_search_runs": LIMITS.runs_per_search,
            "p_day_usd": LIMITS.usd_per_day,
            "p_month_usd": LIMITS.usd_per_month,
        }
    ]


def test_a_refused_search_names_the_limit_and_reserves_nothing() -> None:
    client = httpx2.Client(
        transport=httpx2.MockTransport(
            lambda _: httpx2.Response(200, json={"ok": False, "limit": "day_searches"})
        )
    )
    store = SupabaseStore(BASE, "sb_secret_test", client=client, retry_backoff_seconds=0.0)

    slots = store.begin_on_demand_search("abc123", "Pulsars", [("learn", "hard")], RESERVE, LIMITS)

    assert not slots.ok and slots.ids == () and slots.limit == "day_searches"


def test_a_reservation_is_sent_once_even_when_the_database_fails() -> None:
    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.path)
        return httpx2.Response(503, json={"message": "down"})

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    store = SupabaseStore(BASE, "sb_secret_test", client=client, retry_backoff_seconds=0.0)

    with pytest.raises(StoreError):
        store.begin_on_demand_search("abc123", "Pulsars", [("quiz", "easy")], RESERVE, LIMITS)
    assert len(calls) == 1  # a retry could reserve a second search


def test_the_store_reads_each_levels_usual_run_time() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path.endswith("/rpc/live_run_estimates")
        return httpx2.Response(
            200,
            json=[
                {"mode": "learn", "difficulty": "hard", "median_seconds": 24.5, "runs": 12},
                {"mode": "quiz", "difficulty": "easy", "median_seconds": 15.1, "runs": 3},
            ],
        )

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    store = SupabaseStore(BASE, "sb_secret_test", client=client, retry_backoff_seconds=0.0)

    found = store.live_run_estimates()

    assert [(row.mode, row.difficulty, row.median_seconds, row.runs) for row in found] == [
        ("learn", "hard", 24.5, 12),
        ("quiz", "easy", 15.1, 3),
    ]


class FakeStore:
    def __init__(self, found: OnDemandUsage | None) -> None:
        self.found = found
        self.asked: list[str] = []

    def __enter__(self) -> FakeStore:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def on_demand_usage(self, user_hash: str, now: datetime) -> OnDemandUsage:
        self.asked.append(user_hash)
        if self.found is None:
            raise StoreError("down")
        return self.found


def use_store(monkeypatch: pytest.MonkeyPatch, store: FakeStore) -> None:
    monkeypatch.setattr(SupabaseStore, "from_env", classmethod(lambda cls: store))


def test_endpoint_answers_with_the_visitors_quota_and_is_never_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(usage(visitor=1))
    use_store(monkeypatch, store)
    visitor = salted_hash("203.0.113.9", "pepper")

    response = quota_api.handle(ApiRequest("GET", "/api/quota", visitor=visitor))

    assert response.status == 200
    assert isinstance(response.body, dict)
    assert response.body["remaining"] == 1 and response.body["global_open"] is True
    assert response.headers["Cache-Control"] == "no-store"
    assert store.asked == [visitor]
    assert visitor not in json.dumps(response.body)


def test_endpoint_refuses_other_methods_unknown_visitors_and_a_down_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_store(monkeypatch, FakeStore(None))

    assert quota_api.handle(ApiRequest("POST", "/api/quota", visitor="v")).status == 405
    assert quota_api.handle(ApiRequest("GET", "/api/quota", visitor="")).status == 503
    assert quota_api.handle(ApiRequest("GET", "/api/quota", visitor="v")).status == 503


def test_dev_server_serves_the_quota_route() -> None:
    assert ROUTES["/api/quota"] is quota_api.app
