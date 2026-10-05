"""The small HTTP layer behind the API functions in `api/`.

Each function is a plain `handle(ApiRequest) -> ApiResponse | StreamResponse`, which keeps it
easy to test. `make_app` wraps one in a WSGI application, the form Vercel's Python runtime loads
from the `app` name in an `api/*.py` file. WSGI streams a response by returning an iterator,
which is how /api/research sends the agent's steps as they happen (one JSON object per line).
The local dev server (`dev/api_server.py`) serves the same applications with the standard
library's `wsgiref`, so a function behaves the same locally and on Vercel. Standard library only.

Before a function runs, the request is counted against the visitor's hourly limit
(`agent/limits.py`). A visitor is a salted hash of their IP address, never the address.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import threading
import traceback
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from http import HTTPStatus
from urllib.parse import parse_qsl
from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

from agent.limits import LIMITS, RequestCount
from agent.rest import StoreError
from agent.store import SupabaseStore

JsonValue = object  # anything json.dumps accepts; built from validated Pydantic models

# Request bodies are small JSON objects; anything longer is cut off and fails to parse.
MAX_BODY_BYTES = 16_384
SALT_ENV = "IP_HASH_SALT"


@dataclass(frozen=True)
class ApiRequest:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    client_ip: str = ""
    # The salted hash of `client_ip`, or "" when it cannot be made (no salt configured).
    visitor: str = ""


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: JsonValue
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StreamResponse:
    """A 200 reply sent as it is produced: each event is written as one line of JSON."""

    events: Iterable[JsonValue]


Handle = Callable[[ApiRequest], ApiResponse | StreamResponse]
RequestCounter = Callable[[str], RequestCount | None]


def json_response(body: JsonValue, status: int = 200, cache_seconds: int = 0) -> ApiResponse:
    """A JSON reply. `cache_seconds` lets Vercel's edge cache serve repeats without the database."""
    cache = f"public, s-maxage={cache_seconds}" if cache_seconds else "no-store"
    return ApiResponse(status=status, body=body, headers={"Cache-Control": cache})


def error_response(status: int, message: str, headers: dict[str, str] | None = None) -> ApiResponse:
    response = json_response({"error": message}, status=status)
    return ApiResponse(response.status, response.body, {**response.headers, **(headers or {})})


def too_many_requests(retry_after: int) -> ApiResponse:
    minutes = max(1, round(retry_after / 60))
    return error_response(
        429,
        f"Too many requests this hour. Try again in {minutes} minute{'s' if minutes > 1 else ''}.",
        {"Retry-After": str(retry_after)},
    )


def salted_hash(value: str, salt: str) -> str:
    """A one-way, salted hash of a visitor's IP address. Only the hash is ever stored, never the
    address (GDPR); without the salt it cannot be matched back to an address."""
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()


def sign(purpose: str, value: str) -> str:
    """A token proving the server issued `value` for `purpose` (keyed with the salt secret)."""
    salt = os.environ.get(SALT_ENV, "").strip()
    if not salt:
        raise RuntimeError(f"{SALT_ENV} is not set")
    key = hashlib.sha256(f"token-key:{salt}".encode()).digest()
    return hmac.new(key, f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()


def verify_signature(purpose: str, value: str, token: str) -> bool:
    try:
        expected = sign(purpose, value)
    except RuntimeError:
        return False
    return hmac.compare_digest(expected, token)


def read_json(request: ApiRequest) -> object:
    """The request body as JSON, or None if it is missing or not JSON."""
    try:
        return json.loads(request.body) if request.body else None
    except ValueError:
        return None


# --- Request limits ---------------------------------------------------------------------------

_shared: SupabaseStore | None = None
_shared_lock = threading.Lock()


def _store() -> SupabaseStore:
    """One store per process, so a warm serverless instance reuses its connection."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = SupabaseStore.from_env()
        return _shared


def count_request(visitor: str) -> RequestCount | None:
    """Count one request against the visitor's hourly limit. None when it cannot be counted
    (no database configured or reachable): the request is then served, because the limit guards
    against abuse and must not take the site down with it."""
    try:
        return _store().hit_request_limit(visitor, LIMITS.requests_per_hour)
    except StoreError as error:
        print(f"request limit not counted: {error}", file=sys.stderr)
        return None


# --- WSGI -------------------------------------------------------------------------------------


def client_ip(environ: WSGIEnvironment) -> str:
    """The visitor's address. Vercel replaces X-Forwarded-For with the client's address, and a
    local proxy (Vite) appends it, so the last entry is the one a client cannot forge."""
    forwarded = [part.strip() for part in environ.get("HTTP_X_FORWARDED_FOR", "").split(",")]
    forwarded = [part for part in forwarded if part]
    return forwarded[-1] if forwarded else str(environ.get("REMOTE_ADDR", ""))


def request_from_environ(environ: WSGIEnvironment) -> ApiRequest:
    try:
        length = min(int(environ.get("CONTENT_LENGTH") or 0), MAX_BODY_BYTES)
    except ValueError:
        length = 0
    ip = client_ip(environ)
    salt = os.environ.get(SALT_ENV, "").strip()
    return ApiRequest(
        method=str(environ.get("REQUEST_METHOD", "GET")),
        path=str(environ.get("PATH_INFO", "")),
        query=dict(parse_qsl(str(environ.get("QUERY_STRING", "")))),
        body=environ["wsgi.input"].read(length) if length > 0 else b"",
        client_ip=ip,
        visitor=salted_hash(ip, salt) if salt and ip else "",
    )


def _status_line(status: int) -> str:
    return f"{status} {HTTPStatus(status).phrase}"


def _send(response: ApiResponse, start_response: StartResponse) -> list[bytes]:
    data = json.dumps(response.body).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(data))),
        *response.headers.items(),
    ]
    start_response(_status_line(response.status), headers)
    return [data]


def _lines(events: Iterable[JsonValue]) -> Iterator[bytes]:
    """Each event as a line of JSON. A failure part-way through becomes a last error event.

    The server closes this iterator when the response ends, early if the client left; the close
    is passed on to `events`, so a stream can finish its work before the request ends.
    """
    iterator = iter(events)
    try:
        for event in iterator:
            yield json.dumps(event).encode("utf-8") + b"\n"
    except Exception:
        traceback.print_exc(file=sys.stderr)
        error = {"type": "error", "message": "Something went wrong on our side."}
        yield json.dumps(error).encode("utf-8") + b"\n"
    finally:
        close = getattr(iterator, "close", None)
        if callable(close):
            close()


def make_app(handle: Handle, counter: RequestCounter | None = count_request) -> WSGIApplication:
    """The WSGI application for one API function. Pass `counter=None` to skip request limits."""

    def app(environ: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
        request = request_from_environ(environ)
        if counter is not None and request.visitor:
            counted = counter(request.visitor)
            if counted is not None and not counted.allowed:
                return _send(too_many_requests(counted.retry_after), start_response)
        try:
            response = handle(request)
        except Exception:  # never leak internals to the browser; log them for the operator
            traceback.print_exc(file=sys.stderr)
            response = error_response(500, "Something went wrong on our side.")
        if isinstance(response, StreamResponse):
            start_response(
                _status_line(200),
                [
                    ("Content-Type", "application/x-ndjson; charset=utf-8"),
                    ("Cache-Control", "no-store"),
                    # Ask any proxy in between not to hold the stream back.
                    ("X-Accel-Buffering", "no"),
                ],
            )
            return _lines(response.events)
        return _send(response, start_response)

    return app
