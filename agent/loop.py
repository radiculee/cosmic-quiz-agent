"""The tool-calling loop, shared by LEARN and QUIZ.

The model decides which tools to call and when to answer. The code owns everything that must
not depend on the model: step, time and token budgets, the layer 1 checks (fetched URLs,
verbatim quotes, numbers), the word range, and the outcome.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass

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
    ToolSpec,
    Usage,
    UserMessage,
    prompt_tokens_bound,
)
from agent.prompts import learn, quiz
from agent.prompts.common import WORD_LIMITS, correction, length_problem, nudge
from agent.schemas import (
    CodeCheck,
    Difficulty,
    Explanation,
    Mode,
    Outcome,
    QuizItem,
    RunResult,
    Step,
)
from agent.tools import (
    RESEARCH_TOOLS,
    SUBMIT_ANSWER,
    SUBMIT_QUIZ,
    Tool,
    ToolContext,
    ToolError,
    make_http_client,
)
from agent.verify import cited_pages, code_check

MAX_NUDGES = 2
# One round to fix the code-check problems and the length. After that, a wrong length is accepted
# with a note, bad citations are dropped, and an unsupported number fails the run.
MAX_ANSWER_CORRECTIONS = 1
LENGTH_TOLERANCE = 0.1
_MAX_ARGUMENT_PREVIEW = 80

StepCallback = Callable[[Step], None]


@dataclass(frozen=True)
class Task[AnswerT: (Explanation, QuizItem)]:
    """What one run should produce: its prompts, its submit tool and its answer model."""

    mode: Mode
    topic: str
    difficulty: Difficulty
    system_prompt: str
    user_prompt: str
    submit_tool: ToolSpec
    answer_model: type[AnswerT]


def learn_task(
    topic: str, difficulty: Difficulty, lead_url: str | None = None
) -> Task[Explanation]:
    return Task(
        mode="learn",
        topic=topic,
        difficulty=difficulty,
        system_prompt=learn.SYSTEM_PROMPT,
        user_prompt=learn.user_prompt(topic, difficulty, lead_url),
        submit_tool=SUBMIT_ANSWER,
        answer_model=Explanation,
    )


def quiz_task(topic: str, difficulty: Difficulty, lead_url: str | None = None) -> Task[QuizItem]:
    return Task(
        mode="quiz",
        topic=topic,
        difficulty=difficulty,
        system_prompt=quiz.SYSTEM_PROMPT,
        user_prompt=quiz.user_prompt(topic, difficulty, lead_url),
        submit_tool=SUBMIT_QUIZ,
        answer_model=QuizItem,
    )


def length_ok(words: int, difficulty: Difficulty) -> bool:
    """Within the difficulty's word range, give or take 10%."""
    low, high = WORD_LIMITS[difficulty]
    return low * (1 - LENGTH_TOLERANCE) <= words <= high * (1 + LENGTH_TOLERANCE)


def shuffle_options(item: QuizItem, rng: random.Random) -> QuizItem:
    """Put the correct option at a random position, so models' position habits do not leak."""
    order = list(range(len(item.options)))
    rng.shuffle(order)
    options = tuple(item.options[i] for i in order)
    return item.model_copy(
        update={"options": options, "correct_index": order.index(item.correct_index)}
    )


class _Run:
    """Mutable state for a single run, kept out of the public functions' signatures."""

    def __init__(self, settings: Settings, on_step: StepCallback | None) -> None:
        self.settings = settings
        self.on_step = on_step
        self.started = time.monotonic()
        self.steps: list[Step] = []
        self.usage = Usage()
        self.model_calls = 0
        # For the cost bound: the exact prompt size of the last call, and how many messages it had.
        self.last_prompt_tokens: int | None = None
        self.messages_sent = 0

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def log(self, step: Step) -> None:
        self.steps.append(step)
        if self.on_step is not None:
            self.on_step(step)

    def next_call_bound_usd(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> float:
        """An upper bound on what the next call can cost. After the first call the previous
        prompt's exact size is known, so only the messages added since are bounded by bytes."""
        if self.last_prompt_tokens is None:
            texts = [system, *(m.model_dump_json() for m in messages)]
            tokens = prompt_tokens_bound(*texts, *(t.model_dump_json() for t in tools))
        else:
            added = (m.model_dump_json() for m in messages[self.messages_sent :])
            tokens = self.last_prompt_tokens + prompt_tokens_bound(*added)
        return self.settings.price.max_call_cost_usd(tokens, self.settings.max_output_tokens)

    def budget_problem(self, next_call_usd: float) -> str | None:
        if self.model_calls >= self.settings.max_steps:
            return f"step budget of {self.settings.max_steps} model calls reached"
        if self.elapsed() >= self.settings.max_seconds:
            return f"time budget of {self.settings.max_seconds:.0f}s reached"
        if self.usage.total_input_tokens >= self.settings.max_input_tokens:
            return f"token budget of {self.settings.max_input_tokens} input tokens reached"
        spent = self.usage.cost_usd(self.settings.price)
        if spent + next_call_usd > self.settings.max_run_cost_usd:
            return (
                f"cost limit of ${self.settings.max_run_cost_usd:.2f} per run reached: spent "
                f"${spent:.4f}, and the next call could cost up to ${next_call_usd:.4f}"
            )
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
    lead_url: str | None = None,
) -> RunResult:
    """Research a topic and return a LEARN explanation, with the full run log and its cost.

    `lead_url` is a news article to start from, for topics the Curator found in a feed.
    """
    task = learn_task(topic, difficulty, lead_url)
    return run_agent(task, llm, settings, on_step, http_client)


