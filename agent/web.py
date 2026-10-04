"""The small HTTP layer behind the API functions in `api/`.

Each function is a plain `handle(ApiRequest) -> ApiResponse`, which keeps it easy to test.
`make_handler` wraps one in the `BaseHTTPRequestHandler` class that Vercel's Python runtime
calls, and the local dev server (`dev/api_server.py`) uses the same wrapper, so a function
behaves the same locally and on Vercel. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qsl, urlsplit

JsonValue = object  # anything json.dumps accepts; built from validated Pydantic models


@dataclass(frozen=True)
class ApiRequest:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    client_ip: str = ""


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: JsonValue
    headers: dict[str, str] = field(default_factory=dict)


Handle = Callable[[ApiRequest], ApiResponse]


def json_response(body: JsonValue, status: int = 200, cache_seconds: int = 0) -> ApiResponse:
    """A JSON reply. `cache_seconds` lets Vercel's edge cache serve repeats without the database."""
    cache = f"public, s-maxage={cache_seconds}" if cache_seconds else "no-store"
    return ApiResponse(status=status, body=body, headers={"Cache-Control": cache})


def error_response(status: int, message: str) -> ApiResponse:
    return json_response({"error": message}, status=status)


class ApiHandler(BaseHTTPRequestHandler):
    """Serves one API function over HTTP. `make_handler` makes a subclass per function."""

    def api_function(self, request: ApiRequest) -> ApiResponse:
        return error_response(404, f"No API function for {request.path}.")

    def do_GET(self) -> None:
        self._respond()

    def do_POST(self) -> None:
        self._respond()

    def _respond(self) -> None:
        parts = urlsplit(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        # Behind Vercel (and Vite's dev proxy) the client's address is the first entry.
        forwarded = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        request = ApiRequest(
            method=self.command,
            path=parts.path,
            query=dict(parse_qsl(parts.query)),
            body=self.rfile.read(length) if length else b"",
            client_ip=forwarded or self.client_address[0],
        )
        try:
            response = self.api_function(request)
        except Exception:  # never leak internals to the browser; log them for the operator
            traceback.print_exc(file=sys.stderr)
            response = error_response(500, "Something went wrong on our side.")
        data = json.dumps(response.body).encode("utf-8")
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for name, value in response.headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        status = args[1] if len(args) > 1 else ""
        sys.stderr.write(f"{self.command} {self.path} -> {status}" + chr(10))


def salted_hash(value: str, salt: str) -> str:
    """A one-way, salted hash of a visitor's IP address. Only the hash is ever stored, never the
    address (GDPR); without the salt it cannot be matched back to an address."""
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()


def read_json(request: ApiRequest) -> object:
    """The request body as JSON, or None if it is missing or not JSON."""
    try:
        return json.loads(request.body) if request.body else None
    except ValueError:
        return None


def make_handler(handle: Handle) -> type[ApiHandler]:
    """The request handler class for one API function: what Vercel's Python runtime calls."""

    class Handler(ApiHandler):
        def api_function(self, request: ApiRequest) -> ApiResponse:
            return handle(request)

    return Handler
