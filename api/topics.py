"""GET /api/topics: every topic in the bank, with the modes and difficulties it can be played at.

The UI uses it to suggest topics as the player types and to pick a random one.
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
    body = {"topics": [topic.model_dump(mode="json") for topic in topics]}
    return json_response(body, cache_seconds=CACHE_SECONDS)


app = make_app(handle)
