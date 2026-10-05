"""The Curator's pipeline: research -> draft -> verify -> publish / review / discard -> retire.

A job is one topic in one mode at one difficulty. Each job runs the agent, the three-layer
publish gate and the publish rule (`agent/gate.py`), and its whole record is stored, whatever the
outcome. Jobs run on a few worker threads under a hard dollar cap on Anthropic spend: every job
reserves the most it can possibly cost (`job_cost_limit`, enforced before each model call), so
the cap holds even if every running job turns out as expensive as allowed.

Every payload is written to disk before it is sent to the bank and removed once stored, so a
database or network failure never loses a run that has already been paid for: the next Curator
run sends it again first, and the bank ignores a payload it already holds. On a fresh machine
each run (GitHub Actions), the pending folder must be carried between runs for this to work.
"""

from __future__ import annotations

import contextlib
import threading
from collections import deque
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent.config import Settings
from agent.console import slugify
from agent.llm import LLMProvider
from agent.loop import run_learn, run_quiz
from agent.publish import verify_and_decide
from agent.schemas import Difficulty, ItemRecord, Mode
from agent.store import (
    CuratorSummary,
    CuratorTrigger,
    ItemPayload,
    JobKey,
    Store,
    StoreError,
    TopicRef,
    build_payload,
    job_key,
)
from agent.verifiers import JevClient

MODES: tuple[Mode, ...] = ("learn", "quiz")
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")

# Typical Anthropic cost per job (agent run plus the Haiku verifier), measured over the 180 runs
# of the bank build on 2026-10-02. Used for the estimate shown before a run.
JOB_COST_TYPICAL: dict[Mode, float] = {"learn": 0.027, "quiz": 0.029}
# How often the job loop wakes while jobs run. A wait without a timeout cannot be interrupted by
# Ctrl+C on Windows, so the loop polls instead.
_POLL_SECONDS = 1.0


def _print_now(message: str) -> None:
    """Print and flush, so progress shows up live in redirected logs (GitHub Actions)."""
    print(message, flush=True)


def job_cost_limit(settings: Settings) -> float:
    """The most one job can spend on Anthropic (see `Settings.max_job_cost_usd`)."""
    return settings.max_job_cost_usd


@dataclass(frozen=True)
class Job:
    topic: TopicRef
    mode: Mode
    difficulty: Difficulty

    @property
    def key(self) -> JobKey:
        return job_key(self.topic.name, self.mode, self.difficulty)

    @property
    def label(self) -> str:
        return f"{self.mode:<5} {self.difficulty:<6} {self.topic.name}"


def plan_jobs(topics: Sequence[TopicRef], attempted: set[JobKey]) -> tuple[list[Job], int]:
    """Every mode and difficulty for each topic, topic by topic, minus jobs already run.

    Topic order means that if the cap is reached, the finished topics are complete.
    """
    jobs: list[Job] = []
    skipped = 0
    for topic in topics:
        for mode in MODES:
            for difficulty in DIFFICULTIES:
                job = Job(topic=topic, mode=mode, difficulty=difficulty)
                if job.key in attempted:
                    skipped += 1
                else:
                    jobs.append(job)
    return jobs, skipped


def estimate(jobs: Sequence[Job], settings: Settings) -> tuple[float, float]:
    """Typical and largest possible Anthropic cost of the jobs."""
    typical = sum(JOB_COST_TYPICAL[job.mode] for job in jobs)
    return typical, len(jobs) * job_cost_limit(settings)


def produce(job: Job, llm: LLMProvider, jev: JevClient | None, settings: Settings) -> ItemRecord:
    """Run one job through the agent and the publish gate."""
    lead = job.topic.lead_url
    if job.mode == "learn":
        result = run_learn(job.topic.name, job.difficulty, llm, settings, lead_url=lead)
    else:
        result = run_quiz(job.topic.name, job.difficulty, llm, settings, lead_url=lead)
    return verify_and_decide(result, llm, jev, settings)


class Budget:
    """A hard cap on Anthropic spend for one Curator run, safe across worker threads.

    Work may start only if the spend so far, plus what is reserved for work still running, plus
    its own reservation, stays within the cap. Reservations are the most the work can cost.
    """

    def __init__(self, cap_usd: float) -> None:
        self.cap_usd = cap_usd
        self._spent = 0.0
        self._reserved = 0.0
        self._lock = threading.Lock()

    @property
    def spent_usd(self) -> float:
        with self._lock:
            return self._spent

    def try_reserve(self, amount_usd: float) -> bool:
        with self._lock:
            if self._spent + self._reserved + amount_usd > self.cap_usd:
                return False
            self._reserved += amount_usd
            return True

    def settle(self, reserved_usd: float, actual_usd: float) -> None:
        with self._lock:
            self._reserved -= reserved_usd
            self._spent += actual_usd


