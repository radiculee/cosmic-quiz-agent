"""GET /api/reveal?id=N[&token=T]: a quiz item's answer, explanation, sources and source check.

Called once the player has answered. Without a token only published items can be revealed.
A live run gives its player a token for the item it made (`agent/ondemand.py`), which also
reveals that item while it is in review, with the doubts that held it back.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.bank import BankReader, LiveResults
from agent.ondemand import REVEAL_PURPOSE
from agent.rest import StoreError
from agent.web import (
    ApiRequest,
    ApiResponse,
    error_response,
    json_response,
    make_app,
    verify_signature,
)

# A published item's answer never changes, so repeats can come from Vercel's edge cache.
CACHE_SECONDS = 300


class RevealQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(gt=0)
    token: str = Field(default="", max_length=128)


def handle(request: ApiRequest) -> ApiResponse:
    if request.method != "GET":
        return error_response(405, "Use GET.")
    try:
        query = RevealQuery.model_validate(request.query)
    except ValidationError:
        return error_response(400, "Give the item's id.")
    live = bool(query.token)
    if live and not verify_signature(REVEAL_PURPOSE, str(query.id), query.token):
        return error_response(403, "That answer link is not valid.")
    try:
        with LiveResults.from_env() if live else BankReader.from_env() as reader:
            answer = reader.reveal(query.id)
    except StoreError:
        return error_response(503, "The question bank is not reachable right now.")
    if answer is None:
        return error_response(404, "There is no such quiz item.")
    # A live item may still be in review, so its answer is never cached.
    return json_response(answer.model_dump(mode="json"), cache_seconds=0 if live else CACHE_SECONDS)


app = make_app(handle)
