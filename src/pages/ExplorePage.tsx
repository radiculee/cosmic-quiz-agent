import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, fetchItem, streamResearch } from "../api";
import { AgentLog, type LogLine, type LogOutcome } from "../components/AgentLog";
import { LearnCard } from "../components/LearnCard";
import { Link } from "../components/Link";
import { QuizCard } from "../components/QuizCard";
import { SegmentedControl } from "../components/SegmentedControl";
import { TopicInput } from "../components/TopicInput";
import { type AnswerScore, scoreAnswer } from "../game";
import { afterAnswer, afterLearn, afterLiveRun } from "../profile";
import { GLOBAL_CAP_NOTICE, quotaLine } from "../quota";
import { learnTopicPath, navigate, PATHS, useLocation, usePageTitle } from "../router";
import { suggest, type TopicStatus, topicStatus } from "../topics";
import type { Award } from "../trophies";
import {
  DIFFICULTIES,
  type Difficulty,
  type LearnItem,
  MODES,
  type Mode,
  type QuizQuestion,
  type ResearchEvent,
} from "../types";
import { useQuota } from "../useQuota";
import { loadedTopics, type TopicsState } from "../useTopics";
import {
  LoadFailed,
  loadError,
  MAX_TOPIC_CHARS,
  MIN_TOPIC_CHARS,
  PageHeading,
  type PageProps,
  PRIMARY_BUTTON,
} from "./common";

/** What shows under the form. */
type View =
  | { kind: "idle" }
  | { kind: "loading"; label: string }
  | { kind: "failed"; message: string; retry: () => void }
  | { kind: "learn"; item: LearnItem }
  | { kind: "quiz"; question: QuizQuestion; revealToken?: string | undefined }
  | { kind: "fallback"; topic: string | null; mode: Mode; difficulty: Difficulty };

/** A live run's agent log, kept on screen above what it produced. */
interface LiveLog {
  /** A new log per run, so the panel (and its timer) starts afresh. */
  id: number;
  topic: string;
  mode: Mode;
  difficulty: Difficulty;
  lines: LogLine[];
  outcome: LogOutcome;
}

function isMode(value: string | null): value is Mode {
  return (MODES as readonly (string | null)[]).includes(value);
}

function isDifficulty(value: string | null): value is Difficulty {
  return (DIFFICULTIES as readonly (string | null)[]).includes(value);
}

/**
 * The web page: a topic not in the bank is researched live by the agent, with its steps
 * streamed as a log, and the result (one explanation or one question) shown here with its
 * sources and source check. Each visitor has 3 live runs a day. A topic the bank already has is
 * free: LEARN links to it, and QUIZ plays its question here without a live run.
 *
 * The address can carry the form's values (`?topic=...&mode=...&difficulty=...`, from the Learn
 * page's "research it live" link); it only fills the form, so a link can never spend a run.
 */
