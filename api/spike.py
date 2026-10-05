"""GET /api/spike?seconds=N: a temporary probe for the Session 7 Vercel spike (removed after it).

Streams one line a second for N seconds (at most 320, past the 300-second limit) with the server's
clock, and first echoes the headers that carry the client's address. It answers:

* Are WSGI responses delivered line by line, or held back until the end?
* Does the 300-second limit cut a stream, and how?
* Does closing the stream early reach the app (the live run's thread waits on that)?
* Which address does a visitor appear from (X-Forwarded-For and friends)?

It costs nothing: no model, no database. It is not counted against request limits.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Generator

from agent.web import ApiRequest, ApiResponse, JsonValue, StreamResponse, error_response, make_app

MAX_SECONDS = 320


def _ticks(seconds: int, request: ApiRequest, started: float) -> Generator[JsonValue]:
    sent = 0
    try:
        yield {
            "type": "hello",
            "client_ip": request.client_ip,
            "visitor_hashed": bool(request.visitor),
            "query": request.query,
        }
        for tick in range(1, seconds + 1):
            time.sleep(1.0)
            sent = tick
            yield {"type": "tick", "tick": tick, "server_seconds": round(time.time() - started, 2)}
        yield {"type": "done", "server_seconds": round(time.time() - started, 2)}
    finally:
        # Shows in the function's log: whether an early close reached the app, and when.
        print(
            f"spike: stream closed after {sent} tick(s), {time.time() - started:.1f}s",
            file=sys.stderr,
        )


def handle(request: ApiRequest) -> ApiResponse | StreamResponse:
    if request.method != "GET":
        return error_response(405, "Use GET.")
    try:
        seconds = int(request.query.get("seconds", "5"))
    except ValueError:
        return error_response(400, "seconds must be a whole number.")
    if not 0 <= seconds <= MAX_SECONDS:
        return error_response(400, f"seconds must be between 0 and {MAX_SECONDS}.")
    return StreamResponse(_ticks(seconds, request, time.time()))


app = make_app(handle, counter=None)
