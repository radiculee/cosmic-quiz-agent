"""POST /api/research {"topic": "..."} or {"surprise": true}

A live search: researches a topic and streams the agent's steps as lines of JSON
(`agent/ondemand.py`). It makes a question and an explanation at each level, leaving out what
the bank already has, and sends each item as it is ready. With "surprise", the agent picks a
topic the bank does not have yet (agent/topic_pick.py). Guarded by the on-topic check (for a
typed topic), the visitor's daily searches and the global caps (DESIGN.md decision 9).
"""

from __future__ import annotations

import os
import sys
import threading
from collections.abc import Generator
from typing import Self

import anthropic
import httpx2
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from agent.bank import BankReader, LiveResults
from agent.config import load_settings
from agent.limits import limits_at
from agent.llm import AnthropicProvider
from agent.ondemand import ResearchEvent, RunTimes, SearchRequest, Services, research
from agent.rest import StoreError
from agent.store import SupabaseStore
from agent.topic_check import InvalidTopicError, JevTopicJudge, clean_topic
from agent.topic_pick import HaikuTopicPicker
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
    # A page loaded before 2026-10-28 still sends "difficulty"; every search now makes all three
    # levels, so it is ignored rather than refused.
    model_config = ConfigDict(extra="ignore")

    topic: str | None = Field(default=None, min_length=1, max_length=200)
    surprise: bool = False

    @model_validator(mode="after")
    def _one_of(self) -> Self:
        if (self.topic is None) == (not self.surprise):
            raise ValueError("send a topic, or surprise: true, but not both")
        return self


# Everything a live search needs. Checked before any client is made, so a server missing one never
# opens connections it cannot use.
REQUIRED_ENV = (
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_SECRET_KEY",
    "ANTHROPIC_API_KEY",
    "TYPESAFE_API_KEY",
    "IP_HASH_SALT",
)

# The same as AnthropicProvider's own client (agent/llm.py), which this replaces only to add the
# rate-limit log line.
ANTHROPIC_TIMEOUT_SECONDS = 60.0
ANTHROPIC_MAX_RETRIES = 3

_services: Services | None = None
_services_lock = threading.Lock()


class NotConfiguredError(Exception):
    pass


def services() -> Services:
    """The clients live searches use, made once per process and shared by its requests (they are
    thread-safe), so a warm serverless instance reuses its connections."""
    global _services
    with _services_lock:
        if _services is None:
            missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
            if missing:
                raise NotConfiguredError(f"missing {', '.join(missing)}")
            settings = load_settings()
            llm = AnthropicProvider(settings.model, client=anthropic_client())
            store = SupabaseStore.from_env()
            _services = Services(
                judge=JevTopicJudge(
                    settings.jev_model, settings.jev_timeout_seconds, settings.jev_input_per_mtok
                ),
                picker=HaikuTopicPicker(llm, settings),
                bank=BankReader.from_env(),
                results=LiveResults.from_env(),
                store=store,
                llm=llm,
                jev=make_jev(settings),
                settings=settings,
                run_times=RunTimes(store.live_run_estimates),
                limits=limits_at,
                sign=sign,
            )
        return _services


def anthropic_client() -> anthropic.Anthropic:
    """The Anthropic client live searches share, logging every 429 it meets."""
    return anthropic.Anthropic(
        timeout=ANTHROPIC_TIMEOUT_SECONDS,
        max_retries=ANTHROPIC_MAX_RETRIES,
        http_client=anthropic.DefaultHttpxClient(event_hooks={"response": [log_rate_limit]}),
    )


def log_rate_limit(response: httpx2.Response) -> None:
    """One log line for every 429 from Anthropic, retries included (decided 2026-10-28), so the
    launch shows whether a search's runs at once meet the account's rate limits. The thread's
    name says which search and item met it; the SDK then waits and retries."""
    if response.status_code != 429:
        return
    headers = response.headers
    print(
        f"anthropic 429: thread={threading.current_thread().name} "
        f"path={response.request.url.path} "
        f"retry_after={headers.get('retry-after', '-')} "
        f"requests_left={headers.get('anthropic-ratelimit-requests-remaining', '-')} "
        f"input_tokens_left={headers.get('anthropic-ratelimit-input-tokens-remaining', '-')} "
        f"output_tokens_left={headers.get('anthropic-ratelimit-output-tokens-remaining', '-')}",
        file=sys.stderr,
    )


def handle(request: ApiRequest) -> ApiResponse | StreamResponse:
    if request.method != "POST":
        return error_response(405, "Use POST.")
    try:
        body = ResearchBody.model_validate(read_json(request))
    except ValidationError:
        return error_response(400, "Send a topic, or ask the agent to pick one.")
    try:
        topic = None if body.topic is None else clean_topic(body.topic)
    except InvalidTopicError as error:
        return error_response(400, str(error))
    if not request.visitor:  # no IP_HASH_SALT: the per-visitor limit cannot be applied
        return error_response(503, "Live research is not available right now.")
    try:
        live = services()
    except (NotConfiguredError, StoreError, ValueError) as error:
        print(f"live research is not configured: {error}", file=sys.stderr)
        return error_response(503, "Live research is not available right now.")
    search = SearchRequest(topic=topic, visitor=request.visitor)
    return StreamResponse(_as_json(research(search, live)))


def _as_json(events: Generator[ResearchEvent]) -> Generator[JsonValue]:
    """The events as JSON objects. Closing this closes `events`, which waits for a started
    search to be stored (agent/ondemand.py)."""
    try:
        for event in events:
            yield event.model_dump(mode="json")
    finally:
        events.close()


app = make_app(handle)
