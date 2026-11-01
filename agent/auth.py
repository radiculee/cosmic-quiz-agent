"""Who a signed-in player is, from the access token their browser sends.

Accounts are optional (docs/SESSIONS.md, Decisions, 2026-10-30). A signed-in browser sends
`Authorization: Bearer <access token>` from Supabase Auth. The server checks the token by asking
Supabase whose it is (`GET /auth/v1/user`) rather than checking its signature here:

  * no new dependency: checking an ES256 or RS256 signature needs `cryptography`, which is large
    for the Vercel bundle, and this uses `httpx2`, already pinned;
  * it works whatever signing keys the project uses;
  * a player who signed out or deleted the account is refused at once, not when the token
    expires (about an hour later).

The cost is one request, only on calls that carry a token. Any failure counts as not signed in,
so a caller falls back to treating the request as a guest's. Anonymous Supabase users are refused
too: they get the `authenticated` role, so they would otherwise pass the accounts' policies.

Only the user id is read from the reply; the email and everything else are ignored and never
kept. The limits key a player by `account_visitor`, a salted hash of the id, never the id.
"""

from __future__ import annotations

import hashlib
import os
import sys
from typing import Self
from uuid import UUID

import httpx2
from pydantic import BaseModel, ConfigDict, ValidationError

URL_ENV = "SUPABASE_URL"
KEY_ENV = "SUPABASE_PUBLISHABLE_KEY"
TIMEOUT_SECONDS = 5.0
# An access token is a JWT of about 1 KB; a header far longer than that is not one.
MAX_TOKEN_LENGTH = 4096


class AuthUser(BaseModel):
    """The part of Supabase's `/auth/v1/user` reply this module uses."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: UUID
    is_anonymous: bool = False


def bearer_token(authorization: str) -> str | None:
    """The token in an `Authorization: Bearer <token>` header, or None if there is none."""
    scheme, _, token = authorization.strip().partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token or len(token) > MAX_TOKEN_LENGTH:
        return None
    if any(character.isspace() for character in token):
        return None
    return token


def _log(message: str) -> None:
    print(f"auth: {message}", file=sys.stderr, flush=True)


class TokenChecker:
    """Checks access tokens against one Supabase project, with its publishable key.

    The key goes on each request, never into the HTTP client's defaults, so a client shared with
    other code can never send it anywhere else. A client passed in stays the caller's to close.
    """

    def __init__(
        self,
        url: str,
        key: str,
        *,
        timeout_seconds: float = TIMEOUT_SECONDS,
        client: httpx2.Client | None = None,
    ) -> None:
        self._endpoint = url.rstrip("/") + "/auth/v1/user"
        self._key = key
        self._owns_client = client is None
        self._client = client or httpx2.Client(timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def user_id(self, authorization: str) -> UUID | None:
        """The signed-in player's id, or None when the header carries no valid token, the user
        is anonymous, or Supabase cannot be asked. Sent once, with no retry, to keep the caller
        fast; a guest's limits are the fallback."""
        token = bearer_token(authorization)
        if token is None:
            return None
        try:
            response = self._client.get(
                self._endpoint,
                headers={"apikey": self._key, "Authorization": f"Bearer {token}"},
            )
        except httpx2.HTTPError as error:
            _log(f"Supabase Auth could not be reached: {type(error).__name__}")
            return None
        status = response.status_code
        if status != 200:
            # 4xx: the token expired, was signed out or its user was deleted; that is a guest,
            # not an error. A rate limit or a server error is logged.
            if status == 429 or status >= 500:
                _log(f"Supabase Auth answered HTTP {status}")
            return None
        try:
            user = AuthUser.model_validate_json(response.content)
        except ValidationError:
            _log("Supabase Auth returned an unexpected reply")
            return None
        return None if user.is_anonymous else user.id


def checker_from_env(client: httpx2.Client | None = None) -> TokenChecker | None:
    """A checker for the project in the environment, or None when it is not configured."""
    url = os.environ.get(URL_ENV, "").strip()
    key = os.environ.get(KEY_ENV, "").strip()
    if not url or not key:
        return None
    return TokenChecker(url, key, client=client)


def signed_in_user(authorization: str) -> UUID | None:
    """The player a request's Authorization header signs in, or None for a guest."""
    if bearer_token(authorization) is None:
        return None
    checker = checker_from_env()
    if checker is None:
        _log(f"{URL_ENV} and {KEY_ENV} must be set to check sign-ins")
        return None
    with checker:
        return checker.user_id(authorization)


def account_visitor(user_id: UUID, salt: str) -> str:
    """The key a signed-in player's limits are kept under: a salted hash of the user id, in the
    same form as an IP address's (`agent.web.salted_hash`). The "account:" prefix keeps it apart
    from every IP key, and without the salt it cannot be matched back to the account."""
    return hashlib.sha256(f"{salt}:account:{user_id}".encode()).hexdigest()
