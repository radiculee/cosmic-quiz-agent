"""The eval history for the analytics page: a short summary of every stored eval run.

    python -m evals export [--out src/data/evals.json]

Eval results stay local (evals/results/ is not committed), so the page cannot read them. This
writes the figures each run's report already holds into one small JSON file that is committed
and built into the UI (decided 2026-10-08): no page text, item text or topic names. Each new
eval run adds an entry, so the file grows into a history. Free: nothing is called.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter

from agent.gate import DEFAULT_RULE
from agent.schemas import Difficulty, ItemRecord, LayerVerdict, Status
from evals.seeding import FAULT_TYPES
from evals.store import ITEMS_FILE, RESULTS_DIR, read_lines

DEFAULT_OUT = Path("src") / "data" / "evals.json"
SUMMARY_FILE = "summary.json"
ONTOPIC_FILE = "ontopic.json"
LEVELS: tuple[Difficulty, ...] = ("easy", "medium", "hard")

# --- What the page reads --------------------------------------------------------------------------


class _Export(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LevelPass(_Export):
    difficulty: Difficulty
    items: int
    layer1_pass: int


class FaultCatches(_Export):
    """Planted faults of one kind, and how many each layer flagged and the gate kept out."""

    fault: str
    items: int
    layer1: int
    haiku: int
    jev: int
    handled: int


class CalibrationBand(_Export):
    band: str  # Jev's confidence, such as "0.90-0.97"
    claims: int
    right: int


class GenerationEval(_Export):
    """One `python -m evals run`, as its report (`python -m evals report`) summarised it."""

    run: str
    at: datetime
    size: Literal["full", "quick"]
    model: str
    jev_model: str | None
    jev_criteria: str | None
    gate_rule: str
    items: int
    layer1_pass: int
    by_difficulty: list[LevelPass]
    unfetched_urls: int
    verified: int
    haiku: dict[LayerVerdict, int]
    jev: dict[LayerVerdict, int]
    agreement: int  # items where Haiku and Jev agree on pass or not
    gate: dict[Status, int]
    seeded: list[FaultCatches]
    calibration: list[CalibrationBand]
    anthropic_usd: float
    typesafe_usd: float


class JudgeScore(_Export):
    judge: str
    right: int


class OntopicEval(_Export):
    """One `python -m evals ontopic`: labelled inputs, and how many each judge got right."""

    run: str
    at: datetime
    inputs: int
    on_topic: int  # inputs that should be researched; the rest should be refused
    judges: list[JudgeScore]


class EvalHistory(_Export):
    generation: list[GenerationEval]
    ontopic: list[OntopicEval]


# --- What the reports hold (evals/report.py) ------------------------------------------------------


class _Report(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class _Level(_Report):
    items: int
    layer1_pass: int


class _Generation(_Report):
    easy: _Level | None = None
    medium: _Level | None = None
    hard: _Level | None = None
    all: _Level
    unfetched_urls_in_passed: int = 0


class _Verifiers(_Report):
    verified: int = 0
    haiku: dict[LayerVerdict, int] = {}
    jev: dict[LayerVerdict, int] = {}
    agreement: int = 0
    status_by_rule: dict[str, dict[Status, int]] = {}


class _Fault(_Report):
    n: int
    layer1: int
    haiku: int
    jev: int
    by_rule: dict[str, int]


class _Band(_Report):
    n: int
    right: int


class _Cost(_Report):
    agent_usd: float = 0.0
    haiku_usd: float = 0.0
    jev_usd: float = 0.0
    seeded_anthropic_usd: float = 0.0
    seeded_typesafe_usd: float = 0.0


class _Summary(_Report):
    generation: _Generation
    verifiers: _Verifiers = _Verifiers()
    seeded: dict[str, _Fault] = {}
    calibration: dict[str, _Band] = {}
    cost: _Cost = _Cost()


class _Judged(_Report):
    expected: bool
    accepted: bool


_ONTOPIC = TypeAdapter(dict[str, list[_Judged]])


# --- Building it ----------------------------------------------------------------------------------


def run_time(run: str) -> datetime:
    """When a run started, from its directory name ("20261001T131332Z-full")."""
    return datetime.strptime(run.split("-", 1)[0], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def _versions(items_path: Path) -> tuple[str, str | None, str | None]:
    """The model, and Jev's model and criteria, from the run's first record that has them."""
    model = ""
    for record in read_lines(items_path, ItemRecord):
        model = model or record.run.model
        jev = record.verification.jev if record.verification else None
        if jev is not None and jev.model:
            return model, jev.model, jev.criteria
    return model, None, None


def generation_eval(run_dir: Path) -> GenerationEval:
    summary = _Summary.model_validate_json((run_dir / SUMMARY_FILE).read_text(encoding="utf-8"))
    model, jev_model, jev_criteria = _versions(run_dir / ITEMS_FILE)
    levels = [(level, getattr(summary.generation, level)) for level in LEVELS]
    cost = summary.cost
    return GenerationEval(
        run=run_dir.name,
        at=run_time(run_dir.name),
        size="quick" if run_dir.name.endswith("-quick") else "full",
        model=model,
        jev_model=jev_model,
        jev_criteria=jev_criteria,
        gate_rule=DEFAULT_RULE,
        items=summary.generation.all.items,
        layer1_pass=summary.generation.all.layer1_pass,
        by_difficulty=[
            LevelPass(difficulty=level, items=found.items, layer1_pass=found.layer1_pass)
            for level, found in levels
            if found is not None
        ],
        unfetched_urls=summary.generation.unfetched_urls_in_passed,
        verified=summary.verifiers.verified,
        haiku=summary.verifiers.haiku,
        jev=summary.verifiers.jev,
        agreement=summary.verifiers.agreement,
        gate=summary.verifiers.status_by_rule.get(DEFAULT_RULE, {}),
        seeded=[
            FaultCatches(
                fault=fault,
                items=found.n,
                layer1=found.layer1,
                haiku=found.haiku,
                jev=found.jev,
                handled=found.by_rule.get(DEFAULT_RULE, 0),
            )
            for fault in FAULT_TYPES
            if (found := summary.seeded.get(fault)) is not None
        ],
        calibration=[
            CalibrationBand(band=band, claims=found.n, right=found.right)
            for band, found in summary.calibration.items()
        ],
        anthropic_usd=cost.agent_usd + cost.haiku_usd + cost.seeded_anthropic_usd,
        typesafe_usd=cost.jev_usd + cost.seeded_typesafe_usd,
    )


def ontopic_eval(run_dir: Path) -> OntopicEval:
    judged = _ONTOPIC.validate_json((run_dir / ONTOPIC_FILE).read_text(encoding="utf-8"))
    cases = next(iter(judged.values()), [])
    return OntopicEval(
        run=run_dir.name,
        at=run_time(run_dir.name),
        inputs=len(cases),
        on_topic=sum(1 for case in cases if case.expected),
        judges=[
            JudgeScore(judge=judge, right=sum(1 for c in results if c.expected == c.accepted))
            for judge, results in sorted(judged.items())
        ],
    )


def collect(results_dir: Path = RESULTS_DIR) -> EvalHistory:
    """Every eval run with a report, oldest first. Runs without one (unfinished, or a
    re-check's own files) are skipped."""
    generation: list[GenerationEval] = []
    ontopic: list[OntopicEval] = []
    for run_dir in sorted(p for p in results_dir.iterdir() if p.is_dir()):
        if (run_dir / SUMMARY_FILE).exists() and (run_dir / ITEMS_FILE).exists():
            generation.append(generation_eval(run_dir))
        elif (run_dir / ONTOPIC_FILE).exists():
            ontopic.append(ontopic_eval(run_dir))
    return EvalHistory(generation=generation, ontopic=ontopic)


def write_history(history: EvalHistory, out: Path = DEFAULT_OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(history.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
    out.write_text(text, encoding="utf-8")
    return out
