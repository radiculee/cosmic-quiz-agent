import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, fetchItem, fetchTopics, streamResearch } from "./api";
import { AgentLog, type LogLine, type LogOutcome } from "./components/AgentLog";
import { BadgeChip } from "./components/BadgeChip";
import { DiceIcon } from "./components/DiceIcon";
import { LearnCard } from "./components/LearnCard";
import { ProfileStrip } from "./components/ProfileStrip";
import { QuizCard } from "./components/QuizCard";
import { RunHud } from "./components/RunHud";
import { RunResults } from "./components/RunResults";
import { SegmentedControl } from "./components/SegmentedControl";
import { TopicInput } from "./components/TopicInput";
import {
  type AnswerScore,
  answerInRun,
  type BadgeId,
  isRunFinished,
  planRun,
  type Run,
} from "./game";
import {
  afterAnswer,
  afterLearn,
  afterRun,
  browserStorage,
  loadProfile,
  type Profile,
  saveProfile,
} from "./profile";
import { randomTopic, suggest, topicStatus } from "./topics";
import {
  type BankTopic,
  DIFFICULTIES,
  type Difficulty,
  type LearnItem,
  MODES,
  type Mode,
  type QuizQuestion,
  type ResearchEvent,
} from "./types";
import { useRunClock } from "./useRunClock";

type TopicsState =
  | { kind: "loading" }
  | { kind: "failed" }
  | { kind: "loaded"; topics: BankTopic[] };

/** What the area under the controls shows. */
type View =
  | { kind: "idle" }
  | { kind: "loading"; label: string }
  | { kind: "failed"; message: string; retry: () => void }
  | { kind: "quiz"; question: QuizQuestion; number: number; revealToken?: string }
  | { kind: "learn"; item: LearnItem; newBadges: BadgeId[] }
  | {
      kind: "results";
      run: Run;
      elapsed: number;
      pointsBefore: number;
      pointsAfter: number;
      newBadges: BadgeId[];
    };

function useTopics(): [TopicsState, () => void] {
  const [state, setState] = useState<TopicsState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    fetchTopics(controller.signal)
      .then((topics) => setState({ kind: "loaded", topics }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error(error);
          setState({ kind: "failed" });
        }
      });
    return () => controller.abort();
  }, [attempt]);

  return [state, () => setAttempt((n) => n + 1)];
}

/** The saved profile, with an updater that also saves it and returns any new badges. */
function useProfile(): [Profile, (update: (profile: Profile) => [Profile, BadgeId[]]) => BadgeId[]] {
  const [profile, setProfile] = useState<Profile>(() => loadProfile(browserStorage()));
  const latest = useRef(profile);
  const update = useCallback((change: (profile: Profile) => [Profile, BadgeId[]]) => {
    const [next, earned] = change(latest.current);
    latest.current = next;
    setProfile(next);
    saveProfile(browserStorage(), next);
    return earned;
  }, []);
  return [profile, update];
}

/** A live run's agent log, kept on screen above the card it produced. */
interface LiveLog {
  /** A new log per run, so the panel (and its timer) starts afresh. */
  id: number;
  topic: string;
  mode: Mode;
  difficulty: Difficulty;
  lines: LogLine[];
  outcome: LogOutcome;
}

// The server cleans topics the same way (agent/topic_check.py); this only avoids a wasted call.
const MIN_TOPIC_CHARS = 2;
const MAX_TOPIC_CHARS = 80;

function loadError(error: unknown): string {
  if (error instanceof ApiError && error.status === 429) {
    return error.message;
  }
  return error instanceof ApiError && error.status === 404
    ? "There is no item for this topic at these settings yet."
    : "The question could not be loaded. Try again in a moment.";
}

