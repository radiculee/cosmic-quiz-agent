"""Deployment packaging: the two dependency lists must not drift apart."""

from __future__ import annotations

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
