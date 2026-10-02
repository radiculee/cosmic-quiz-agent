"""Console helpers shared by the command lines (agent, evals, curator)."""

from __future__ import annotations

import re
import sys

_NOT_SLUG = re.compile("[^a-z0-9]+")


def slugify(text: str, max_chars: int = 40) -> str:
    """A short, file-name-safe form of a topic, for log and payload file names."""
    return _NOT_SLUG.sub("-", text.lower()).strip("-")[:max_chars] or "topic"


def use_utf8_output() -> None:
    """Page text can contain characters the Windows console code page cannot encode."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def confirm(message: str, assume_yes: bool) -> bool:
    """Show a cost estimate and ask before spending. `assume_yes` approves it in advance."""
    print(f"Estimated cost: {message}")
    if assume_yes:
        return True
    try:
        return input("Continue? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:  # no terminal to answer from: treat as no
        print("\nNo answer; stopping. Pass --yes to approve the cost in advance.")
        return False