export function ExplorePage({
  topicsState,
  retryTopics,
  profile,
  updateProfile,
  celebrate,
  difficulty,
  setDifficulty,
}: PageProps) {
  usePageTitle("Explore");
  const location = useLocation();
  const [initial] = useState(() => {
    const params = location.searchParams;
    const mode = params.get("mode");
    const level = params.get("difficulty");
    return {
      // As long as the server accepts (api/research.py); the hint asks for less than that.
      topic: (params.get("topic") ?? "").slice(0, 200),
      mode: isMode(mode) ? mode : "learn",
      difficulty: isDifficulty(level) ? level : null,
    };
  });
  const [query, setQuery] = useState(initial.topic);
  const [mode, setMode] = useState<Mode>(initial.mode);
  const [view, setView] = useState<View>({ kind: "idle" });
  const [liveLog, setLiveLog] = useState<LiveLog | null>(null);
  const [quotaState, refreshQuota] = useQuota();
  const request = useRef<AbortController | null>(null);
  const viewRef = useRef<HTMLDivElement>(null);
  // A live question's Web researcher trophy waits until it is answered, so no pop-up covers an
  // unanswered question.
  const deferred = useRef<Award[]>([]);

  useEffect(() => {
    if (initial.difficulty) {
      setDifficulty(initial.difficulty);
    }
  }, [initial.difficulty, setDifficulty]);

  // Leaving the page closes the stream (the server still finishes and stores a started run) and
  // shows anything still held back.
  useEffect(
    () => () => {
      request.current?.abort();
      if (deferred.current.length > 0) {
        celebrate(deferred.current);
        deferred.current = [];
      }
    },
    [celebrate],
  );

  const topics = loadedTopics(topicsState);
  const status = topicStatus(topics, query, mode, difficulty);
  const suggestions = useMemo(
    () => suggest(topics, query, mode, difficulty),
    [topics, query, mode, difficulty],
  );
  const quota = quotaState.kind === "loaded" ? quotaState.quota : null;
  const typed = query.trim().length;
  const wantsLive =
    (status.kind === "unknown" || status.kind === "elsewhere") &&
    typed >= MIN_TOPIC_CHARS &&
    typed <= MAX_TOPIC_CHARS;
  // If the quota cannot be read, the server still enforces every limit when a run starts.
  const liveAllowed = quota === null || (quota.remaining > 0 && quota.global_open);
  const busy = view.kind === "loading" || liveLog?.outcome.kind === "running";
  const canGo = !busy && (status.kind === "ready" || (wantsLive && liveAllowed));

  function newRequest(): AbortSignal {
    request.current?.abort();
    request.current = new AbortController();
    return request.current.signal;
  }

  function scrollToResult() {
    viewRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /** A topic the bank has at QUIZ and this difficulty: play its question here, free. */
  function playBankQuestion(topic: string, level: Difficulty) {
    const signal = newRequest();
    setLiveLog(null);
    deferred.current = [];
    setView({ kind: "loading", label: `Loading ${topic}...` });
    fetchItem(topic, "quiz", level, profile.seenItems, signal)
      .then((item) => {
        if (item.mode !== "quiz") {
          throw new ApiError("expected a quiz item");
        }
        setView({ kind: "quiz", question: item });
        scrollToResult();
      })
      .catch((error: unknown) => {
        if (!signal.aborted) {
          setView({
            kind: "failed",
            message: loadError(error),
            retry: () => playBankQuestion(topic, level),
          });
        }
      });
  }

  function research(topic: string) {
    const runMode = mode;
    const runDifficulty = difficulty;
    const signal = newRequest();
    deferred.current = [];
    setView({ kind: "idle" });
    setLiveLog({
      id: Date.now(),
      topic,
      mode: runMode,
      difficulty: runDifficulty,
      lines: [],
      outcome: { kind: "running" },
    });
    scrollToResult();
    let ended = false;
    const finish = (outcome: LogOutcome) => {
      ended = true;
      setLiveLog((log) => (log ? { ...log, outcome } : log));
    };
    const fallBack = (message: string, bankTopic: string | null = null) => {
      finish({ kind: "fallback", message });
      setView({ kind: "fallback", topic: bankTopic, mode: runMode, difficulty: runDifficulty });
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
          fallBack(event.message, event.topic);
          break;
        case "error":
          fallBack(event.message);
          break;
        case "result": {
          const item = event.item;
          finish({ kind: item.status === "review" ? "review" : "published" });
          const live = updateProfile(afterLiveRun);
          if (item.mode === "learn") {
            setView({ kind: "learn", item });
            celebrate([...live, ...updateProfile((p) => afterLearn(p, item.id, item.topic))]);
          } else if (event.reveal_token) {
            deferred.current = live;
            setView({ kind: "quiz", question: item, revealToken: event.reveal_token });
          } else {
            celebrate(live);
          }
          break;
        }
      }
    };

    streamResearch(topic, runMode, runDifficulty, onEvent, signal)
      .then(() => {
        if (!ended && !signal.aborted) {
          fallBack("The live run ended without a result.");
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
        fallBack("Live research is not available right now.");
      })
      .finally(() => {
        if (!signal.aborted) {
          refreshQuota();
        }
      });
  }

  function go() {
    if (!canGo) {
      return;
    }
    if (status.kind === "ready") {
      if (mode === "learn") {
        navigate(learnTopicPath(status.topic.name));
      } else {
        playBankQuestion(status.topic.name, difficulty);
      }
      return;
    }
    research(query.trim());
  }

  /** One question on its own: scored like a quiz answer, with no streak and no run. */
  function onAnswered(question: QuizQuestion, correct: boolean, seconds: number): AnswerScore {
    const streak = correct ? 1 : 0;
    const score = scoreAnswer(question.difficulty, correct, streak, seconds);
    const awards = updateProfile((p) =>
      afterAnswer(p, question.difficulty, question.id, question.topic, score, correct, streak),
    );
    celebrate([...deferred.current, ...awards]);
    deferred.current = [];
    return score;
  }

  function startOver() {
    request.current?.abort();
    setView({ kind: "idle" });
    setLiveLog(null);
    setQuery("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="flex flex-col items-center">
      <PageHeading title="Explore">
        Research a topic that is not in the bank yet. The agent reads NASA, ESA, arXiv and
        Wikipedia live, then checks what it wrote against the pages it read.
      </PageHeading>

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
          placeholder="A new topic, e.g. Pulsars"
          onChange={setQuery}
          onSubmit={go}
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

      <button
        type="button"
        onClick={go}
        disabled={!canGo}
        className={`${PRIMARY_BUTTON} mt-6 px-12 py-4 text-[11px]`}
      >
        Go
      </button>
      {quota && (
        <p role="status" className="mt-4 max-w-md text-center text-sm text-slate">
          {quota.global_open ? quotaLine(quota) : GLOBAL_CAP_NOTICE}
        </p>
      )}

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
        {view.kind === "loading" && <p className="text-center text-sm text-slate">{view.label}</p>}
        {view.kind === "failed" && <LoadFailed message={view.message} onRetry={view.retry} />}
        {view.kind === "learn" && (
          <LearnCard item={view.item} onNext={startOver} nextLabel="Another new topic" />
        )}
        {view.kind === "quiz" && (
          <QuizCard
            question={view.question}
            revealToken={view.revealToken}
            onAnswered={(correct, seconds) => onAnswered(view.question, correct, seconds)}
            nextLabel="Another new topic"
            onNext={startOver}
          />
        )}
        {view.kind === "fallback" && (
          <Fallback
            topic={view.topic}
            mode={view.mode}
            onPlay={() => view.topic && playBankQuestion(view.topic, view.difficulty)}
          />
        )}
      </div>
    </div>
  );
}

/** No live result: the bank is free, so offer it. */
function Fallback({
  topic,
  mode,
  onPlay,
}: {
  topic: string | null;
  mode: Mode;
  onPlay: () => void;
}) {
  const link = "text-teal underline underline-offset-4 hover:text-ink";
  if (topic && mode === "learn") {
    return (
      <p className="text-center text-sm text-ink/90">
        <Link to={learnTopicPath(topic)} className={link}>
          Read {topic} in Learn
        </Link>
        , free.
      </p>
    );
  }
  if (topic) {
    return (
      <p className="text-center">
        <button type="button" onClick={onPlay} className={`${PRIMARY_BUTTON} px-6 py-3.5 text-[10px]`}>
          Play its question, free
        </button>
      </p>
    );
  }
  return (
    <p className="text-center text-sm text-ink/90">
      <Link to={PATHS.learn} className={link}>
        Browse the topics in Learn
      </Link>{" "}
      or{" "}
      <Link to={PATHS.quiz} className={link}>
        play a quiz run
      </Link>
      .
    </p>
  );
}

interface HintProps {
  state: TopicsState;
  status: TopicStatus;
  mode: Mode;
  difficulty: Difficulty;
  tooLong: boolean;
  onRetry: () => void;
}

/** One line under the topic box: what GO will do, or why it is not available. */
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
    return <p className={`${base} text-rust`}>Keep the topic under {MAX_TOPIC_CHARS} characters.</p>;
  }
  switch (status.kind) {
    case "empty":
      return (
        <p className={`${base} text-slate`}>
          Any astronomy or space topic. The agent researches it in about 20 seconds.
        </p>
      );
    case "unknown":
      return (
        <p className={`${base} text-slate`}>
          Not in the bank yet. GO researches it live: the agent reads and checks its sources in
          about 20 seconds.
        </p>
      );
    case "elsewhere": {
      const others = status.difficulties.map((level) => level.toUpperCase()).join(" or ");
      return (
        <p className={`${base} text-slate`}>
          {status.topic.name} has no {mode.toUpperCase()} item at {difficulty.toUpperCase()} yet.
          GO researches one live{others ? `, or try ${others}` : ""}.
        </p>
      );
    }
    case "ready":
      return mode === "learn" ? (
        <p className={`${base} text-slate`}>
          Already in the bank, so it is free:{" "}
          <Link
            to={learnTopicPath(status.topic.name)}
            className="text-teal underline underline-offset-4 hover:text-ink"
          >
            read it in Learn
          </Link>
          .
        </p>
      ) : (
        <p className={`${base} text-slate`}>
          Already in the bank, so GO plays its question here for free, without a live run.
        </p>
      );
  }
}
