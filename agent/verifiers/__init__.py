"""Layers 2 and 3 of the publish gate: model-based verifiers that run after the code checks.

`verify` runs both verifiers on one answer in parallel and returns every layer's result. The
publish decision is made from that record in `agent/gate.py`, so it can be re-scored later with a
different rule or threshold without calling the models again.
"""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor

from agent.config import Settings
from agent.llm import LLMProvider
from agent.schemas import Answer, CodeCheck, Verification
from agent.verifiers.haiku import verify_with_haiku
from agent.verifiers.jev import JevClient, TypeSafeJev, verify_with_jev


def verify(
    answer: Answer,
    code: CodeCheck,
    pages: Mapping[str, str],
    llm: LLMProvider,
    jev: JevClient | None,
    settings: Settings,
) -> Verification:
    """Run layers 2 and 3 on an answer that has been through layer 1.

    `pages` maps each cited URL to the page text the agent read. Pass `jev=None` to skip layer 3
    (for example when no TypeSafe key is configured).
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        haiku_future = pool.submit(verify_with_haiku, answer, pages, llm, settings)
        jev_future = pool.submit(verify_with_jev, answer, pages, jev, settings) if jev else None
        haiku = haiku_future.result()
        jev_report = jev_future.result() if jev_future else None
    return Verification(code=code, haiku=haiku, jev=jev_report)


__all__ = ["JevClient", "TypeSafeJev", "verify", "verify_with_haiku", "verify_with_jev"]
