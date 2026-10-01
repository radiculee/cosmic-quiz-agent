"""The tool-calling loop.

The model decides which tools to call and when to answer. The code owns everything that must
not depend on the model: step, time and token budgets, the citation rule, and the outcome.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from agent.config import Settings
from agent.llm import (
    LLMError,
    LLMProvider,
    Message,
    ToolCall,
    ToolResult,
    ToolResultsMessage,
    Usage,
    UserMessage,
)
from agent.prompts.learn import NUDGE, SYSTEM_PROMPT, user_prompt
from agent.schemas import Difficulty, Explanation
from agent.tools import (
    RESEARCH_TOOLS,
    SUBMIT_ANSWER,
    Tool,
    ToolContext,
    ToolError,
    make_http_client,
)
from agent.verify import CitationCheck, check_citations

Outcome = Literal[
    "passed",  # answer submitted and at least one citation was fetched in this run
    "failed_citations",  # answer submitted but every citation was dropped
    "no_answer",  # the model kept replying without calling submit_answer
    "budget_exceeded",  # step, time or token budget ran out
    "llm_error",  # a model call failed after retries
]

MAX_NUDGES = 2
_MAX_ARGUMENT_PREVIEW = 80


class Step(BaseModel):
    """One entry in the run log: a model call or a tool call."""

    model_config = ConfigDict(frozen=True)

    index: int
    kind: Literal["model", "tool"]
    summary: str
    seconds: float
    usage: Usage | None = None
    is_error: bool = False


class RunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    topic: str
    difficulty: Difficulty
    model: str
    outcome: Outcome
    detail: str = ""
    answer: Explanation | None = None
    citation_check: CitationCheck | None = None
    fetched_urls: tuple[str, ...] = ()
    steps: tuple[Step, ...] = ()
    model_calls: int = 0
    usage: Usage = Usage()
    cost_usd: float = 0.0
    seconds: float = 0.0


StepCallback = Callable[[Step], None]


class _Run:
    """Mutable state for a single run, kept out of the public function's signature."""

    def __init__(self, settings: Settings, on_step: StepCallback | None) -> None:
        self.settings = settings
        self.on_step = on_step
        self.started = time.monotonic()
        self.steps: list[Step] = []
        self.usage = Usage()
        self.model_calls = 0

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def log(self, step: Step) -> None:
        self.steps.append(step)
        if self.on_step is not None:
            self.on_step(step)

    def budget_problem(self) -> str | None:
        if self.model_calls >= self.settings.max_steps:
            return f"step budget of {self.settings.max_steps} model calls reached"
        if self.elapsed() >= self.settings.max_seconds:
            return f"time budget of {self.settings.max_seconds:.0f}s reached"
        if self.usage.total_input_tokens >= self.settings.max_input_tokens:
            return f"token budget of {self.settings.max_input_tokens} input tokens reached"
        return None


def _preview(arguments: dict[str, object]) -> str:
    text = json.dumps(arguments, ensure_ascii=False)
    if len(text) > _MAX_ARGUMENT_PREVIEW:
        return text[: _MAX_ARGUMENT_PREVIEW - 3] + "..."
    return text


def run_learn(
    topic: str,
    difficulty: Difficulty,
    llm: LLMProvider,
    settings: Settings,
    on_step: StepCallback | None = None,
) -> RunResult:
    """Research a topic and return a LEARN explanation, with the full run log and its cost."""
    run = _Run(settings, on_step)
    tools = {tool.spec.name: tool for tool in RESEARCH_TOOLS}
    tool_specs = [tool.spec for tool in RESEARCH_TOOLS] + [SUBMIT_ANSWER]
    messages: list[Message] = [UserMessage(text=user_prompt(topic, difficulty))]
    nudges = 0

    with make_http_client(settings) as http:
        ctx = ToolContext(settings=settings, http=http)

        def finish(
            outcome: Outcome,
            detail: str = "",
            answer: Explanation | None = None,
            check: CitationCheck | None = None,
        ) -> RunResult:
            return RunResult(
                topic=topic,
                difficulty=difficulty,
                model=llm.model,
                outcome=outcome,
                detail=detail,
                answer=answer,
                citation_check=check,
                fetched_urls=tuple(sorted(ctx.fetched)),
                steps=tuple(run.steps),
                model_calls=run.model_calls,
                usage=run.usage,
                cost_usd=run.usage.cost_usd(settings.price),
                seconds=round(run.elapsed(), 2),
            )

        while True:
            problem = run.budget_problem()
            if problem is not None:
                return finish("budget_exceeded", problem)

            call_started = time.monotonic()
            try:
                completion = llm.complete(
                    SYSTEM_PROMPT, messages, tool_specs, settings.max_output_tokens
                )
            except LLMError as error:
                return finish("llm_error", str(error))
            run.model_calls += 1
            run.usage = run.usage + completion.usage
            messages.append(completion.message)

            calls = completion.message.tool_calls
            names = ", ".join(call.name for call in calls) or "no tool calls"
            run.log(
                Step(
                    index=len(run.steps),
                    kind="model",
                    summary=f"{names} (stop: {completion.stop_reason})",
                    seconds=round(time.monotonic() - call_started, 2),
                    usage=completion.usage,
                )
            )

            if not calls:
                nudges += 1
                if nudges > MAX_NUDGES:
                    return finish("no_answer", "model stopped without calling submit_answer")
                messages.append(UserMessage(text=NUDGE))
                continue

            results: list[ToolResult] = []
            answer: Explanation | None = None
            for call in calls:
                if call.name == SUBMIT_ANSWER.name:
                    result, answer = _accept_answer(call)
                else:
                    result = _run_tool(call, tools, ctx, run)
                results.append(result)
            messages.append(ToolResultsMessage(results=tuple(results)))

            if answer is not None:
                check = check_citations(answer.citations, ctx.fetched)
                if not check.passed:
                    return finish(
                        "failed_citations", "no cited URL was fetched in this run", answer, check
                    )
                kept = Explanation(explanation=answer.explanation, citations=check.kept)
                return finish("passed", answer=kept, check=check)


def _accept_answer(call: ToolCall) -> tuple[ToolResult, Explanation | None]:
    try:
        answer = Explanation.model_validate(call.arguments)
    except ValidationError as error:
        message = f"submit_answer arguments were invalid, fix and call it again: {error}"
        return ToolResult(call_id=call.id, content=message, is_error=True), None
    return ToolResult(call_id=call.id, content="Answer received."), answer


def _run_tool(call: ToolCall, tools: dict[str, Tool], ctx: ToolContext, run: _Run) -> ToolResult:
    started = time.monotonic()
    tool = tools.get(call.name)
    is_error = False
    if tool is None:
        content, is_error = f"Unknown tool {call.name!r}.", True
    else:
        try:
            content = tool.run(call.arguments, ctx)
        except ToolError as error:
            content, is_error = str(error), True

    status = "error" if is_error else f"{len(content)} chars"
    run.log(
        Step(
            index=len(run.steps),
            kind="tool",
            summary=f"{call.name}({_preview(call.arguments)}) -> {status}",
            seconds=round(time.monotonic() - started, 2),
            is_error=is_error,
        )
    )
    return ToolResult(call_id=call.id, content=content, is_error=is_error)
