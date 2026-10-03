"""From one agent run to a publish decision: layers 2 and 3, then the rule in `agent/gate.py`.

The Curator, the evals and the command line all go through `verify_and_decide`, so they can
never decide the same item differently.
"""

from __future__ import annotations

from agent.config import Settings
from agent.gate import DEFAULT_RULE, GateRule, decide
from agent.llm import LLMProvider
from agent.schemas import ItemRecord, RunResult, Status
from agent.verifiers import JevClient, verify


def verify_and_decide(
    result: RunResult,
    llm: LLMProvider,
    jev: JevClient | None,
    settings: Settings,
    rule: GateRule = DEFAULT_RULE,
) -> ItemRecord:
    """Verify a run's answer and decide its status.

    A run with no answer has no status; an answer that failed the layer 1 code checks is
    discarded without spending anything on the verifiers.
    """
    if result.answer is None or result.code_check is None or not result.code_check.passed:
        status: Status | None = "discarded" if result.answer is not None else None
        return ItemRecord(run=result, status=status, rule=rule)
    verification = verify(result.answer, result.code_check, result.cited_pages, llm, jev, settings)
    return ItemRecord(
        run=result, verification=verification, status=decide(verification, rule), rule=rule
    )