JobOutcome = ItemRecord | Exception


def run_jobs(
    jobs: Sequence[Job],
    work: Callable[[Job], ItemRecord],
    on_done: Callable[[Job, JobOutcome], None],
    budget: Budget,
    workers: int,
    job_limit_usd: float,
) -> tuple[int, str | None]:
    """Run jobs in order on `workers` threads while the budget allows.

    `on_done` is called on this thread as each job finishes and must not raise (the Curator's
    never does: a result it cannot handle is written to disk). On Ctrl+C no new job starts, and the
    jobs already running (already paid for) are waited for and handed to `on_done`. Returns how
    many jobs ran and, if the run stopped early, why.
    """
    pending = deque(jobs)
    running: dict[Future[ItemRecord], Job] = {}
    finished = 0

    def collect(future: Future[ItemRecord]) -> None:
        nonlocal finished
        job = running.pop(future)
        finished += 1
        try:
            record = future.result()
        except Exception as error:  # a bug in one job must not lose the others
            budget.settle(job_limit_usd, job_limit_usd)  # unknown spend: assume the limit
            on_done(job, error)
            return
        budget.settle(job_limit_usd, record.anthropic_cost_usd)
        on_done(job, record)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        try:
            while pending or running:
                while pending and len(running) < workers and budget.try_reserve(job_limit_usd):
                    job = pending.popleft()
                    running[pool.submit(work, job)] = job
                if not running:
                    break  # nothing can start within the cap
                done, _ = wait(running, timeout=_POLL_SECONDS, return_when=FIRST_COMPLETED)
                for future in done:
                    collect(future)
        except KeyboardInterrupt:
            left = len(pending)
            pending.clear()
            for future in as_completed(list(running)):
                collect(future)
            return finished, (
                f"interrupted (Ctrl+C): {left} jobs not started; the running ones were saved"
            )
    if pending:
        return finished, (
            f"dollar cap of ${budget.cap_usd:.2f} reached; {len(pending)} jobs left for the "
            "next run"
        )
    return finished, None


@dataclass
class _Tally:
    published: int = 0
    review: int = 0
    discarded: int = 0
    no_item: int = 0
    typesafe_usd: float = 0.0


def set_aside(
    pending_dir: Path, path: Path, folder: str, reason: object, say: Callable[[str], None]
) -> None:
    """Move a pending payload out of the way, with the reason next to it, so it is kept for
    inspection but never blocks or repeats in later runs."""
    target = pending_dir / folder
    target.mkdir(parents=True, exist_ok=True)
    path.replace(target / path.name)
    (target / f"{path.stem}.reason.txt").write_text(str(reason), encoding="utf-8")
    say(f"  Set aside {path.name} in {target}: {reason}")


def flush_pending(store: Store, pending_dir: Path, say: Callable[[str], None]) -> int:
    """Send payloads left on disk by an earlier run that could not reach the bank. A file that
    cannot be read goes to `corrupt/`, and one the bank refuses goes to `rejected/`, so neither
    blocks or repeats in later runs. Free: no model calls."""
    sent = 0
    for path in sorted(pending_dir.glob("*.json")):
        try:
            payload = ItemPayload.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:  # pydantic's ValidationError is a ValueError
            set_aside(pending_dir, path, "corrupt", error, say)
            continue
        try:
            store.record_item(payload)
        except StoreError as error:
            if error.permanent:  # the bank refuses this payload: sending it again cannot help
                set_aside(pending_dir, path, "rejected", error, say)
            else:
                say(f"Still cannot store {path.name}: {error}")
            continue
        path.unlink()
        sent += 1
    if sent:
        say(f"Stored {sent} run(s) left over from an earlier Curator run.")
    return sent


