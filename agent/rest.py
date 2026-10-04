"""A small client for Supabase's REST API (PostgREST).

Shared by the Curator's store (secret key, `agent/store.py`) and the public bank reads
(publishable key, `agent/bank.py`), so both retry, report errors and validate replies the same way.
"""

from __future__ import annotations

import time
from typing import Self

import httpx2
from pydantic import TypeAdapter, ValidationError

# Retries for requests that are safe to repeat. Waits double each time: 1 s, then 2 s by default.
RETRIES = 2
_RETRY_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
# PostgREST returns at most this many rows per request on Supabase; longer reads are paged.
PAGE_SIZE = 1000


class StoreError(Exception):
    """A read or write to the bank failed. `status` is the HTTP status, if there was a reply."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status

    @property
    def permanent(self) -> bool:
        """The bank refused the request itself (a 4xx other than a timeout or rate limit), so
        sending the same request again cannot succeed."""
        return (
            self.status is not None and 400 <= self.status < 500 and self.status not in (408, 429)
        )


def parse[T](adapter: TypeAdapter[T], reply: object, what: str) -> T:
    """Validate a reply from the database, so a schema mismatch fails loudly here."""
    try:
        return adapter.validate_python(reply)
    except ValidationError as error:
        raise StoreError(f"{what} returned an unexpected reply: {error}") from error


class RestClient:
    """Requests to one Supabase project with one key.

    The key goes on each request, never into the HTTP client's defaults, so a client shared with
    other code can never send it anywhere else. A client passed in stays the caller's to close.
    """

    def __init__(
        self,
        url: str,
        key: str,
        *,
        timeout_seconds: float = 30.0,
        retry_backoff_seconds: float = 1.0,
        client: httpx2.Client | None = None,
    ) -> None:
        self._backoff = retry_backoff_seconds
        self._headers = {"apikey": key, "Content-Type": "application/json"}
        self._owns_client = client is None
        self._client = client or httpx2.Client(timeout=timeout_seconds)
        self._base = url.rstrip("/") + "/rest/v1"

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def send(
        self,
        method: str,
        path: str,
        *,
        json: object = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        retries: int = 0,
    ) -> object:
        """One request, retried `retries` times on network errors, timeouts, rate limits and
        5xx responses. Returns the decoded JSON reply (None for an empty one)."""
        attempt = 0
        while True:
            try:
                response = self._client.request(
                    method,
                    self._base + path,
                    json=json,
                    params=params,
                    headers={**self._headers, **(headers or {})},
                )
            except httpx2.HTTPError as error:
                if attempt < retries:
                    self._wait(attempt)
                    attempt += 1
                    continue
                raise StoreError(f"{method} {path} failed: {type(error).__name__}") from error
            if response.status_code in _RETRY_STATUSES and attempt < retries:
                self._wait(attempt)
                attempt += 1
                continue
            if response.status_code >= 400:
                raise StoreError(
                    f"{method} {path}: HTTP {response.status_code} {response.text}",
                    response.status_code,
                )
            try:
                reply: object = response.json() if response.content else None
            except ValueError as error:
                raise StoreError(f"{method} {path}: the reply was not JSON") from error
            return reply

    def read_all(self, path: str, params: dict[str, str]) -> list[object]:
        """Every row of a read, fetched a page at a time. `params` must include an `order`, so
        the pages do not overlap."""
        rows: list[object] = []
        while True:
            page_params = {**params, "limit": str(PAGE_SIZE), "offset": str(len(rows))}
            reply = self.send("GET", path, params=page_params, retries=RETRIES)
            page = parse(TypeAdapter(list[object]), reply, f"reading {path}")
            rows.extend(page)
            if len(page) < PAGE_SIZE:
                return rows

    def _wait(self, attempt: int) -> None:
        time.sleep(self._backoff * 2**attempt)
