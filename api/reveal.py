"""GET /api/reveal?id=N: the answer to a quiz item, with its explanation, sources and source check.

Called once the player has answered. Only published items can be revealed.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.bank import BankReader
from agent.rest import StoreError
from agent.web import ApiRequest, ApiResponse, error_response, json_response, make_handler

# An item's answer never changes, so repeats can come from Vercel's edge cache.
CACHE_SECONDS = 300


class RevealQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(gt=0)


def handle(request: ApiRequest) -> ApiResponse:
    if request.method != "GET":
        return error_response(405, "Use GET.")
    try:
        query = RevealQuery.model_validate(request.query)
    except ValidationError:
        return error_response(400, "Give the item's id.")
    try:
        with BankReader.from_env() as bank:
            answer = bank.reveal(query.id)
    except StoreError:
        return error_response(503, "The question bank is not reachable right now.")
    if answer is None:
        return error_response(404, "There is no such quiz item.")
    return json_response(answer.model_dump(mode="json"), cache_seconds=CACHE_SECONDS)


handler = make_handler(handle)
