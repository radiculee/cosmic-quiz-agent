"""GET /api/item?topic=...&mode=quiz|learn&difficulty=easy|medium|hard[&exclude=1,2,3]

A random published item for the topic, mode and difficulty. A quiz item comes without its
answer, explanation or sources: those are fetched from /api/reveal once the player has answered,
so the answer is never in the browser before then. `exclude` lists items this browser has
already shown, avoided while there is another to show.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.bank import BankReader
from agent.rest import StoreError
from agent.schemas import Difficulty, Mode
from agent.web import ApiRequest, ApiResponse, error_response, json_response, make_handler

# The browser sends every item it has shown (up to 500, src/profile.ts) so they are skipped.
MAX_EXCLUDED = 500


class ItemQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic: str = Field(min_length=1, max_length=200)
    mode: Mode
    difficulty: Difficulty
    exclude: str = ""

    def excluded_ids(self) -> frozenset[int]:
        ids = (part.strip() for part in self.exclude.split(","))
        return frozenset(int(part) for part in ids if part.isdigit())


def handle(request: ApiRequest) -> ApiResponse:
    if request.method != "GET":
        return error_response(405, "Use GET.")
    try:
        query = ItemQuery.model_validate(request.query)
    except ValidationError:
        return error_response(400, "Give a topic, a mode (learn or quiz) and a difficulty.")
    excluded = query.excluded_ids()
    if len(excluded) > MAX_EXCLUDED:
        return error_response(400, f"Exclude at most {MAX_EXCLUDED} items.")
    try:
        with BankReader.from_env() as bank:
            item = bank.random_item(query.topic, query.mode, query.difficulty, excluded)
    except StoreError:
        return error_response(503, "The question bank is not reachable right now.")
    if item is None:
        return error_response(404, "There is no item for that topic, mode and difficulty yet.")
    return json_response(item.model_dump(mode="json"))


handler = make_handler(handle)
