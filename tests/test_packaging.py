"""Deployment packaging: the two dependency lists must not drift apart, and every response
carries the security headers (docs/SECURITY_AUDIT.md S5)."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_and_requirements_pin_the_same_runtime_dependencies() -> None:
    # Vercel installs from pyproject.toml; pip (the Curator workflow, local setup) from
    # requirements.txt. A dependency added to one only would break the other at runtime.
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    assert sorted(project["dependencies"]) == sorted(requirements)
    assert all("==" in pin for pin in requirements), "runtime dependencies must be pinned"


def test_vercel_runs_the_python_version_we_test_on() -> None:
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


def _headers() -> dict[str, str]:
    """The headers vercel.json sends with every path."""
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    every_path = [rule for rule in config["headers"] if rule["source"] == "/(.*)"]
    assert len(every_path) == 1, "one header rule covers every path, pages and API alike"
    return {header["key"]: header["value"] for header in every_path[0]["headers"]}


def _csp() -> dict[str, list[str]]:
    """The Content-Security-Policy as directive -> sources."""
    directives = (part.split() for part in _headers()["Content-Security-Policy"].split(";"))
    return {words[0]: words[1:] for words in directives if words}


def test_every_response_carries_the_security_headers() -> None:
    headers = _headers()

    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    for feature in ("camera", "microphone", "geolocation", "payment", "usb"):
        assert f"{feature}=()" in headers["Permissions-Policy"]


def test_the_content_security_policy_allows_only_this_site_and_its_fonts() -> None:
    policy = _csp()

    assert policy["default-src"] == ["'self'"]
    assert policy["script-src"] == ["'self'"]  # no inline or outside scripts
    assert policy["style-src"] == ["'self'", "https://fonts.googleapis.com"]
    assert policy["font-src"] == ["https://fonts.gstatic.com"]
    assert policy["connect-src"] == ["'self'"]  # the UI only calls its own /api
    assert policy["frame-ancestors"] == ["'none'"]  # no other site may frame the game
    assert policy["object-src"] == ["'none'"] and policy["base-uri"] == ["'none'"]
    assert "upgrade-insecure-requests" in policy
    assert not any("unsafe" in source for sources in policy.values() for source in sources)


def test_the_page_has_no_inline_script_the_policy_would_block() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script([^>]*)>(.*?)</script>", html, flags=re.DOTALL)

    assert scripts, "the page loads its bundle with a script tag"
    for attributes, body in scripts:
        assert 'src="' in attributes and not body.strip()
