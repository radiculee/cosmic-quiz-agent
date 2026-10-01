"""The tool-calling loop.

The model decides which tools to call and when to answer. The code owns everything that must
not depend on the model: step, time and token budgets, the citation rule, and the outcome.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from contextlib import ExitStack

import httpx2
from pydantic import ValidationError

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
from agent.prompts.learn import (
    NUDGE,
    SYSTEM_PROMPT,
    WORD_LIMITS,
    length_correction,
    user_prompt,
)
from agent.schemas import CitationCheck, Difficulty, Explanation, Outcome, RunResult, Step
from agent.tools import (
    RESEARCH_TOOLS,
    SUBMIT_ANSWER,
    Tool,
    ToolContext,
    ToolError,
    make_http_client,
)
from agent.verify import check_citations

MAX_NUDGES = 2
# One chance to fix the length; after that a good answer is accepted with a note rather than lost.
MAX_LENGTH_CORRECTIONS = 1
LENGTH_TOLERANCE = 0.1
_MAX_ARGUMENT_PREVIEW = 80


def length_ok(words: int, difficulty: Difficulty) -> bool:
    """Within the difficulty's word range, give or take 10%."""
    low, high = WORD_LIMITS[difficulty]
    return low * (1 - LENGTH_TOLERANCE) <= words <= high * (1 + LENGTH_TOLERANCE)


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
    http_client: httpx2.Client | None = None,
) -> RunResult:
    """Research a topic and return a LEARN explanation, with the full run log and its cost.

    Tools share one HTTP client per run. Pass `http_client` to supply your own (the caller then
    owns closing it); otherwise one is created and closed here.
    """
    run = _Run(settings, on_step)
    tools = {tool.spec.name: tool for tool in RESEARCH_TOOLS}
    tool_specs = [tool.spec for tool in RESEARCH_TOOLS] + [SUBMIT_ANSWER]
    messages: list[Message] = [UserMessage(text=user_prompt(topic, difficulty))]
    nudges = 0
    length_corrections = 0

    with ExitStack() as stack:
        http = http_client or stack.enter_context(make_http_client(settings))
        ctx = ToolContext(settings=settings, http=http)

        def finish(
            outcome: Outcome,
            detail: str = "",
            answer: Explanation | None = None,
            check: CitationCheck | None = None,
        ) -> RunResult:
            return RunResult(
                mode="learn",
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
            length_note = ""
            for call in calls:
                if call.name == SUBMIT_ANSWER.name:
                    result, answer = _accept_answer(call)
                    if answer is not None:
                        words = len(answer.explanation.split())
                        if not length_ok(words, difficulty):
                            if length_corrections < MAX_LENGTH_CORRECTIONS:
                                length_corrections += 1
                                message = length_correction(words, difficulty)
                                result = ToolResult(call_id=call.id, content=message, is_error=True)
                                answer = None
                            else:
                                length_note = f"explanation is {words} words, outside the range"
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
                return finish("passed", length_note, answer=kept, check=check)


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
            tool=call.name,
            is_error=is_error,
        )
    )
    return ToolResult(call_id=call.id, content=content, is_error=is_error)
