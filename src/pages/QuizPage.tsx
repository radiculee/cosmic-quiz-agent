import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { ApiError, fetchItem } from "../api";
import { ProfileStrip } from "../components/ProfileStrip";
import { QuizCard } from "../components/QuizCard";
import { RunHud } from "../components/RunHud";
import { RunResults } from "../components/RunResults";
import { Dropdown } from "../components/Dropdown";
import { SegmentedControl } from "../components/SegmentedControl";
import {
  type AnswerScore,
  answerInRun,
  availableLength,
  isRunFinished,
  lengthNote,
  planRun,
  quizTopicCount,
  RUN_LENGTHS,
  type Run,
  type RunLength,
} from "../game";
import { afterAnswer, afterRun } from "../profile";
import { usePageTitle } from "../router";
import type { Award } from "../trophies";
import { DIFFICULTIES, type Difficulty, type QuizQuestion } from "../types";
import { useRunClock } from "../useRunClock";
import { loadedTopics } from "../useTopics";
import {
  LoadFailed,
  loadError,
  PageHeading,
  type PageProps,
  PRIMARY_BUTTON,
  TopicsNotice,
} from "./common";

/** What the page shows below its heading. */
type View =
  | { kind: "setup" }
  | { kind: "loading"; label: string }
  | { kind: "failed"; message: string; retry: () => void }
  | { kind: "question"; question: QuizQuestion; number: number }
  | {
      kind: "results";
      run: Run;
      elapsed: number;
      pointsBefore: number;
      pointsAfter: number;
      awards: Award[];
    };

/** A label beside a control, for sighted players; the control carries its own accessible name. */
function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 sm:flex-row sm:gap-4">
      <span aria-hidden="true" className="on-scene-muted font-pixel text-[8px] uppercase sm:w-24 sm:text-right">
        {label}
      </span>
      {children}
    </div>
  );
}

/**
 * QUIZ: pick a difficulty and a length, then play a run against the clock, every question on a
 * different random topic (unplayed ones first). A length is offered only when the bank has that
 * many topics at the difficulty, so a run never repeats a topic and never costs anything.
 */
