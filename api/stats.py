"""GET /api/stats: Mission Control, "The agent" tab (docs/PLAN.md Session 9).

    /api/stats?mode=learn|quiz&difficulty=easy|medium|hard&source=curator|on_demand&days=7|30

The agent's measured statistics for the chosen runs, with the month's spend against the caps.
Each filter left out means all; `days` left out is all time.

Aggregates only: `agent_stats()` (migration 007) counts in the database and is all the
publishable key may run against the agent's runs. The figures change only when a run is stored,
so each filter set is cached at the edge for ten minutes and repeats never reach the database.
"""

from __future__ import annotations

import sys

from pydantic import BaseModel, ConfigDict, ValidationError

from agent.rest import StoreError
from agent.schemas import Difficulty, Mode
from agent.stats import Period, StatsFilters, StatsReader, stats_reply
from agent.store import RunSource
from agent.web import ApiRequest, ApiResponse, error_response, json_response, make_app

CACHE_SECONDS = 600


class StatsQuery(BaseModel):
    # Unknown parameters and other spellings of a value are refused rather than read, so they
    # cannot make new cache entries.
    model_config = ConfigDict(extra="forbid")

    mode: Mode | None = None
    difficulty: Difficulty | None = None
    source: RunSource | None = None
    days: Period | None = None

    def filters(self) -> StatsFilters:
        return StatsFilters(
            mode=self.mode,
            difficulty=self.difficulty,
            source=self.source,
            days=None if self.days is None else int(self.days),
        )


def handle(request: ApiRequest) -> ApiResponse:
    if request.method != "GET":
        return error_response(405, "Use GET.")
    try:
        query = StatsQuery.model_validate(request.query)
    except ValidationError:
        return error_response(
            400,
            "Filter by mode (learn or quiz), difficulty (easy, medium or hard), source "
            "(curator or on_demand) and days (7 or 30), or leave any of them out.",
        )
    try:
        with StatsReader.from_env() as reader:
            stats = reader.agent_stats(query.filters())
    except StoreError as error:
        print(f"stats not read: {error}", file=sys.stderr)
        return error_response(503, "The statistics are not reachable right now.")
    return json_response(stats_reply(stats).model_dump(mode="json"), cache_seconds=CACHE_SECONDS)


app = make_app(handle)
