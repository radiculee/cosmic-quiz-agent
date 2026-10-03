"""Layers 2 and 3 and the publish rules, with a scripted model and a fake Jev: no paid calls."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from agent.config import JevCriteria, Settings
from agent.gate import decide, haiku_verdict, jev_verdict, rescore
from agent.llm import JsonObject, LLMError, Usage
from agent.schemas import (
    Citation,
    CitationCheck,
    CodeCheck,
    Explanation,
    HaikuReport,
    JevCheck,
    JevReport,
    QuizItem,
    Verification,
)
from agent.verifiers import haiku as haiku_module
from agent.verifiers import verify
from agent.verifiers.haiku import build_prompt, verify_with_haiku
from agent.verifiers.jev import (
    ClaimAnswer,
    ClaimResults,
    JevError,
    build_claims,
    split_sentences,
    verify_with_jev,
)
from tests.conftest import FakeLLM

URL = "https://en.wikipedia.org/wiki/Neutron_star"
PAGE = (
    "A neutron star is the collapsed core of a massive star. Neutron stars have a radius on "
    "the order of 10 kilometres. They are supported against collapse by neutron degeneracy."
)
PAGES = {URL: PAGE}
ITEM = QuizItem(
    question="What is a neutron star?",
    options=("A young planet", "A collapsed stellar core", "A comet", "A gas cloud"),
    correct_index=1,
    explanation=(
        "A neutron star is the collapsed core of a massive star. It is only about 10 kilometres "
        "across. A young planet is a different object entirely."
    ),
    citations=(Citation(url=URL, quote="A neutron star is the collapsed core of a massive star."),),
)
CODE_PASS = CodeCheck(citations=CitationCheck(kept=ITEM.citations))


def haiku_reply(**overrides: object) -> dict[str, Any]:
    reply: dict[str, Any] = {
        "answer": {
            "verdict": "supported",
            "quote": "A neutron star is the collapsed core of a massive star.",
            "source_url": URL,
        },
        "distractors": [
            {"option": o, "verdict": "wrong", "reason": "Not what the source says."}
            for o in ("A comet", "A young planet", "A gas cloud")  # out of order on purpose
        ],
        "explanation_problems": [],
    }
    reply.update(overrides)
    return reply


class FakeJev:
    """Answers every claim with the probabilities chosen for its key (default: clear support)."""

    criteria: JevCriteria = "astro-1"

    def __init__(self, overrides: Mapping[str, dict[str, float]] | None = None) -> None:
        self.overrides = dict(overrides or {})
        self.states: list[JsonObject] = []
        self.claims: list[dict[str, str]] = []

    def check_claims(self, state: JsonObject, claims: Mapping[str, str]) -> ClaimResults:
        self.states.append(state)
        self.claims.append(dict(claims))
        answers: dict[str, ClaimAnswer] = {}
        for key in claims:
            default = {"supports": 0.02, "contradicts": 0.95, "says_nothing": 0.03}
            if key.startswith(("correct", "sentence")):
                default = {"supports": 0.97, "contradicts": 0.01, "says_nothing": 0.02}
            probabilities = self.overrides.get(key, default)
            verdict = max(probabilities, key=lambda k: probabilities[k])
            answers[key] = ClaimAnswer.model_validate(
                {
                    "verdict": verdict,
                    "confidence": probabilities[verdict],
                    "probabilities": probabilities,
                }
            )
        return ClaimResults(model="jev-1.13.0", input_tokens=1000, answers=answers)


class BrokenJev:
    criteria: JevCriteria = "astro-1"

    def check_claims(self, state: JsonObject, claims: Mapping[str, str]) -> ClaimResults:
        raise JevError("TypeSafeRateLimitError: slow down")


# --- Layer 2: Haiku -----------------------------------------------------------------------------


def test_haiku_prompt_marks_the_correct_option_and_includes_sources() -> None:
    prompt = build_prompt(ITEM, PAGES)

    assert f'<source url="{URL}">' in prompt
    assert "B. A collapsed stellar core  <- marked correct" in prompt


def test_haiku_pass_matches_distractors_by_text(settings: Settings) -> None:
    llm = FakeLLM(json_replies=[haiku_reply()])

    report = verify_with_haiku(ITEM, PAGES, llm, settings)

    assert report.verdict == "pass"
    assert report.answer_quote_verbatim
    assert [d.option for d in report.distractors] == list(ITEM.distractors)
    assert report.cost_usd == pytest.approx(0.00015)


@pytest.mark.parametrize(
    ("overrides", "verdict"),
    [
        ({"answer": {"verdict": "not_found", "quote": "", "source_url": URL}}, "fail"),
        # The verifier claims support but its quote is not on the page: a person decides.
        (
            {
                "answer": {
                    "verdict": "supported",
                    "quote": "Neutron stars are planets.",
                    "source_url": URL,
                }
            },
            "borderline",
        ),
        (
            {
                "distractors": [
                    {"option": "A young planet", "verdict": "also_correct", "reason": "?"},
                    {"option": "A comet", "verdict": "wrong", "reason": "-"},
                    {"option": "A gas cloud", "verdict": "wrong", "reason": "-"},
                ]
            },
            "fail",
        ),
        (
            {
                "distractors": [
                    {"option": "A young planet", "verdict": "unclear", "reason": "?"},
                    {"option": "A comet", "verdict": "wrong", "reason": "-"},
                    {"option": "A gas cloud", "verdict": "wrong", "reason": "-"},
                ]
            },
            "borderline",
        ),
        ({"explanation_problems": ["The size is not stated."]}, "borderline"),
    ],
)
def test_haiku_verdicts(settings: Settings, overrides: dict[str, object], verdict: str) -> None:
    report = verify_with_haiku(
        ITEM, PAGES, FakeLLM(json_replies=[haiku_reply(**overrides)]), settings
    )
    assert report.verdict == verdict


def test_haiku_errors_and_bad_replies_are_reported(settings: Settings) -> None:
    failed = verify_with_haiku(
        ITEM, PAGES, FakeLLM(json_replies=[LLMError("overloaded")]), settings
    )
    malformed = verify_with_haiku(ITEM, PAGES, FakeLLM(json_replies=[{"answer": 1}]), settings)

    assert failed.verdict == "error" and "overloaded" in failed.reasons[0]
    assert malformed.verdict == "error"


def test_haiku_checks_learn_explanations(settings: Settings) -> None:
    answer = Explanation(
        explanation="A neutron star is a collapsed core.", citations=ITEM.citations
    )
    llm = FakeLLM(json_replies=[{"explanation_problems": []}])

    report = verify_with_haiku(answer, PAGES, llm, settings)

    assert report.verdict == "pass"
    assert "<explanation>" in llm.json_prompts[0]


# --- Layer 3: Jev -------------------------------------------------------------------------------


def test_split_sentences_skips_fragments() -> None:
    assert split_sentences(
        "It spins. Neutron stars are dense remnants. About 10 km across, they are tiny."
    ) == [
        "Neutron stars are dense remnants.",
        "About 10 km across, they are tiny.",
    ]


def test_claims_cover_answer_distractors_and_sentences() -> None:
    claims = build_claims(ITEM)

    assert claims["correct_answer"][1].endswith("is: A collapsed stellar core")
    assert sorted(k for k in claims if k.startswith("distractor")) == [
        "distractor_0",
        "distractor_1",
        "distractor_2",
    ]
    assert [kind for kind, _ in claims.values()].count("sentence") == 3


def test_jev_pass_sends_full_pages_as_state(settings: Settings) -> None:
    jev = FakeJev()

    report = verify_with_jev(ITEM, PAGES, jev, settings)

    assert report.verdict == "pass"
    assert jev.states[0] == {"sources": [{"url": URL, "text": PAGE}]}
    assert len(report.checks) == 7
    assert report.cost_usd == pytest.approx(1000 * 0.042 / 1_000_000)


def test_jev_fails_a_supported_distractor(settings: Settings) -> None:
    jev = FakeJev({"distractor_1": {"supports": 0.91, "contradicts": 0.04, "says_nothing": 0.05}})

    report = verify_with_jev(ITEM, PAGES, jev, settings)

    assert report.verdict == "fail"
    assert "supported (0.91) distractor" in report.reasons[0]


def test_jev_weak_support_for_the_answer_is_borderline(settings: Settings) -> None:
    jev = FakeJev({"correct_answer": {"supports": 0.6, "contradicts": 0.1, "says_nothing": 0.3}})

    assert verify_with_jev(ITEM, PAGES, jev, settings).verdict == "borderline"


def test_jev_errors_are_reported(settings: Settings) -> None:
    report = verify_with_jev(ITEM, PAGES, BrokenJev(), settings)
    assert report.verdict == "error" and "slow down" in report.reasons[0]


def test_jev_verdict_can_be_rescored_at_another_threshold() -> None:
    checks = (
        JevCheck(
            kind="correct_answer",
            claim="x",
            verdict="supports",
            confidence=0.85,
            probabilities={"supports": 0.85, "contradicts": 0.05, "says_nothing": 0.1},
        ),
    )

    assert jev_verdict(checks, 0.8)[0] == "pass"
    assert jev_verdict(checks, 0.9)[0] == "borderline"


def test_unsupported_sentences_are_only_flagged_on_request() -> None:
    checks = (
        JevCheck(
            kind="sentence",
            claim="Neutron stars smell of cinnamon.",
            verdict="says_nothing",
            confidence=0.9,
            probabilities={"supports": 0.05, "contradicts": 0.05, "says_nothing": 0.9},
        ),
    )

    assert jev_verdict(checks, 0.8)[0] == "pass"
    assert jev_verdict(checks, 0.8, flag_unsupported_sentences=True)[0] == "borderline"


# --- The publish decision -------------------------------------------------------------------------


def verification(haiku: str, jev: str, code_passed: bool = True) -> Verification:
    code = CODE_PASS if code_passed else CodeCheck(citations=CitationCheck(kept=()))
    return Verification(
        code=code,
        haiku=HaikuReport(verdict=haiku),  # type: ignore[arg-type]
        jev=JevReport(verdict=jev),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("haiku", "jev", "rule", "status"),
    [
        ("pass", "pass", "all_must_pass", "published"),
        ("pass", "borderline", "all_must_pass", "review"),
        ("pass", "fail", "all_must_pass", "discarded"),
        ("pass", "error", "all_must_pass", "review"),
        ("pass", "fail", "jev_escalates", "review"),  # Jev can only escalate, never discard
        ("borderline", "pass", "jev_escalates", "review"),
        ("fail", "pass", "jev_escalates", "discarded"),
        ("pass", "pass", "jev_escalates", "published"),
        ("pass", "fail", "haiku_only", "published"),
        ("fail", "pass", "jev_only", "published"),
    ],
)
def test_gate_rules(haiku: str, jev: str, rule: str, status: str) -> None:
    assert decide(verification(haiku, jev), rule) == status  # type: ignore[arg-type]


def test_layer_one_failure_always_discards() -> None:
    assert decide(verification("pass", "pass", code_passed=False), "haiku_only") == "discarded"


def test_haiku_verdict_ignores_learn_answer_fields() -> None:
    report = HaikuReport(verdict="pass", explanation_problems=())
    assert haiku_verdict(report, is_quiz=False) == ("pass", ())


def test_verify_runs_both_layers(settings: Settings) -> None:
    result = verify(
        ITEM, CODE_PASS, PAGES, FakeLLM(json_replies=[haiku_reply()]), FakeJev(), settings
    )

    assert result.haiku is not None and result.haiku.verdict == "pass"
    assert result.jev is not None and result.jev.verdict == "pass"
    assert decide(result) == "published"


def test_verify_without_jev_goes_to_review(settings: Settings) -> None:
    result = verify(ITEM, CODE_PASS, PAGES, FakeLLM(json_replies=[haiku_reply()]), None, settings)

    assert result.jev is None
    assert decide(result, "all_must_pass") == "review"
    assert decide(result, "haiku_only") == "published"


class CrashingJev:
    criteria: JevCriteria = "astro-1"

    def check_claims(self, state: JsonObject, claims: Mapping[str, str]) -> ClaimResults:
        raise RuntimeError("unexpected SDK bug")


def test_verify_turns_unexpected_failures_into_error_verdicts(settings: Settings) -> None:
    llm = FakeLLM(json_replies=[RuntimeError("boom")])

    verification = verify(ITEM, CODE_PASS, PAGES, llm, CrashingJev(), settings)

    assert verification.haiku is not None and verification.haiku.verdict == "error"
    assert "crashed" in verification.haiku.reasons[0]
    assert verification.jev is not None and verification.jev.verdict == "error"
    assert verification.jev.criteria == "astro-1"
    assert decide(verification) == "review"


def test_verifier_is_skipped_when_its_call_could_cost_too_much(settings: Settings) -> None:
    tight = settings.model_copy(update={"max_verifier_cost_usd": 0.001})
    llm = FakeLLM()  # a model call would fail the test

    report = verify_with_haiku(ITEM, PAGES, llm, tight)

    assert report.verdict == "error" and report.reasons[0].startswith("verifier skipped")


def test_jev_report_records_the_criteria_the_client_sent(settings: Settings) -> None:
    generic = settings.model_copy(update={"jev_criteria": "generic-1"})

    report = verify_with_jev(ITEM, PAGES, FakeJev(), generic)

    assert report.criteria == "astro-1"


def test_rescore_applies_the_current_rules_to_stored_verdicts() -> None:
    # Stored under the old rule: a verifier quote not on the page failed the item.
    stored = HaikuReport(
        verdict="fail",
        reasons=("verifier's supporting quote is not on a cited page",),
        answer_verdict="supported",
        answer_quote="Not on the page.",
        answer_quote_verbatim=False,
    )
    verification = Verification(code=CODE_PASS, haiku=stored, jev=JevReport(verdict="pass"))

    rescored = rescore(verification)

    assert rescored.haiku is not None and rescored.haiku.verdict == "borderline"
    assert decide(verification) == "discarded" and decide(rescored) == "review"


def test_a_billed_verifier_call_that_fails_keeps_its_cost(settings: Settings) -> None:
    cut_off = LLMError("structured output stopped early (max_tokens)", Usage(output_tokens=2048))
    llm = FakeLLM(json_replies=[cut_off])

    report = verify_with_haiku(ITEM, PAGES, llm, settings)

    assert report.verdict == "error"
    assert report.cost_usd == pytest.approx(2048 * 5 / 1_000_000)


def test_a_crash_after_the_verifier_call_keeps_its_cost(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object) -> None:
        raise KeyError("unexpected shape")

    monkeypatch.setattr(haiku_module, "_match_distractors", broken)
    llm = FakeLLM(json_replies=[haiku_reply()])

    report = verify_with_haiku(ITEM, PAGES, llm, settings)

    assert report.verdict == "error" and "crashed" in report.reasons[0]
    assert report.cost_usd > 0


class CountingLLM(FakeLLM):
    def __init__(self, tokens: int | None, replies: list[dict[str, Any] | Exception]) -> None:
        super().__init__(json_replies=replies)
        self.tokens = tokens

    def count_json_tokens(self, system: str, prompt: str, schema: dict[str, Any]) -> int:
        if self.tokens is None:
            raise LLMError("counter unreachable")
        return self.tokens


def test_the_verifier_bound_uses_the_exact_prompt_size(settings: Settings) -> None:
    # 48,000 bytes of page text: the byte bound would skip the verifier at $0.07, but the exact
    # count (12,000 tokens) shows the call costs at most $0.025.
    long_pages = {URL: PAGE + " filler" * 6_800}
    exact = CountingLLM(12_000, [haiku_reply()])
    unknown = CountingLLM(None, [])

    assert verify_with_haiku(ITEM, long_pages, exact, settings).verdict == "pass"
    skipped = verify_with_haiku(ITEM, long_pages, unknown, settings)
    assert skipped.reasons[0].startswith("verifier skipped")