def run_quiz(
    topic: str,
    difficulty: Difficulty,
    llm: LLMProvider,
    settings: Settings,
    on_step: StepCallback | None = None,
    http_client: httpx2.Client | None = None,
    rng: random.Random | None = None,
    lead_url: str | None = None,
) -> RunResult:
    """Research a topic and return one quiz item, with its options in random order."""
    task = quiz_task(topic, difficulty, lead_url)
    result = run_agent(task, llm, settings, on_step, http_client)
    if isinstance(result.answer, QuizItem):
        shuffled = shuffle_options(result.answer, rng or random.Random())
        result = result.model_copy(update={"answer": shuffled})
    return result


def run_agent[AnswerT: (Explanation, QuizItem)](
    task: Task[AnswerT],
    llm: LLMProvider,
    settings: Settings,
    on_step: StepCallback | None = None,
    http_client: httpx2.Client | None = None,
) -> RunResult:
    """Run the tool-calling loop for one task.

    Tools share one HTTP client per run. Pass `http_client` to supply your own (the caller then
    owns closing it); otherwise one is created and closed here.
    """
    run = _Run(settings, on_step)
    tools = {tool.spec.name: tool for tool in RESEARCH_TOOLS}
    tool_specs = [tool.spec for tool in RESEARCH_TOOLS] + [task.submit_tool]
    messages: list[Message] = [UserMessage(text=task.user_prompt)]
    nudges = 0
    corrections = 0

    with ExitStack() as stack:
        http = http_client or stack.enter_context(make_http_client(settings))
        ctx = ToolContext(settings=settings, http=http)

        def finish(
            outcome: Outcome,
            detail: str = "",
            answer: AnswerT | None = None,
            check: CodeCheck | None = None,
        ) -> RunResult:
            pages = cited_pages(answer.citations, ctx.fetched) if answer is not None else {}
            return RunResult(
                mode=task.mode,
                topic=task.topic,
                difficulty=task.difficulty,
                model=llm.model,
                outcome=outcome,
                detail=detail,
                answer=answer,
                code_check=check,
                cited_pages=pages,
                fetched_urls=tuple(sorted(ctx.fetched)),
                pages_read=tuple(ctx.reads),
                steps=tuple(run.steps),
                model_calls=run.model_calls,
                nudges=nudges,
                usage=run.usage,
                cost_usd=run.usage.cost_usd(settings.price),
                seconds=round(run.elapsed(), 2),
            )

        while True:
            bound = run.next_call_bound_usd(task.system_prompt, messages, tool_specs)
            problem = run.budget_problem(bound)
            if problem is not None:
                return finish("budget_exceeded", problem)

            call_started = time.monotonic()
            run.messages_sent = len(messages)
            try:
                completion = llm.complete(
                    task.system_prompt, messages, tool_specs, settings.max_output_tokens
                )
            except LLMError as error:
                return finish("llm_error", str(error))
            run.model_calls += 1
            run.usage = run.usage + completion.usage
            run.last_prompt_tokens = completion.usage.total_input_tokens
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
                if nudges >= MAX_NUDGES:
                    return finish(
                        "no_answer", f"model stopped without calling {task.submit_tool.name}"
                    )
                nudges += 1
                messages.append(UserMessage(text=nudge(task.submit_tool.name)))
                continue

            results: list[ToolResult] = []
            final: tuple[AnswerT, CodeCheck, list[str]] | None = None
            for call in calls:
                if call.name != task.submit_tool.name:
                    results.append(_run_tool(call, tools, ctx, run))
                    continue
                answer = _parse_answer(call, task)
                if isinstance(answer, ToolResult):
                    results.append(answer)  # invalid arguments: the model is told and tries again
                    continue
                check = code_check(answer, ctx.fetched)
                words = len(answer.explanation.split())
                problems = list(check.problems)
                if not length_ok(words, task.difficulty):
                    problems.append(length_problem(words, task.difficulty))
                if problems and corrections < MAX_ANSWER_CORRECTIONS:
                    corrections += 1
                    message = correction(problems, task.submit_tool.name)
                    results.append(ToolResult(call_id=call.id, content=message, is_error=True))
                    continue
                results.append(ToolResult(call_id=call.id, content="Answer received."))
                final = (answer, check, problems)
            messages.append(ToolResultsMessage(results=tuple(results)))

            if final is not None:
                answer, check, problems = final
                if not check.passed:
                    return finish("failed_checks", "; ".join(check.problems), answer, check)
                kept = answer.model_copy(update={"citations": check.citations.kept})
                return finish("passed", "; ".join(problems), kept, check)


def _parse_answer[AnswerT: (Explanation, QuizItem)](
    call: ToolCall, task: Task[AnswerT]
) -> AnswerT | ToolResult:
    try:
        return task.answer_model.model_validate(call.arguments)
    except ValidationError as error:
        message = f"{task.submit_tool.name} arguments were invalid, fix and call it again: {error}"
        return ToolResult(call_id=call.id, content=message, is_error=True)


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
            arguments=call.arguments,
            is_error=is_error,
        )
    )
    return ToolResult(call_id=call.id, content=content, is_error=is_error)
