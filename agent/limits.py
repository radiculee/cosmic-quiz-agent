"""The on-demand guardrails' numbers and types (DESIGN.md decision 9, set 2026-10-04).

The counting happens in the database (supabase/migrations/004_on_demand_runs.sql) so it holds
across serverless instances; the numbers are passed in from here, so they live in reviewed code.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LimitName = Literal["user_day", "day_runs", "day_usd", "month_usd"]


class LimitSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Per visitor (a salted hash of the IP address), across every API endpoint. Raised from 60 on
    # 2026-10-04: a 10-question run is about 21 requests (a question and its answer each).
    requests_per_hour: int = Field(default=300, gt=0)
    # Per visitor: live runs of custom topics a day (UTC). Bank questions do not count. Lowered
    # from 10 on 2026-10-05, so one visitor cannot use up the day's global cap of 10 runs.
    user_runs_per_day: int = Field(default=3, gt=0)
    # All visitors together. A run reserves the most it can cost until it ends, so the dollar
    # caps hold even while runs are in flight. The monthly ceiling leaves room for the daily
    # Curator (about $5 a month) under the $10 Anthropic limit.
    runs_per_day: int = Field(default=10, gt=0)
    usd_per_day: float = Field(default=0.50, gt=0)
    usd_per_month: float = Field(default=4.00, gt=0)


LIMITS = LimitSettings()


class RequestCount(BaseModel):
    """One request counted for a visitor in the current clock hour."""

    model_config = ConfigDict(frozen=True)

    allowed: bool
    count: int
    retry_after: int


class RunSlot(BaseModel):
    """Permission to start a live run, or the limit that refused it."""

    model_config = ConfigDict(frozen=True)

    ok: bool
    id: int | None = None
    limit: LimitName | None = None


class OnDemandUsage(BaseModel):
    """Live runs so far, counted as `begin_on_demand_run` counts them: by start time in UTC, and
    a run that has not ended at its reservation."""

    model_config = ConfigDict(frozen=True)

    visitor_runs_today: int = Field(ge=0)
    runs_today: int = Field(ge=0)
    usd_today: float = Field(ge=0)
    usd_this_month: float = Field(ge=0)


class Quota(BaseModel):
    """What the web page shows before a live run is spent (GET /api/quota)."""

    model_config = ConfigDict(frozen=True)

    remaining: int = Field(ge=0)
    limit: int = Field(gt=0)
    # When the visitor's daily count starts again: the next midnight UTC.
    resets_at: datetime
    # Whether the global caps would let a run start now. Off when today's runs or budget, or the
    # month's budget, are used up.
    global_open: bool


def day_start(now: datetime) -> datetime:
    """Midnight UTC at the start of `now`'s day, as the database's limits count days."""
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def month_start(now: datetime) -> datetime:
    return day_start(now).replace(day=1)


def quota(usage: OnDemandUsage, limits: LimitSettings, reserve_usd: float, now: datetime) -> Quota:
    """The visitor's quota. The global check repeats `begin_on_demand_run`'s (migration 004), so
    the page says "paused" exactly when a run would be refused; the database still decides."""

    def fits(spent: float, cap: float) -> bool:
        # Rounded as the reservation is sent to the database, so float noise cannot tip it.
        return round(spent + reserve_usd, 6) <= cap

    return Quota(
        remaining=max(0, limits.user_runs_per_day - usage.visitor_runs_today),
        limit=limits.user_runs_per_day,
        resets_at=day_start(now) + timedelta(days=1),
        global_open=(
            usage.runs_today < limits.runs_per_day
            and fits(usage.usd_today, limits.usd_per_day)
            and fits(usage.usd_this_month, limits.usd_per_month)
        ),
    )


LIMIT_MESSAGES: dict[LimitName, str] = {
    "user_day": (
        f"You have researched {LIMITS.user_runs_per_day} custom topics today, the daily "
        "limit. It resets at midnight UTC."
    ),
    "day_runs": "Custom topics have reached today's limit for everyone. It resets at midnight UTC.",
    "day_usd": "Custom topics have reached today's budget. It resets at midnight UTC.",
    "month_usd": "Custom topics have used this month's budget and resume next month.",
}
