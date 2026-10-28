"""GET /api/topics: every topic in the bank at every level, with the modes and difficulties.

Learn and Quiz list a topic only once both modes are published at all three difficulties
(decided 2026-10-28), so each level offers the same topics. A topic still missing a level is
left out until `python -m curator complete` or `daily` fills it; a live search still finds it
(agent/ondemand.py reads the bank directly).

The UI uses the list to suggest topics as the player types and to pick a random one.
"""

from __future__ import annotations

from agent.bank import BankReader
from agent.rest import StoreError
from agent.web import ApiRequest, ApiResponse, error_response, json_response, make_app

# The bank changes at most once a day (the Curator), so a short edge cache is safe.
CACHE_SECONDS = 300


def handle(request: ApiRequest) -> ApiResponse:
    if request.method != "GET":
        return error_response(405, "Use GET.")
    try:
        with BankReader.from_env() as bank:
            topics = bank.topics()
    except StoreError:
        return error_response(503, "The question bank is not reachable right now.")
    body = {"topics": [topic.model_dump(mode="json") for topic in topics if topic.complete]}
    return json_response(body, cache_seconds=CACHE_SECONDS)


app = make_app(handle)
