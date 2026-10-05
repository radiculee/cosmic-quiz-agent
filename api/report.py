"""POST /api/report {"id": N, "reason": "..."}: a player reports an item as wrong or unclear.

Each visitor can report an item once; two reports from different visitors hide it until it is
looked at. A visitor is a salted hash of their IP address (IP_HASH_SALT), never the address.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.bank import BankReader
from agent.rest import StoreError
from agent.store import SupabaseStore
from agent.web import (
    ApiRequest,
    ApiResponse,
    error_response,
    json_response,
    make_app,
    read_json,
)


class ReportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=300)


def handle(request: ApiRequest) -> ApiResponse:
    if request.method != "POST":
        return error_response(405, "Use POST.")
    try:
        body = ReportBody.model_validate(read_json(request))
    except ValidationError:
        return error_response(400, "Send the item's id, and optionally a short reason.")
    if not request.visitor:  # no IP_HASH_SALT configured: reports cannot be told apart
        return error_response(503, "Reports are not available right now.")
    reason = (body.reason or "").strip() or None
    try:
        with BankReader.from_env() as bank:
            if not bank.is_published(body.id):
                return error_response(404, "There is no such item.")
        with SupabaseStore.from_env() as store:
            added = store.add_report(body.id, request.visitor, reason)
    except StoreError:
        return error_response(503, "The question bank is not reachable right now.")
    return json_response({"reported": True, "already": not added})


app = make_app(handle)
