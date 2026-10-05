"""The on-demand guardrails' numbers and types (DESIGN.md decision 9, set 2026-10-04).

The counting happens in the database (supabase/migrations/004_on_demand_runs.sql) so it holds
across serverless instances; the numbers are passed in from here, so they live in reviewed code.
"""

from __future__ import annotations

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


LIMIT_MESSAGES: dict[LimitName, str] = {
    "user_day": (
        f"You have researched {LIMITS.user_runs_per_day} custom topics today, the daily "
        "limit. It resets at midnight UTC."
    ),
    "day_runs": "Custom topics have reached today's limit for everyone. It resets at midnight UTC.",
    "day_usd": "Custom topics have reached today's budget. It resets at midnight UTC.",
    "month_usd": "Custom topics have used this month's budget and resume next month.",
}
