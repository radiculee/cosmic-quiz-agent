"""The on-demand guardrails' numbers and types (DESIGN.md decision 9, set 2026-10-04).

The counting happens in the database (migrations 004 and 006) so it holds across serverless
instances; the numbers are passed in from here, so they live in reviewed code.

Since 2026-10-08 a live search on the web page makes a whole topic, one agent run at a time: up
to six items since 2026-10-28 (a question and an explanation at each level). The daily limits
count searches; the dollar caps count every run, each reserving the most it can cost until it
ends.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# "search" is not a limit a player meets: it is the database refusing a later run that cannot
# join its search (another visitor's, still running, or already full).
LimitName = Literal["user_day", "day_searches", "day_usd", "month_usd", "search"]


class LimitSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Per visitor (a salted hash of the IP address), across every API endpoint. Raised from 60 on
    # 2026-10-04: a 10-question run is about 21 requests (a question and its answer each).
    requests_per_hour: int = Field(default=300, gt=0)
    # Per visitor: live searches a day (UTC). Bank items do not count, nor does a search that
    # finds everything already in the bank. Changed 2026-10-08 from 3 live runs of one item each.
    user_searches_per_day: int = Field(default=2, gt=0)
    # All visitors together. Changed 2026-10-08 from 10 live runs: a search costs about $0.12.
    searches_per_day: int = Field(default=4, gt=0)
    # The items a search can make: a question and an explanation at each of the three levels
    # (changed 2026-10-28 from 4, the explanation at one level). About $0.17 for all six; the
    # dollar caps are unchanged, so a day's budget covers fewer whole searches, and the daily
    # Curator makes what a cap or the clock leaves out.
    runs_per_search: int = Field(default=6, gt=0)
    # Every run reserves the most it can cost until it ends, so the dollar caps hold even while
    # runs are in flight. The monthly ceiling leaves room for the daily Curator (about $5 a
    # month) under the $10 Anthropic limit. A run starts only if today's spend plus its
    # reservation fits, so the day's last search may end early (decided 2026-10-08).
    usd_per_day: float = Field(default=0.50, gt=0)
    usd_per_month: float = Field(default=4.00, gt=0)
    # Per visitor: reports a day (UTC). Two reports from different visitors hide an item, so
    # without a limit two connections could hide the whole bank (docs/SECURITY_AUDIT.md S2,
    # set by Vedant on 2026-10-09).
    reports_per_day: int = Field(default=10, gt=0)


LIMITS = LimitSettings()

# The LinkedIn launch (decided 2026-10-21 by Vedant): for the week from the post on Tuesday
# 3 November 2026, more live searches, so more of the people who see it can try one. The
# monthly ceiling is unchanged, so the launch can never spend more than a usual month and the
# daily Curator keeps its share of the $10 Anthropic limit. The window ends by itself: outside
# it the usual limits apply with no deploy.
LAUNCH_STARTS = datetime(2026, 11, 3, tzinfo=UTC)
LAUNCH_ENDS = datetime(2026, 11, 10, tzinfo=UTC)
LAUNCH_LIMITS = LimitSettings(user_searches_per_day=5, searches_per_day=20, usd_per_day=2.50)


def limits_at(now: datetime) -> LimitSettings:
    """The limits in force at `now`: the launch week's (the UTC days 3 to 9 November 2026), or
    the usual ones. Read for each request, so a long-lived server picks up both ends of the
    window."""
    return LAUNCH_LIMITS if LAUNCH_STARTS <= now < LAUNCH_ENDS else LIMITS


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
    """Live research so far, counted as `begin_on_demand_run` counts it: by start time in UTC,
    searches by the run that opened each one, and a run that has not ended at its reservation."""

    model_config = ConfigDict(frozen=True)

    visitor_searches_today: int = Field(ge=0)
    searches_today: int = Field(ge=0)
    usd_today: float = Field(ge=0)
    usd_this_month: float = Field(ge=0)


class Quota(BaseModel):
    """What the web page shows before a live search is spent (GET /api/quota)."""

    model_config = ConfigDict(frozen=True)

    remaining: int = Field(ge=0)
    limit: int = Field(gt=0)
    # When the visitor's daily count starts again: the next midnight UTC.
    resets_at: datetime
    # Whether the global caps would let a search start now. Off when today's searches or
    # budget, or the month's budget, are used up.
    global_open: bool


def day_start(now: datetime) -> datetime:
    """Midnight UTC at the start of `now`'s day, as the database's limits count days."""
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def month_start(now: datetime) -> datetime:
    return day_start(now).replace(day=1)


def seconds_to_next_day(now: datetime) -> int:
    """Whole seconds until the next midnight UTC, when the daily limits start again."""
    return math.ceil((day_start(now) + timedelta(days=1) - now).total_seconds())


def _fits(spent: float, reserve_usd: float, cap: float) -> bool:
    # Rounded as the reservation is sent to the database, so float noise cannot tip it.
    return round(spent + reserve_usd, 6) <= cap


def global_limit(
    usage: OnDemandUsage, limits: LimitSettings, reserve_usd: float
) -> LimitName | None:
    """The global cap that would refuse a new search now, or None. It repeats
    `begin_on_demand_run`'s checks for a search's first run (migration 006), in the same order;
    the database still decides."""
    if usage.searches_today >= limits.searches_per_day:
        return "day_searches"
    if not _fits(usage.usd_today, reserve_usd, limits.usd_per_day):
        return "day_usd"
    if not _fits(usage.usd_this_month, reserve_usd, limits.usd_per_month):
        return "month_usd"
    return None


def search_limit(
    usage: OnDemandUsage, limits: LimitSettings, reserve_usd: float
) -> LimitName | None:
    """The limit that would refuse this visitor's new search now, or None: their own daily
    searches first, as the database checks them, then the global caps."""
    if usage.visitor_searches_today >= limits.user_searches_per_day:
        return "user_day"
    return global_limit(usage, limits, reserve_usd)


def quota(usage: OnDemandUsage, limits: LimitSettings, reserve_usd: float, now: datetime) -> Quota:
    """The visitor's quota. The page says "paused" exactly when the global caps would refuse a
    search (`global_limit`)."""
    return Quota(
        remaining=max(0, limits.user_searches_per_day - usage.visitor_searches_today),
        limit=limits.user_searches_per_day,
        resets_at=day_start(now) + timedelta(days=1),
        global_open=global_limit(usage, limits, reserve_usd) is None,
    )


_LIMIT_MESSAGES: dict[LimitName, str] = {
    "user_day": (
        "You have made {count} live searches today, the daily limit. It resets at midnight UTC."
    ),
    "day_searches": (
        "Live searches have reached today's limit for everyone. It resets at midnight UTC."
    ),
    "day_usd": "Live research has reached today's budget. It resets at midnight UTC.",
    "month_usd": "Live research has used this month's budget and resumes next month.",
    "search": "This search cannot start another run.",
}


def limit_message(limit: LimitName, limits: LimitSettings) -> str:
    """What the player is told when `limit` refuses a search, with the number in force."""
    return _LIMIT_MESSAGES[limit].format(count=limits.user_searches_per_day)


REPORTS_MESSAGE = (
    f"You have sent {LIMITS.reports_per_day} reports today, the daily limit. "
    "It resets at midnight UTC."
)
