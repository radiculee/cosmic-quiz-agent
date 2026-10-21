"""GET /api/quota: the visitor's live searches left today, when that count resets, and whether
the global caps would let a search start now.

The web page shows it before a live search is spent (DESIGN.md decision 9). It is counted from
`on_demand_runs` with the secret key, on the server only: the browser gets four values and never
a visitor hash. The database still decides when a run starts (`begin_on_demand_run`), so a quota
that is a moment out of date can only make the page more cautious or less, never break a limit.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from agent.config import Settings
from agent.limits import limits_at, quota
from agent.rest import StoreError
from agent.store import SupabaseStore
from agent.web import ApiRequest, ApiResponse, error_response, json_response, make_app

UNAVAILABLE = "Live research is not available right now."
# Each run of a search reserves the most it can cost when it starts (agent/ondemand.py). That
# bound is the same for every model, so the default settings give it without reading the
# environment.
RESERVE_USD = Settings().max_job_cost_usd


def handle(request: ApiRequest) -> ApiResponse:
    if request.method != "GET":
        return error_response(405, "Use GET.")
    if not request.visitor:  # no IP_HASH_SALT: visitors cannot be told apart
        return error_response(503, UNAVAILABLE)
    now = datetime.now(UTC)
    try:
        with SupabaseStore.from_env() as store:
            usage = store.on_demand_usage(request.visitor, now)
    except StoreError as error:
        print(f"quota not read: {error}", file=sys.stderr)
        return error_response(503, UNAVAILABLE)
    # Per visitor, so never cached at the edge (json_response sends no-store).
    return json_response(quota(usage, limits_at(now), RESERVE_USD, now).model_dump(mode="json"))


app = make_app(handle)
