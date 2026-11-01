"""Checking a signed-in player's access token (agent/auth.py) against a mock Supabase Auth."""

from __future__ import annotations

import io
from collections.abc import Callable
from uuid import UUID
from wsgiref.util import setup_testing_defaults

import httpx2
import pytest

from agent.auth import (
    KEY_ENV,
    MAX_TOKEN_LENGTH,
    URL_ENV,
    TokenChecker,
    account_visitor,
    bearer_token,
    checker_from_env,
    signed_in_user,
)
from agent.web import request_from_environ, salted_hash

BASE = "https://example.supabase.co"
KEY = "sb_publishable_test"
USER_ID = UUID("0b0e6f9c-3f5e-4d0a-9a43-6f1d2b7c8e10")
TOKEN = "eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.c2lnbmF0dXJl"
USER_REPLY = {
    "id": str(USER_ID),
    "aud": "authenticated",
    "role": "authenticated",
    "email": "player@example.com",
    "is_anonymous": False,
}

Handler = Callable[[httpx2.Request], httpx2.Response]


def checker_with(handler: Handler) -> TokenChecker:
    return TokenChecker(BASE, KEY, client=httpx2.Client(transport=httpx2.MockTransport(handler)))


def replying(status: int, body: object) -> Handler:
    return lambda _request: httpx2.Response(status, json=body)


# --- The header ---------------------------------------------------------------------------------


def test_a_bearer_header_gives_its_token() -> None:
    assert bearer_token(f"Bearer {TOKEN}") == TOKEN
    assert bearer_token(f"bearer   {TOKEN}  ") == TOKEN


@pytest.mark.parametrize(
    "header",
    [
        "",
        "Bearer",
        "Bearer ",
        f"Basic {TOKEN}",
        TOKEN,
        f"Bearer {TOKEN} extra",
        "Bearer " + "a" * (MAX_TOKEN_LENGTH + 1),
    ],
)
def test_a_header_without_one_bearer_token_gives_none(header: str) -> None:
    assert bearer_token(header) is None


# --- Asking Supabase ----------------------------------------------------------------------------


def test_a_valid_token_gives_the_user_id() -> None:
    assert checker_with(replying(200, USER_REPLY)).user_id(f"Bearer {TOKEN}") == USER_ID


def test_the_check_sends_the_token_and_the_publishable_key_to_the_user_endpoint() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=USER_REPLY)

    checker_with(handler).user_id(f"Bearer {TOKEN}")

    assert len(seen) == 1
    assert seen[0].method == "GET"
    assert str(seen[0].url) == f"{BASE}/auth/v1/user"
    assert seen[0].headers["apikey"] == KEY
    assert seen[0].headers["authorization"] == f"Bearer {TOKEN}"


def test_no_token_makes_no_request() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=USER_REPLY)

    assert checker_with(handler).user_id("") is None
    assert seen == []


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_a_refused_token_is_a_guest(status: int, capsys: pytest.CaptureFixture[str]) -> None:
    body = {"code": status, "error_code": "bad_jwt", "msg": "invalid JWT"}
    assert checker_with(replying(status, body)).user_id(f"Bearer {TOKEN}") is None
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("status", [429, 500, 503])
def test_a_rate_limit_or_server_error_is_a_guest_and_is_logged(
    status: int, capsys: pytest.CaptureFixture[str]
) -> None:
    assert checker_with(replying(status, {"msg": "busy"})).user_id(f"Bearer {TOKEN}") is None
    assert f"HTTP {status}" in capsys.readouterr().err


def test_a_network_error_is_a_guest_and_is_logged(capsys: pytest.CaptureFixture[str]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    assert checker_with(handler).user_id(f"Bearer {TOKEN}") is None
    assert "could not be reached" in capsys.readouterr().err


@pytest.mark.parametrize("body", [{"id": "not-a-uuid"}, {"email": "x@example.com"}, [], "text"])
def test_an_unexpected_reply_is_a_guest(body: object) -> None:
    assert checker_with(replying(200, body)).user_id(f"Bearer {TOKEN}") is None


def test_an_anonymous_user_is_refused() -> None:
    reply = {**USER_REPLY, "is_anonymous": True}
    assert checker_with(replying(200, reply)).user_id(f"Bearer {TOKEN}") is None


def test_the_key_stays_off_a_shared_client() -> None:
    shared = httpx2.Client(transport=httpx2.MockTransport(replying(200, USER_REPLY)))
    with TokenChecker(BASE, KEY, client=shared) as checker:
        checker.user_id(f"Bearer {TOKEN}")

    assert "apikey" not in shared.headers
    assert not shared.is_closed
    shared.close()


# --- The environment ----------------------------------------------------------------------------


def test_no_checker_without_the_project_in_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(URL_ENV, raising=False)
    monkeypatch.setenv(KEY_ENV, KEY)
    assert checker_from_env() is None


def test_a_checker_from_the_environment_uses_its_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=USER_REPLY)

    monkeypatch.setenv(URL_ENV, BASE + "/")
    monkeypatch.setenv(KEY_ENV, KEY)
    checker = checker_from_env(httpx2.Client(transport=httpx2.MockTransport(handler)))

    assert checker is not None
    assert checker.user_id(f"Bearer {TOKEN}") == USER_ID
    assert str(seen[0].url) == f"{BASE}/auth/v1/user"


def test_signed_in_user_is_a_guest_when_sign_in_is_not_configured(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(URL_ENV, raising=False)
    monkeypatch.delenv(KEY_ENV, raising=False)

    assert signed_in_user("") is None
    assert capsys.readouterr().err == ""
    assert signed_in_user(f"Bearer {TOKEN}") is None
    assert "must be set" in capsys.readouterr().err


# --- The limits' key ----------------------------------------------------------------------------


def test_the_account_key_is_a_salted_hash_of_the_id_never_the_id() -> None:
    key = account_visitor(USER_ID, "salt-a")

    assert key == account_visitor(USER_ID, "salt-a")
    assert key != account_visitor(USER_ID, "salt-b")
    assert str(USER_ID) not in key
    assert str(USER_ID).replace("-", "") not in key
    assert len(key) == 64


def test_the_account_key_has_the_ip_keys_form_and_cannot_match_one() -> None:
    assert account_visitor(USER_ID, "salt") == salted_hash(f"account:{USER_ID}", "salt")
    assert account_visitor(USER_ID, "salt") != salted_hash(str(USER_ID), "salt")


# --- The request --------------------------------------------------------------------------------


def environ_with(headers: dict[str, str]) -> dict[str, object]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ.update({"REQUEST_METHOD": "GET", "PATH_INFO": "/api/account"})
    environ["wsgi.input"] = io.BytesIO(b"")
    environ.update(headers)
    return environ


def test_a_request_without_an_authorization_header_has_none() -> None:
    request = request_from_environ(environ_with({}))
    assert request.authorization == ""


def test_a_request_keeps_its_authorization_header_as_sent() -> None:
    environ = environ_with({"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"})
    request = request_from_environ(environ)
    assert request.authorization == f"Bearer {TOKEN}"