export function App() {
  const [topicsState, retryTopics] = useTopics();
  const [profile, updateProfile] = useProfile();
  const clock = useRunClock();
  const [difficulty, setDifficulty] = useState<Difficulty>("easy");
  const [mode, setMode] = useState<Mode>("quiz");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<View>({ kind: "idle" });
  const [liveLog, setLiveLog] = useState<LiveLog | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const runRef = useRef<Run | null>(null);
  const runStart = useRef({ points: 0, badges: [] as BadgeId[] });
  const request = useRef<AbortController | null>(null);
  const viewRef = useRef<HTMLDivElement>(null);
  const topRef = useRef<HTMLElement>(null);

  const topics = useMemo(
    () => (topicsState.kind === "loaded" ? topicsState.topics : []),
    [topicsState],
  );
  const status = topicStatus(topics, query, mode, difficulty);
  const typed = query.trim().length;
  const canResearch =
    (status.kind === "unknown" || status.kind === "elsewhere") &&
    typed >= MIN_TOPIC_CHARS &&
    typed <= MAX_TOPIC_CHARS;
  const suggestions = useMemo(
    () => suggest(topics, query, mode, difficulty),
    [topics, query, mode, difficulty],
  );

  function replaceRun(next: Run | null) {
    runRef.current = next;
    setRun(next);
  }

  /** Start a request, cancelling any earlier one still in flight. */
  function newRequest(): AbortSignal {
    request.current?.abort();
    request.current = new AbortController();
    return request.current.signal;
  }

  // --- QUIZ runs ------------------------------------------------------------------------------

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
        setView({ kind: "quiz", question: item, number: current.results.length + 1 });
        clock.start();
      })
      .catch((error: unknown) => {
        if (!signal.aborted) {
          setView({ kind: "failed", message: loadError(error), retry: () => loadQuestion(current) });
        }
      });
  }

  function startRun(first: string, runDifficulty: Difficulty) {
    const planned = planRun(topics, runDifficulty, first, profile.played[runDifficulty]);
    runStart.current = { points: profile.points, badges: [] };
    clock.reset();
    replaceRun(planned);
    setQuery(first);
    loadQuestion(planned);
  }

  function onAnswered(question: QuizQuestion, correct: boolean, seconds: number): AnswerScore | null {
    const current = runRef.current;
    if (!current) {
      return null;
    }
    clock.pause();
    const { run: next, score } = answerInRun(current, question.id, question.topic, correct, seconds);
    replaceRun(next);
    const earned = updateProfile((p) =>
      afterAnswer(p, next.difficulty, question.id, question.topic, score, correct, next.streak),
    );
    runStart.current.badges.push(...earned);
    return score;
  }

  function nextQuestion() {
    const current = runRef.current;
    if (!current) {
      return;
    }
    if (!isRunFinished(current)) {
      loadQuestion(current);
      return;
    }
    const elapsed = clock.elapsed;
    const earned = updateProfile((p) => afterRun(p, current, elapsed / 1000));
    setView({
      kind: "results",
      run: current,
      elapsed,
      pointsBefore: runStart.current.points,
      pointsAfter: runStart.current.points + current.points,
      newBadges: [...runStart.current.badges, ...earned],
    });
  }

  function playAgain(previous: Run) {
    const first = randomTopic(
      topics,
      "quiz",
      previous.difficulty,
      "",
      Math.random,
      profile.played[previous.difficulty],
    );
    if (first) {
      startRun(first.name, previous.difficulty);
    }
  }

  // --- LEARN ----------------------------------------------------------------------------------

  function loadLearn(topic: string, learnDifficulty: Difficulty = difficulty) {
    replaceRun(null);
    clock.reset();
    const signal = newRequest();
    setQuery(topic);
    setView({ kind: "loading", label: `Loading ${topic}...` });
    fetchItem(topic, "learn", learnDifficulty, profile.seenItems, signal)
      .then((item) => {
        if (item.mode !== "learn") {
          throw new ApiError("expected a LEARN item");
        }
        const earned = updateProfile((p) => afterLearn(p, item.id, item.topic));
        setView({ kind: "learn", item, newBadges: earned });
      })
      .catch((error: unknown) => {
        if (!signal.aborted) {
          setView({
            kind: "failed",
            message: loadError(error),
            retry: () => loadLearn(topic, learnDifficulty),
          });
        }
      });
  }

  // --- Custom topics, researched live -------------------------------------------------------

  /** A live quiz question becomes question 1 of a run; the rest come from the bank. */
  function startLiveRun(question: QuizQuestion, revealToken: string) {
    const played = profile.played[question.difficulty];
    const planned = planRun(topics, question.difficulty, question.topic, played);
    runStart.current = { points: profile.points, badges: [] };
    clock.reset();
    replaceRun(planned);
    setView({ kind: "quiz", question, number: 1, revealToken });
    clock.start();
  }

  /** No live result: carry on from the bank at the same settings. */
  function playFromBank(runMode: Mode, runDifficulty: Difficulty, topic?: string) {
    const avoid = runMode === "quiz" ? profile.played[runDifficulty] : profile.learned;
    const name = topic ?? randomTopic(topics, runMode, runDifficulty, "", Math.random, avoid)?.name;
    if (!name) {
      setView({ kind: "idle" });
    } else if (runMode === "quiz") {
      startRun(name, runDifficulty);
    } else {
      loadLearn(name, runDifficulty);
    }
  }

  function research(topic: string) {
    const runMode = mode;
    const runDifficulty = difficulty;
    replaceRun(null);
    clock.reset();
    const signal = newRequest();
    setView({ kind: "idle" });
    setLiveLog({
      id: Date.now(),
      topic,
      mode: runMode,
      difficulty: runDifficulty,
      lines: [],
      outcome: { kind: "running" },
    });
    viewRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    let ended = false;
    const finish = (outcome: LogOutcome) => {
      ended = true;
      setLiveLog((log) => (log ? { ...log, outcome } : log));
    };
    const fallBack = (message: string, bankTopic?: string) => {
      finish({ kind: "fallback", message });
      playFromBank(runMode, runDifficulty, bankTopic);
    };

    const onEvent = (event: ResearchEvent) => {
      switch (event.type) {
        case "log": {
          const line: LogLine = {
            label: event.label,
            detail: event.detail,
            tone: event.tone,
            verdict: event.verdict,
          };
          setLiveLog((log) => (log ? { ...log, lines: [...log.lines, line] } : log));
          break;
        }
        case "rejected":
          finish({ kind: "rejected", message: event.message });
          break;
        case "fallback":
          fallBack(event.message, event.topic ?? undefined);
          break;
        case "error":
          fallBack(`${event.message} Here is a question from the bank.`);
          break;
        case "result": {
          const item = event.item;
          finish({ kind: item.status === "review" ? "review" : "published" });
          if (item.mode === "quiz" && event.reveal_token) {
            startLiveRun(item, event.reveal_token);
          } else if (item.mode === "learn") {
            const earned = updateProfile((p) => afterLearn(p, item.id, item.topic));
            setView({ kind: "learn", item, newBadges: earned });
          }
          break;
        }
      }
    };

    streamResearch(topic, runMode, runDifficulty, onEvent, signal)
      .then(() => {
        if (!ended && !signal.aborted) {
          fallBack("The live run ended without a result. Here is a question from the bank.");
        }
      })
      .catch((error: unknown) => {
        if (signal.aborted || ended) {
          return;
        }
        if (error instanceof ApiError && (error.status === 400 || error.status === 429)) {
          finish({ kind: "rejected", message: error.message });
          return;
        }
        fallBack("Live research is not available right now. Here is a question from the bank.");
      });
  }

  function anotherTopic() {
    const topic = randomTopic(topics, "learn", difficulty, query, Math.random, profile.learned);
    if (topic) {
      loadLearn(topic.name);
    }
  }

  // --- Controls -------------------------------------------------------------------------------

  function start() {
    if (canResearch) {
      research(query.trim());
      return;
    }
    if (status.kind !== "ready") {
      return;
    }
    setLiveLog(null);
    if (mode === "quiz") {
      startRun(status.topic.name, difficulty);
    } else {
      loadLearn(status.topic.name);
    }
  }

  function pickRandom() {
    const avoid = mode === "quiz" ? profile.played[difficulty] : profile.learned;
    const topic = randomTopic(topics, mode, difficulty, query, Math.random, avoid);
    if (topic) {
      setQuery(topic.name);
    }
  }

  function changeSettings() {
    replaceRun(null);
    clock.reset();
    setLiveLog(null);
    setView({ kind: "idle" });
    topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Bring each new card into view.
  const viewKey =
    view.kind === "quiz"
      ? `quiz-${view.question.id}`
      : view.kind === "learn"
        ? `learn-${view.item.id}`
        : view.kind;
  useEffect(() => {
    if (viewKey.startsWith("quiz-") || viewKey.startsWith("learn-") || viewKey === "results") {
      viewRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [viewKey]);

  const lastQuestion = run !== null && run.results.length >= run.topics.length;
  const researching = liveLog?.outcome.kind === "running";

  return (
    <main
      ref={topRef}
      className="mx-auto flex min-h-dvh max-w-3xl flex-col items-center px-4 py-16 sm:py-24"
    >
      <h1 className="text-center font-heading text-5xl font-bold uppercase tracking-tight sm:text-7xl">
        Cosmic Quiz
      </h1>
      <p className="mt-6 max-w-xl text-center text-lg leading-relaxed text-ink/90">
        An AI agent reads NASA, ESA and Wikipedia, writes the questions, and checks every answer
        against the pages it read.
      </p>

      <div className="mt-10 flex flex-col items-center gap-5">
        <SegmentedControl
          label="Difficulty"
          options={DIFFICULTIES}
          value={difficulty}
          onChange={setDifficulty}
        />
        <SegmentedControl label="Mode" options={MODES} value={mode} onChange={setMode} />
      </div>

      <div className="mt-10 w-full max-w-xl">
        <TopicInput
          value={query}
          suggestions={suggestions}
          disabled={topicsState.kind !== "loaded"}
          onChange={setQuery}
          onSubmit={start}
        />
        <Hint
          state={topicsState}
          status={status}
          mode={mode}
          difficulty={difficulty}
          tooLong={typed > MAX_TOPIC_CHARS}
          onRetry={retryTopics}
        />
      </div>

      <div className="mt-6 flex items-center gap-4">
        <button
          type="button"
          onClick={pickRandom}
          disabled={topics.length === 0}
          className="flex items-center gap-3 rounded-lg border border-white/10 bg-surface px-5 py-4 font-pixel text-[9px] uppercase text-ink transition-colors hover:border-white/25 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:opacity-50"
        >
          <DiceIcon />
          Random topic
        </button>
        <button
          type="button"
          onClick={start}
          disabled={
            (status.kind !== "ready" && !canResearch) || view.kind === "loading" || researching
          }
          className="rounded-lg bg-teal px-12 py-4 font-pixel text-[11px] uppercase text-void transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:opacity-40"
        >
          Go
        </button>
      </div>
      {mode === "quiz" && (
        <p className="mt-3 text-xs text-slate">
          GO starts a run of up to 10 questions on different topics, against the clock.
        </p>
      )}

      <div className="mt-12 w-full max-w-xl">
        <ProfileStrip profile={profile} />
      </div>

      <div ref={viewRef} className="mt-10 w-full scroll-mt-6" aria-live="polite">
        {liveLog && (
          <div className="mb-6">
            <AgentLog
              key={liveLog.id}
              topic={liveLog.topic}
              mode={liveLog.mode}
              difficulty={liveLog.difficulty}
              lines={liveLog.lines}
              outcome={liveLog.outcome}
            />
          </div>
        )}
        {view.kind === "loading" && (
          <p className="text-center text-sm text-slate">{view.label}</p>
        )}
        {view.kind === "failed" && (
          <p role="alert" className="text-center text-sm text-slate">
            {view.message}{" "}
            <button
              type="button"
              onClick={view.retry}
              className="text-teal underline underline-offset-4"
            >
              Try again
            </button>
          </p>
        )}
        {view.kind === "quiz" && run && (
          <>
            <RunHud
              run={run}
              question={view.number}
              elapsed={clock.elapsed}
              running={clock.running}
            />
            <QuizCard
              question={view.question}
              revealToken={view.revealToken}
              onAnswered={(correct, seconds) => onAnswered(view.question, correct, seconds)}
              nextLabel={lastQuestion ? "See results" : "Next question"}
              onNext={nextQuestion}
            />
          </>
        )}
        {view.kind === "learn" && (
          <>
            {view.newBadges.length > 0 && (
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <span className="font-pixel text-[8px] uppercase text-slate">New badge</span>
                <ul className="flex gap-2">
                  {view.newBadges.map((id) => (
                    <BadgeChip key={id} id={id} earned />
                  ))}
                </ul>
              </div>
            )}
            <LearnCard item={view.item} onNext={anotherTopic} />
          </>
        )}
        {view.kind === "results" && (
          <RunResults
            run={view.run}
            elapsed={view.elapsed}
            pointsBefore={view.pointsBefore}
            pointsAfter={view.pointsAfter}
            newBadges={view.newBadges}
            onPlayAgain={() => playAgain(view.run)}
            onChangeSettings={changeSettings}
          />
        )}
      </div>

      {topicsState.kind === "loaded" && (
        <p className="mt-auto pt-16 text-center text-xs text-slate">
          {topicsState.topics.length} topics in the bank. Every answer is checked against the pages
          the agent read.
        </p>
      )}
    </main>
  );
}

interface HintProps {
  state: TopicsState;
  status: ReturnType<typeof topicStatus>;
  mode: Mode;
  difficulty: Difficulty;
  tooLong: boolean;
  onRetry: () => void;
}

/** One line under the topic box explaining what GO will do, or why it is not available. */
function Hint({ state, status, mode, difficulty, tooLong, onRetry }: HintProps) {
  const base = "mt-3 min-h-5 text-sm";
  if (state.kind === "loading") {
    return <p className={`${base} text-slate`}>Loading topics...</p>;
  }
  if (state.kind === "failed") {
    return (
      <p className={`${base} text-slate`}>
        Could not load the topics.{" "}
        <button type="button" onClick={onRetry} className="text-teal underline underline-offset-4">
          Try again
        </button>
      </p>
    );
  }
  if (tooLong) {
    return <p className={`${base} text-rust`}>Keep the topic under 80 characters.</p>;
  }
  if (status.kind === "unknown") {
    return (
      <p className={`${base} text-slate`}>
        Not in the bank yet. GO researches it live: the agent reads and checks its sources in
        about 20 seconds.
      </p>
    );
  }
  if (status.kind === "elsewhere") {
    const others = status.difficulties.map((d) => d.toUpperCase()).join(" or ");
    return (
      <p className={`${base} text-slate`}>
        {status.topic.name} has no {mode.toUpperCase()} item at {difficulty.toUpperCase()} yet.
        GO researches one live{others ? `, or try ${others}` : ""}.
      </p>
    );
  }
  return <p className={base} />;
}
