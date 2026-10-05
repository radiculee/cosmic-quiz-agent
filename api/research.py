"""POST /api/research {"topic": "...", "mode": "learn"|"quiz", "difficulty": "easy"|...}

Researches a custom topic live and streams the agent's steps as lines of JSON
(`agent/ondemand.py`), ending with the item, a rejection, or a fallback to the bank. Guarded by
the on-topic check, the visitor's daily limit and the global caps (DESIGN.md decision 9).
"""

from __future__ import annotations

import os
import sys
import threading
from collections.abc import Generator

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.bank import BankReader, LiveResults
from agent.config import load_settings
from agent.limits import LIMITS
from agent.llm import AnthropicProvider
from agent.ondemand import LiveJob, ResearchEvent, Services, research
from agent.rest import StoreError
from agent.schemas import Difficulty, Mode
from agent.store import SupabaseStore
from agent.topic_check import InvalidTopicError, JevTopicJudge, clean_topic
from agent.verifiers import make_jev
from agent.web import (
    ApiRequest,
    ApiResponse,
    JsonValue,
    StreamResponse,
    error_response,
    make_app,
    read_json,
    sign,
)


class ResearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=200)
    mode: Mode
    difficulty: Difficulty


# Everything a live run needs. Checked before any client is made, so a server missing one never
# opens connections it cannot use.
REQUIRED_ENV = (
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_SECRET_KEY",
    "ANTHROPIC_API_KEY",
    "TYPESAFE_API_KEY",
    "IP_HASH_SALT",
)

_services: Services | None = None
_services_lock = threading.Lock()


class NotConfiguredError(Exception):
    pass


def services() -> Services:
    """The clients live runs use, made once per process and shared by its requests (they are
    thread-safe), so a warm serverless instance reuses its connections."""
    global _services
    with _services_lock:
        if _services is None:
            missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
            if missing:
                raise NotConfiguredError(f"missing {', '.join(missing)}")
            settings = load_settings()
            _services = Services(
                judge=JevTopicJudge(
                    settings.jev_model, settings.jev_timeout_seconds, settings.jev_input_per_mtok
                ),
                bank=BankReader.from_env(),
                results=LiveResults.from_env(),
                store=SupabaseStore.from_env(),
                llm=AnthropicProvider(settings.model),
                jev=make_jev(settings),
                settings=settings,
                limits=LIMITS,
                sign=sign,
            )
        return _services


def handle(request: ApiRequest) -> ApiResponse | StreamResponse:
    if request.method != "POST":
        return error_response(405, "Use POST.")
    try:
        body = ResearchBody.model_validate(read_json(request))
    except ValidationError:
        return error_response(400, "Send a topic, a mode (learn or quiz) and a difficulty.")
    try:
        topic = clean_topic(body.topic)
    except InvalidTopicError as error:
        return error_response(400, str(error))
    if not request.visitor:  # no IP_HASH_SALT: the per-visitor limit cannot be applied
        return error_response(503, "Live research is not available right now.")
    try:
        live = services()
    except (NotConfiguredError, StoreError, ValueError) as error:
        print(f"live research is not configured: {error}", file=sys.stderr)
        return error_response(503, "Live research is not available right now.")
    job = LiveJob(topic=topic, mode=body.mode, difficulty=body.difficulty, visitor=request.visitor)
    return StreamResponse(_as_json(research(job, live)))


def _as_json(events: Generator[ResearchEvent]) -> Generator[JsonValue]:
    """The events as JSON objects. Closing this closes `events`, which waits for a started run
    to be stored (agent/ondemand.py)."""
    try:
        for event in events:
            yield event.model_dump(mode="json")
    finally:
        events.close()


app = make_app(handle)