export function QuizPage({
  topicsState,
  retryTopics,
  profile,
  updateProfile,
  celebrate,
  difficulty,
  setDifficulty,
}: PageProps) {
  usePageTitle("Quiz");
  const noteId = useId();
  const clock = useRunClock();
  const topics = loadedTopics(topicsState);
  const [wanted, setWanted] = useState<RunLength>(10);
  // The length of the run being played, for Play again.
  const [runLength, setRunLength] = useState<RunLength>(10);
  const [view, setView] = useState<View>({ kind: "setup" });
  const [run, setRun] = useState<Run | null>(null);
  const runRef = useRef<Run | null>(null);
  const runStart = useRef<{ points: number; awards: Award[] }>({ points: 0, awards: [] });
  const request = useRef<AbortController | null>(null);
  const viewRef = useRef<HTMLDivElement>(null);

  const count = quizTopicCount(topics, difficulty);
  const length = availableLength(count, wanted);
  const note = topicsState.kind === "loaded" ? lengthNote(difficulty, count) : null;

  // Leaving the page drops the run (there is no resume) and any question still loading.
  useEffect(() => () => request.current?.abort(), []);

  function replaceRun(next: Run | null) {
    runRef.current = next;
    setRun(next);
  }

  function newRequest(): AbortSignal {
    request.current?.abort();
    request.current = new AbortController();
    return request.current.signal;
  }

  function loadQuestion(current: Run) {
    const topic = current.topics[current.results.length];
    if (topic === undefined) {
      return;
    }
    const signal = newRequest();
    setView({ kind: "loading", label: `Loading ${topic}...` });
    fetchItem(topic, "quiz", current.difficulty, profile.seenItems, signal)
      .then((item) => {
        if (item.mode !== "quiz") {
          throw new ApiError("expected a quiz item");
        }
        setView({ kind: "question", question: item, number: current.results.length + 1 });
        clock.start();
      })
      .catch((error: unknown) => {
        if (!signal.aborted) {
          setView({ kind: "failed", message: loadError(error), retry: () => loadQuestion(current) });
        }
      });
  }

  function start(questions: RunLength, runDifficulty: Difficulty) {
    const planned = planRun(topics, runDifficulty, questions, profile.played[runDifficulty]);
    runStart.current = { points: profile.points, awards: [] };
    clock.reset();
    setRunLength(questions);
    replaceRun(planned);
    loadQuestion(planned);
  }

  /** Called once the answer is revealed: the clock is paused first, then any trophies pop up. */
  function onAnswered(question: QuizQuestion, correct: boolean, seconds: number): AnswerScore | null {
    const current = runRef.current;
    if (!current) {
      return null;
    }
    const counted = clock.pause();
    const { run: next, score } = answerInRun(current, question.id, question.topic, correct, seconds);
    replaceRun(next);
    const awards = updateProfile((p) =>
      afterAnswer(p, next.difficulty, question.id, question.topic, score, correct, next.streak),
    );
    if (isRunFinished(next)) {
      awards.push(...updateProfile((p) => afterRun(p, next, counted / 1000)));
    }
    runStart.current.awards.push(...awards);
    celebrate(awards);
    return score;
  }

  function showResults(current: Run) {
    request.current?.abort();
    const elapsed = clock.pause();
    setView({
      kind: "results",
      run: current,
      elapsed,
      pointsBefore: runStart.current.points,
      pointsAfter: runStart.current.points + current.points,
      awards: [...runStart.current.awards],
    });
  }

  function nextQuestion() {
    const current = runRef.current;
    if (!current) {
      return;
    }
    if (isRunFinished(current)) {
      showResults(current);
    } else {
      loadQuestion(current);
    }
  }

  /** End early: results for the questions answered so far. Their points are already saved. */
  function endRun() {
    const current = runRef.current;
    if (current) {
      showResults(current);
    }
  }

  function changeSettings() {
    request.current?.abort();
    replaceRun(null);
    clock.reset();
    setView({ kind: "setup" });
  }

  // Bring each new question and the results into view.
  const viewKey = view.kind === "question" ? `question-${view.question.id}` : view.kind;
  useEffect(() => {
    if (viewKey.startsWith("question-") || viewKey === "results") {
      viewRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [viewKey]);

  if (view.kind === "setup" || run === null) {
    return (
      <div className="flex flex-col items-center">
        <PageHeading title="Quiz">
          Every question is on a different topic, unplayed ones first. The clock runs only while a
          question waits for an answer.
        </PageHeading>

        <div className="mt-10 flex flex-col items-center gap-5">
          <Row label="Difficulty">
            <Dropdown
              label="Difficulty"
              options={DIFFICULTIES}
              value={difficulty}
              onChange={setDifficulty}
            />
          </Row>
          <Row label="Questions">
            <SegmentedControl
              label="Questions"
              options={RUN_LENGTHS}
              value={length ?? wanted}
              onChange={setWanted}
              disabled={RUN_LENGTHS.filter((option) => option > count)}
              describedBy={note ? noteId : undefined}
            />
          </Row>
          {note && (
            <p id={noteId} className="scene-note max-w-md text-center text-sm">
              {note}
            </p>
          )}
        </div>

        <div className="mt-8">
          <TopicsNotice state={topicsState} onRetry={retryTopics} />
        </div>
        <button
          type="button"
          onClick={() => length !== null && start(length, difficulty)}
          disabled={length === null}
          className={`${PRIMARY_BUTTON} mt-2 px-14 py-4 text-[11px]`}
        >
          Start
        </button>
        <p className="scene-note mt-4 max-w-md text-center text-xs leading-relaxed">
          EASY 100, MEDIUM 200, HARD 300 points a correct answer. x1.5 from 3 in a row, x2 from 5,
          and +25% for answering within 15 seconds.
        </p>

        <div className="pixel-border mt-14 w-full max-w-xl rounded-sm bg-surface px-5 py-5">
          <ProfileStrip profile={profile} />
        </div>
      </div>
    );
  }

  const answeredAll = run.results.length >= run.topics.length;
  return (
    <div ref={viewRef} className="scroll-mt-6 pt-6" aria-live="polite">
      <h1 className="sr-only">Quiz run, {run.difficulty}</h1>
      {view.kind !== "results" && (
        <>
          <RunHud
            run={run}
            question={view.kind === "question" ? view.number : run.results.length + 1}
            elapsed={clock.elapsed}
            running={clock.running}
          />
          <div className="-mt-2 mb-4 flex justify-end">
            <button
              type="button"
              onClick={endRun}
              className="on-scene-muted font-pixel text-[8px] uppercase underline-offset-4 hover:text-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal"
            >
              End run
            </button>
          </div>
        </>
      )}
      {view.kind === "loading" && <p className="scene-note mx-auto text-center text-sm">{view.label}</p>}
      {view.kind === "failed" && <LoadFailed message={view.message} onRetry={view.retry} />}
      {view.kind === "question" && (
        <QuizCard
          question={view.question}
          onAnswered={(correct, seconds) => onAnswered(view.question, correct, seconds)}
          nextLabel={answeredAll ? "See results" : "Next question"}
          onNext={nextQuestion}
        />
      )}
      {view.kind === "results" && (
        <RunResults
          run={view.run}
          elapsed={view.elapsed}
          pointsBefore={view.pointsBefore}
          pointsAfter={view.pointsAfter}
          awards={view.awards}
          onPlayAgain={() => start(runLength, view.run.difficulty)}
          onChangeSettings={changeSettings}
        />
      )}
    </div>
  );
}
