"""The visitor's live-run quota: the pure rule, the store's reads and GET /api/quota. No network."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx2
import pytest

from agent.limits import LIMITS, LimitSettings, OnDemandUsage, day_start, month_start, quota
from agent.rest import StoreError
from agent.store import SupabaseStore
from agent.web import ApiRequest, salted_hash
from api import quota as quota_api
from dev.api_server import ROUTES

BASE = "https://example.supabase.co"
NOW = datetime(2026, 10, 8, 14, 30, tzinfo=UTC)
RESERVE = 0.17


def usage(
    visitor: int = 0, runs: int = 0, usd_today: float = 0.0, usd_month: float = 0.0
) -> OnDemandUsage:
    return OnDemandUsage(
        visitor_runs_today=visitor, runs_today=runs, usd_today=usd_today, usd_this_month=usd_month
    )


def test_days_and_months_start_at_midnight_utc() -> None:
    evening_in_dublin = datetime.fromisoformat("2026-10-08T23:30:00-01:00")  # 00:30 UTC on the 9th

    assert day_start(NOW) == datetime(2026, 10, 8, tzinfo=UTC)
    assert day_start(evening_in_dublin) == datetime(2026, 10, 9, tzinfo=UTC)
    assert month_start(NOW) == datetime(2026, 10, 1, tzinfo=UTC)


def test_quota_counts_down_the_visitors_runs_and_resets_at_the_next_midnight_utc() -> None:
    fresh = quota(usage(), LIMITS, RESERVE, NOW)
    used = quota(usage(visitor=1), LIMITS, RESERVE, NOW)
    over = quota(usage(visitor=5), LIMITS, RESERVE, NOW)

    assert (fresh.remaining, fresh.limit, fresh.global_open) == (3, 3, True)
    assert used.remaining == 2
    assert over.remaining == 0
    assert fresh.resets_at == datetime(2026, 10, 9, tzinfo=UTC)


def test_global_caps_close_exactly_where_the_database_refuses_a_run() -> None:
    limits = LimitSettings(runs_per_day=10, usd_per_day=0.50, usd_per_month=4.00)

    assert not quota(usage(runs=10), limits, RESERVE, NOW).global_open
    assert quota(usage(runs=9), limits, RESERVE, NOW).global_open
    # The day's budget must hold one more reservation: 0.33 + 0.17 fits, 0.34 + 0.17 does not.
    assert quota(usage(usd_today=0.33, usd_month=0.33), limits, RESERVE, NOW).global_open
    assert not quota(usage(usd_today=0.34, usd_month=0.34), limits, RESERVE, NOW).global_open
    assert not quota(usage(usd_month=3.90), limits, RESERVE, NOW).global_open


def test_quota_serialises_its_reset_time_as_iso_utc() -> None:
    body = quota(usage(visitor=1), LIMITS, RESERVE, NOW).model_dump(mode="json")

    assert body == {
        "remaining": 2,
        "limit": 3,
        "resets_at": "2026-10-09T00:00:00Z",
        "global_open": True,
    }


def test_store_reads_the_visitors_runs_and_sums_the_month_without_other_hashes() -> None:
    seen: list[dict[str, str]] = []
    month_rows = [
        # Yesterday, ended: counts its real cost for the month only.
        {"started_at": "2026-10-07T20:00:00+00:00", "reserved_usd": 0.17, "spent_usd": 0.03},
        # Today, ended.
        {"started_at": "2026-10-08T09:00:00+00:00", "reserved_usd": 0.17, "spent_usd": 0.02},
        # Today, still running: counts its reservation.
        {"started_at": "2026-10-08T14:00:00+00:00", "reserved_usd": 0.17, "spent_usd": None},
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

    assert found.visitor_runs_today == 1
    assert found.runs_today == 2
    assert found.usd_today == pytest.approx(0.19)
    assert found.usd_this_month == pytest.approx(0.22)
    mine, month = seen
    assert mine == {
        "select": "id",
        "user_hash": "eq.abc123",
        "started_at": "gte.2026-10-08T00:00:00+00:00",
    }
    assert month["select"] == "started_at,reserved_usd,spent_usd"
    assert month["started_at"] == "gte.2026-10-01T00:00:00+00:00"
    assert "user_hash" not in month


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
    assert response.body["remaining"] == 2 and response.body["global_open"] is True
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
