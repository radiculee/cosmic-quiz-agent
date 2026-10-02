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
from agent.schemas import Answer, CodeCheck, HaikuReport, JevReport, Verification
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

    Never raises: an unexpected failure in either verifier becomes that layer's "error" verdict,
    which sends the item to review, so a paid agent run is never lost to a verifier bug.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        haiku_future = pool.submit(verify_with_haiku, answer, pages, llm, settings)
        jev_future = pool.submit(verify_with_jev, answer, pages, jev, settings) if jev else None
        try:
            haiku = haiku_future.result()
        except Exception as error:
            haiku = HaikuReport(verdict="error", reasons=(f"verifier crashed: {error!r}",))
        jev_report: JevReport | None = None
        if jev is not None and jev_future is not None:
            try:
                jev_report = jev_future.result()
            except Exception as error:
                jev_report = JevReport(
                    verdict="error",
                    reasons=(f"Jev check crashed: {error!r}",),
                    model=settings.jev_model,
                    criteria=jev.criteria,
                    threshold=settings.jev_threshold,
                )
    return Verification(code=code, haiku=haiku, jev=jev_report)


__all__ = ["JevClient", "TypeSafeJev", "verify", "verify_with_haiku", "verify_with_jev"]