class Curator:
    """Plans, runs and stores the jobs for one Curator invocation."""

    def __init__(
        self,
        store: Store,
        llm: LLMProvider,
        jev: JevClient | None,
        settings: Settings,
        pending_dir: Path,
        say: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.llm = llm
        self.jev = jev
        self.settings = settings
        self.pending_dir = pending_dir
        self._say = say or _print_now
        self._log: list[str] = []

    def say(self, message: str) -> None:
        self._log.append(message)
        with contextlib.suppress(OSError):  # a closed or broken console must never stop a run
            self._say(message)

    def _set_aside(self, path: Path, folder: str, reason: object) -> None:
        set_aside(self.pending_dir, path, folder, reason, self.say)

    def _rescue(self, job: Job, record: ItemRecord, error: Exception) -> None:
        """Last resort when a finished job's result cannot be handled: keep the raw record."""
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        target = self.pending_dir / "unsaved"
        name = f"{stamp}-{job.mode}-{job.difficulty}-{slugify(job.topic.name)}.json"
        try:
            target.mkdir(parents=True, exist_ok=True)
            (target / name).write_text(record.model_dump_json(), encoding="utf-8")
            kept = f"kept the record in {target / name}"
        except OSError as write_error:
            kept = f"and it could not be written to disk either ({write_error})"
        self.say(f"  {job.label}: could not be saved ({error!r}); {kept}")

    def plan(self, topics: Sequence[TopicRef]) -> tuple[list[Job], int]:
        attempted = self.store.attempted_jobs([topic.name for topic in topics])
        return plan_jobs(topics, attempted)

    def flush_pending(self) -> int:
        return flush_pending(self.store, self.pending_dir, self.say)

    def _keep(self, payload: ItemPayload, job: Job) -> Path | None:
        """Write a payload to the pending folder: to a temporary file first, then renamed, so a
        crash mid-write never leaves a half-written payload behind."""
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        name = f"{stamp}-{job.mode}-{job.difficulty}-{slugify(job.topic.name)}.json"
        path = self.pending_dir / name
        try:
            self.pending_dir.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(payload.model_dump_json(), encoding="utf-8")
            temporary.replace(path)
        except OSError as error:
            self.say(f"  Could not write {path}: {error}")
            return None
        return path

    def save(self, job: Job, record: ItemRecord, curator_run_id: int) -> bool:
        """Store one record; if that fails it stays on disk for the next run. True if stored."""
        payload = build_payload(record, job.topic, "curator", curator_run_id)
        path = self._keep(payload, job)
        try:
            ids = self.store.record_item(payload)
        except Exception as error:  # whatever went wrong, a paid run must not be lost silently
            if path is not None and isinstance(error, StoreError) and error.permanent:
                self._set_aside(path, "rejected", error)
                return False
            kept = f"kept {path} for the next run" if path else "it could not be kept on disk"
            self.say(f"  Could not store it ({error}); {kept}.")
            return False
        if ids.duplicate:
            self.say("  (the bank already had this run; not stored twice)")
        if path is not None:
            path.unlink(missing_ok=True)
        return True

    def run(
        self,
        trigger: CuratorTrigger,
        topics: Sequence[TopicRef],
        jobs: Sequence[Job],
        skipped: int,
        budget: Budget,
        workers: int,
    ) -> CuratorSummary:
        """Run the planned jobs, retire stale items and record the totals. The `curator_runs`
        row is always finished, even if the run stops on an error."""
        curator_run_id = self.store.start_curator_run(
            trigger, [topic.name for topic in topics], budget.cap_usd
        )
        self.say(
            f"Curator run {curator_run_id} ({trigger}): {len(jobs)} jobs, {skipped} already done, "
            f"cap ${budget.cap_usd:.2f}"
        )
        tally = _Tally()

        def on_done(job: Job, outcome: JobOutcome) -> None:
            if isinstance(outcome, Exception):
                tally.no_item += 1
                self.say(f"  {job.label}: crashed ({type(outcome).__name__}: {outcome})")
                return
            record = outcome
            try:
                tally.typesafe_usd += record.typesafe_cost_usd
                status = record.status if record.run.answer is not None else None
                if status == "published":
                    tally.published += 1
                elif status == "review":
                    tally.review += 1
                elif status == "discarded":
                    tally.discarded += 1
                else:
                    tally.no_item += 1
                self.say(
                    f"  {job.label}: {record.run.outcome} -> {status or 'no item'} "
                    f"(${record.anthropic_cost_usd:.3f}, {record.run.seconds:.0f}s, "
                    f"spent ${budget.spent_usd:.2f})"
                )
                self.save(job, record, curator_run_id)
            except Exception as error:  # one result that cannot be handled must not lose others
                self._rescue(job, record, error)

        def work(job: Job) -> ItemRecord:
            return produce(job, self.llm, self.jev, self.settings)

        ran, stopped, retired = 0, None, 0
        try:
            ran, stopped = run_jobs(
                jobs, work, on_done, budget, workers, job_cost_limit(self.settings)
            )
            if stopped:
                self.say(f"Stopped: {stopped}")
            retired = self.store.retire_stale()
            if retired:
                self.say(f"Retired {retired} item(s) from news topics past their date.")
        except Exception as error:
            stopped = f"crashed: {error!r}"
            self.say(f"Stopped: {stopped}")
            raise
        finally:
            summary = CuratorSummary(
                jobs_planned=len(jobs),
                jobs_skipped=skipped,
                jobs_run=ran,
                published=tally.published,
                review=tally.review,
                discarded=tally.discarded,
                no_item=tally.no_item,
                retired=retired,
                anthropic_cost_usd=round(budget.spent_usd, 6),
                typesafe_cost_usd=round(tally.typesafe_usd, 8),
                stopped_reason=stopped,
                log=tuple(self._log),
            )
            try:
                self.store.finish_curator_run(curator_run_id, summary)
            except StoreError as error:
                self.say(f"Could not record the run's totals: {error}")
        return summary
