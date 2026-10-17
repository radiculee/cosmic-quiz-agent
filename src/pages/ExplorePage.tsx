import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, fetchItem, streamResearch } from "../api";
import { AgentLog, type LogLine, type LogOutcome } from "../components/AgentLog";
import { Dropdown } from "../components/Dropdown";
import { LearnCard } from "../components/LearnCard";
import { Link } from "../components/Link";
import { QuizCard } from "../components/QuizCard";
import { TopicInput } from "../components/TopicInput";
import { type AnswerScore, scoreAnswer } from "../game";
import { isPlainObject } from "../guards";
import { afterAnswer, afterLearn, afterLiveRun } from "../profile";
import { GLOBAL_CAP_NOTICE, quotaLine } from "../quota";
import { navigate, PATHS, useLocation, usePageTitle } from "../router";
import { startsOffScreen } from "../scroll";
import {
  ended,
  type ExplanationLock,
  explanationLock,
  explanationSlot,
  fromPlan,
  itemLabel,
  madeAnything,
  measured,
  missed,
  nextOpen,
  questionSlots,
  resolved,
  type Search,
  type Slot,
  started,
  summarize,
  summaryLine,
} from "../search";
import { type SearchStatus, searchStatus, suggestAny } from "../topics";
import type { Award } from "../trophies";
import {
  DIFFICULTIES,
  type Difficulty,
  type QuizQuestion,
  type ResearchEvent,
} from "../types";
import { scrollBehavior } from "../useBrowserState";
import { useQuota } from "../useQuota";
import { loadedTopics, type TopicsState } from "../useTopics";
import {
  loadError,
  MAX_TOPIC_CHARS,
  MIN_TOPIC_CHARS,
  PageHeading,
  type PageProps,
  PRIMARY_BUTTON,
  SECONDARY_BUTTON,
} from "./common";
import { StatsPanel } from "./StatsPanel";

/** A search's agent log. `outcome` is set when the search was refused or cut short; otherwise
 * the log ends with a summary of what the search made. */
interface LiveLog {
  /** A new log per search, so the panel and its timer start afresh. */
  id: number;
  topic: string;
  difficulty: Difficulty;
  lines: LogLine[];
  outcome: LogOutcome | null;
}

function isDifficulty(value: string | null): value is Difficulty {
  return (DIFFICULTIES as readonly (string | null)[]).includes(value);
}

const ENDED_EARLY = "The search ended before this was made.";
const UNAVAILABLE = "Live research is not available right now.";

/** The mark on the history entry that the Mission Control button adds. It stays on that
 * entry through Back and Forward, so Close can tell that Back leads to this page. */
const PANEL_OPENED_HERE = { panel: "explore" } as const;

function openedHere(state: unknown): boolean {
  return isPlainObject(state) && state.panel === PANEL_OPENED_HERE.panel;
}

/**
 * The web page: a search researches a topic live and makes the whole of it, one agent run at a
 * time: a question at each level, the chosen level first, then the explanation at the chosen
 * level (docs/PLAN.md Session 8, "The web page makes whole topics"; the order changed on
 * 2026-10-10). Steps stream as an agent log; each question is shown as it is ready, with its
 * sources and source check once answered. The explanation sits behind a button that opens only
 * once every question has been answered, so it can never give an answer away; reading it counts
 * towards Explorer. What the bank already has is shown alongside, free, and a topic the bank has
 * in full uses no search. Each visitor has 2 searches a day.
 *
 * The window scrolls only when the player asks for it: GO, moving to the next question (only if
 * it starts off screen) and opening the explanation. The agent log scrolls its own box.
 *
 * The address can carry the form's values (`?topic=...&difficulty=...`, from the Learn page's
 * "research it live" link); it only fills the form, so a link can never spend a search.
 *
 * "Mission Control" opens over the page at /explore/stats (`statsOpen`). The page stays
 * mounted under it, so a search keeps streaming while the panel is open.
 */
export function ExplorePage({
  topicsState,
  retryTopics,
  profile,
  updateProfile,
  celebrate,
  difficulty,
  setDifficulty,
  statsOpen,
}: PageProps & { statsOpen: boolean }) {
  usePageTitle(statsOpen ? "Mission Control" : "Explore");
  const location = useLocation();
  const [initial] = useState(() => {
    const params = location.searchParams;
    const level = params.get("difficulty");
    return {
      // As long as the server accepts (api/research.py); the hint asks for less than that.
      topic: (params.get("topic") ?? "").slice(0, 200),
      difficulty: isDifficulty(level) ? level : null,
    };
  });
  const [query, setQuery] = useState(initial.topic);
  const [search, setSearch] = useState<Search | null>(null);
  const [log, setLog] = useState<LiveLog | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [questionAt, setQuestionAt] = useState(0);
  const [answered, setAnswered] = useState<ReadonlySet<number>>(new Set());
  const [explanationOpen, setExplanationOpen] = useState(false);
  const [quotaState, refreshQuota] = useQuota();
  const request = useRef<AbortController | null>(null);
  const viewRef = useRef<HTMLDivElement>(null);
  const questionsRef = useRef<HTMLElement>(null);
  const explanationRef = useRef<HTMLElement>(null);
  // What the player just asked to see, brought into view once it is on the page.
  const reveal = useRef<"question" | "explanation" | null>(null);
  // Trophies wait while a question is waiting for its answer, so no pop-up covers it.
  const deferred = useRef<Award[]>([]);
  const awaitingAnswer = useRef(false);
  // A search counts once towards Web researcher, with its first live item.
  const counted = useRef(false);

  function openStats() {
    navigate(PATHS.exploreStats, { state: PANEL_OPENED_HERE });
  }

  /** Back, when the button opened the panel, so no history entry is added. A shared link or a
   * new tab has no web page to go back to, so the address is replaced with /explore instead. */
  function closeStats() {
    if (openedHere(window.history.state)) {
      window.history.back();
    } else {
      navigate(PATHS.explore, { replace: true });
    }
  }

  useEffect(() => {
    if (initial.difficulty) {
      setDifficulty(initial.difficulty);
    }
  }, [initial.difficulty, setDifficulty]);

  // Leaving the page closes the stream (the server still finishes and stores the search) and
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
  const status = searchStatus(topics, query, difficulty);
  const suggestions = useMemo(() => suggestAny(topics, query), [topics, query]);
  const quota = quotaState.kind === "loaded" ? quotaState.quota : null;
  const typed = query.trim().length;
  const sized = typed >= MIN_TOPIC_CHARS && typed <= MAX_TOPIC_CHARS;
  // If the quota cannot be read, the server still enforces every limit when a search starts.
  const liveAllowed = quota === null || (quota.remaining > 0 && quota.global_open);
  // A topic the bank has in part is always allowed: its bank items are shown even when the
  // search itself is refused.
  const canGo =
    !streaming &&
    sized &&
    (status.kind === "complete" ||
      status.kind === "partial" ||
      (status.kind === "new" && liveAllowed));

  const questions = search ? questionSlots(search) : [];
  const current = nextOpen(questions, questionAt);
  const currentSlot = current === null ? undefined : questions[current];
  const currentQuestion =
    currentSlot?.state.kind === "ready" && currentSlot.state.item.mode === "quiz"
      ? currentSlot.state.item
      : null;
  const currentToken = currentSlot?.state.kind === "ready" ? currentSlot.state.revealToken : undefined;
  const awaiting = currentQuestion !== null && !answered.has(currentQuestion.id);
  useEffect(() => {
    awaitingAnswer.current = awaiting;
  }, [awaiting]);
  const explanation = search ? explanationSlot(search) : undefined;
  const lock = search ? explanationLock(search, answered) : undefined;

  // The next question, once the player moves on, if it starts off screen (after a long answer it
  // starts above it); the explanation, once opened.
  useEffect(() => {
    const wanted = reveal.current;
    reveal.current = null;
    const target = wanted === "question" ? questionsRef.current : explanationRef.current;
    if (wanted === null || !target) {
      return;
    }
    if (wanted === "explanation" || startsOffScreen(target.getBoundingClientRect().top, window.innerHeight)) {
      target.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
    }
  }, [current, explanationOpen]);

  function award(awards: readonly Award[]) {
    if (awards.length === 0) {
      return;
    }
    if (awaitingAnswer.current) {
      deferred.current = [...deferred.current, ...awards];
    } else {
      celebrate(awards);
    }
  }

  function newRequest(): AbortSignal {
    request.current?.abort();
    request.current = new AbortController();
    return request.current.signal;
  }

  /** What the bank already has is loaded here, free. */
  function loadBankItems(planned: Search, signal: AbortSignal) {
    const seen = profile.seenItems;
    for (const slot of planned.slots) {
      if (slot.source !== "bank") {
        continue;
      }
      fetchItem(planned.topic, slot.mode, slot.difficulty, seen, signal)
        .then((item) => {
          setSearch((s) => (s?.id === planned.id ? resolved(s, slot.key, item) : s));
        })
        .catch((error: unknown) => {
          if (!signal.aborted) {
            setSearch((s) => (s?.id === planned.id ? missed(s, slot.key, loadError(error)) : s));
          }
        });
    }
  }

  function research(topic: string) {
    const level = difficulty;
    const signal = newRequest();
    const searchId = Date.now();
    const patch = (change: (s: Search) => Search) =>
      setSearch((s) => (s?.id === searchId ? change(s) : s));
    const addLine = (line: LogLine) =>
      setLog((l) => (l ? { ...l, lines: [...l.lines, line] } : l));
    const stop = (outcome: LogOutcome, message: string) => {
      setLog((l) => (l ? { ...l, outcome } : l));
      patch((s) => ended(s, message));
    };

    deferred.current = [];
    counted.current = false;
    setSearch(null);
    setQuestionAt(0);
    setAnswered(new Set());
    setExplanationOpen(false);
    setLog({ id: searchId, topic, difficulty: level, lines: [], outcome: null });
    setStreaming(true);
    viewRef.current?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });

    // The first live item counts the search towards Web researcher. The explanation counts
    // towards Explorer when the player opens it, not when it arrives.
    const onLiveItem = () => {
      if (!counted.current) {
        counted.current = true;
        award(updateProfile(afterLiveRun));
      }
    };

    const onEvent = (event: ResearchEvent) => {
      switch (event.type) {
        case "plan": {
          const planned = fromPlan(searchId, event.topic, event.items);
          setSearch(planned);
          if (event.items.some((item) => item.source === "live")) {
            setLog((l) => (l ? { ...l, topic: event.topic } : l));
          } else {
            setLog(null); // the bank has the whole topic: no agent runs
          }
          loadBankItems(planned, signal);
          break;
        }
        case "log": {
          const key = event.key;
          if (key !== null) {
            patch((s) => started(s, key));
          }
          addLine({
            key,
            label: event.label,
            detail: event.detail,
            tone: event.tone,
            verdict: event.verdict,
          });
          break;
        }
        case "result":
          patch((s) => resolved(s, event.key, event.item, event.reveal_token ?? undefined));
          onLiveItem();
          break;
        case "stats":
          patch((s) => measured(s, event.key, event.stats));
          break;
        case "missed":
          patch((s) => missed(s, event.key, event.message));
          addLine({
            key: event.key,
            label: "Left out",
            detail: event.message,
            tone: "warn",
            verdict: null,
          });
          break;
        case "rejected":
          stop({ kind: "rejected", message: event.message }, event.message);
          break;
        case "fallback":
        case "error":
          stop({ kind: "fallback", message: event.message }, event.message);
          break;
      }
    };

    streamResearch(topic, level, onEvent, signal)
      .catch((error: unknown) => {
        if (signal.aborted) {
          return;
        }
        if (error instanceof ApiError && (error.status === 400 || error.status === 429)) {
          stop({ kind: "rejected", message: error.message }, error.message);
          return;
        }
        stop({ kind: "fallback", message: UNAVAILABLE }, UNAVAILABLE);
      })
      .finally(() => {
        if (!signal.aborted) {
          patch((s) => (s.ended ? s : ended(s, ENDED_EARLY)));
          setStreaming(false);
          refreshQuota();
        }
      });
  }

  function go() {
    if (canGo) {
      research(query.trim());
    }
  }

  /** One question on its own: scored like a quiz answer, with no streak and no run. */
  function onAnswered(question: QuizQuestion, correct: boolean, seconds: number): AnswerScore {
    const streak = correct ? 1 : 0;
    const score = scoreAnswer(question.difficulty, correct, streak, seconds);
    const awards = updateProfile((p) =>
      afterAnswer(p, question.difficulty, question.id, question.topic, score, correct, streak),
    );
    setAnswered((ids) => new Set(ids).add(question.id));
    awaitingAnswer.current = false;
    celebrate([...deferred.current, ...awards]);
    deferred.current = [];
    return score;
  }

  /** The explanation, once its lock is open. Reading it counts towards Explorer. */
  function openExplanation() {
    if (lock?.kind !== "open" || explanation?.state.kind !== "ready") {
      return;
    }
    if (explanationOpen) {
      explanationRef.current?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
      return;
    }
    const item = explanation.state.item;
    reveal.current = "explanation";
    setExplanationOpen(true);
    award(updateProfile((p) => afterLearn(p, item.id, item.topic)));
  }

  function nextQuestion(index: number) {
    reveal.current = "question";
    setQuestionAt(index);
  }

  function startOver() {
    request.current?.abort();
    setStreaming(false);
    setSearch(null);
    setLog(null);
    setExplanationOpen(false);
    setQuery("");
    window.scrollTo({ top: 0, behavior: scrollBehavior() });
  }

  const logOutcome: LogOutcome | null = log
    ? (log.outcome ?? (search?.ended ? searchOutcome(search) : { kind: "running" }))
    : null;
  const showItems =
    search !== null &&
    (!search.ended ||
      search.slots.some((slot) => slot.source === "bank" || slot.state.kind === "ready"));

  return (
    <div className="flex flex-col items-center">
      <PageHeading title="Explore">
        Research a topic that is not in the bank yet. The agent reads NASA, ESA, arXiv and
        Wikipedia live, writes a question at each level and an explanation, and checks each
        against the pages it read. The explanation opens once you have answered the questions.
      </PageHeading>

      <div className="mt-10 flex items-center gap-4">
        <span aria-hidden="true" className="on-scene-muted font-pixel text-[8px] uppercase">
          Difficulty
        </span>
        <Dropdown
          label="Difficulty"
          options={DIFFICULTIES}
          value={difficulty}
          onChange={setDifficulty}
        />
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
        <p role="status" className="scene-note mt-4 max-w-md text-center text-sm">
          {quota.global_open ? quotaLine(quota) : GLOBAL_CAP_NOTICE}
        </p>
      )}
      <button
        type="button"
        onClick={openStats}
        className={`${SECONDARY_BUTTON} mt-6 px-4 py-3 text-[9px]`}
      >
        Mission Control
      </button>

      <div ref={viewRef} className="mt-10 w-full scroll-mt-6" aria-live="polite">
        {log && logOutcome && (
          <div className="mb-8">
            <AgentLog
              key={log.id}
              topic={log.topic}
              difficulty={log.difficulty}
              lines={log.lines}
              outcome={logOutcome}
            />
            {search && search.runs.length > 0 && (
              <p className="scene-note mt-3 text-sm">
                What each run cost and did:{" "}
                <button
                  type="button"
                  onClick={openStats}
                  className="text-teal underline underline-offset-4 hover:text-ink"
                >
                  this search in Mission Control
                </button>
              </p>
            )}
          </div>
        )}

        {search && showItems && (
          <div className="space-y-10">
            <section ref={questionsRef} aria-label="Questions" className="scroll-mt-6">
              <QuestionStrip slots={questions} current={current} answered={answered} />
              {currentSlot && current !== null ? (
                <div className="mt-4">
                  <SlotTag slot={currentSlot} />
                  {currentQuestion ? (
                    <QuizCard
                      key={currentSlot.key}
                      question={currentQuestion}
                      revealToken={currentToken}
                      onAnswered={(correct, seconds) =>
                        onAnswered(currentQuestion, correct, seconds)
                      }
                      {...nextButton(
                        questions,
                        current,
                        () => nextQuestion(current + 1),
                        explanation,
                        lock,
                        openExplanation,
                        startOver,
                      )}
                    />
                  ) : (
                    <SlotNote slot={currentSlot} />
                  )}
                </div>
              ) : (
                <p className="mt-6 text-center">
                  <button
                    type="button"
                    onClick={startOver}
                    className={`${PRIMARY_BUTTON} px-6 py-3.5 text-[10px]`}
                  >
                    Another new topic
                  </button>
                </p>
              )}
            </section>

            {explanation && lock && (
              <section ref={explanationRef} aria-label="Explanation" className="scroll-mt-6">
                <h2 className="on-scene font-heading text-xl font-bold">Explanation</h2>
                <div className="mt-4">
                  {explanationOpen &&
                  explanation.state.kind === "ready" &&
                  explanation.state.item.mode === "learn" ? (
                    <>
                      <SlotTag slot={explanation} />
                      <LearnCard
                        item={explanation.state.item}
                        nextLabel="Another new topic"
                        onNext={startOver}
                      />
                    </>
                  ) : (
                    <ExplanationGate slot={explanation} lock={lock} onOpen={openExplanation} />
                  )}
                </div>
              </section>
            )}
          </div>
        )}

        {search?.ended && !showItems && logOutcome?.kind !== "rejected" && <BankLinks />}
        {!search && logOutcome?.kind === "fallback" && <BankLinks />}
      </div>

      <StatsPanel
        open={statsOpen}
        onClose={closeStats}
        search={search}
        level={log?.difficulty ?? null}
        running={streaming}
      />
    </div>
  );
}

function searchOutcome(search: Search): LogOutcome {
  const summary = summarize(search);
  const message = summaryLine(summary);
  return madeAnything(search) ? { kind: "done", message } : { kind: "nothing", message };
}

/** Why an item is not shown yet: "loading" from the bank, or "researching" live. */
function coming(slot: Slot): string {
  return slot.state.kind === "loading" ? "loading" : "researching";
}

/** The question card's next button: the next question once it is ready; after the last one,
 * the explanation once it opens; else a new topic. */
function nextButton(
  questions: readonly Slot[],
  current: number,
  onNextQuestion: () => void,
  explanation: Slot | undefined,
  lock: ExplanationLock | undefined,
  onOpenExplanation: () => void,
  onNewTopic: () => void,
): { nextLabel: string; onNext: () => void; nextDisabled: boolean } {
  const next = nextOpen(questions, current + 1);
  const slot = next === null ? undefined : questions[next];
  if (slot) {
    const label = itemLabel(slot.key);
    if (slot.state.kind === "ready") {
      return { nextLabel: `Next: ${label}`, onNext: onNextQuestion, nextDisabled: false };
    }
    return { nextLabel: `${label}: ${coming(slot)}`, onNext: onNextQuestion, nextDisabled: true };
  }
  if (explanation && lock && lock.kind !== "missed") {
    if (lock.kind === "open") {
      return { nextLabel: "Read the explanation", onNext: onOpenExplanation, nextDisabled: false };
    }
    return {
      nextLabel: `${itemLabel(explanation.key)}: ${coming(explanation)}`,
      onNext: onOpenExplanation,
      nextDisabled: true,
    };
  }
  return { nextLabel: "Another new topic", onNext: onNewTopic, nextDisabled: false };
}

/** Over each item shown: where it comes from. */
function SlotTag({ slot }: { slot: Slot }) {
  if (slot.state.kind !== "ready") {
    return null;
  }
  return (
    <p className="on-scene-muted mb-3 font-pixel text-[8px] uppercase">
      {slot.source === "bank" ? "From the bank, free" : "Researched just now"}
    </p>
  );
}

/** An item that is not shown (yet): on its way, or left out and why. */
function SlotNote({ slot }: { slot: Slot }) {
  const label = itemLabel(slot.key);
  const text = {
    waiting: `The ${label} is next in line. It appears here when it is ready.`,
    researching: `The agent is researching the ${label}. It appears here when it is ready.`,
    loading: `Loading the ${label} from the bank...`,
    ready: "",
    missed: `The ${label} was left out. ${slot.state.kind === "missed" ? slot.state.message : ""}`,
  }[slot.state.kind];
  return (
    <p
      className={`pixel-border rounded-sm bg-surface px-5 py-4 text-sm ${
        slot.state.kind === "missed" ? "text-slate" : "text-ink/90"
      }`}
    >
      {text}
    </p>
  );
}

/** The explanation before it is opened: why it is not open yet, or the button that opens it. */
function ExplanationGate({
  slot,
  lock,
  onOpen,
}: {
  slot: Slot;
  lock: ExplanationLock;
  onOpen: () => void;
}) {
  const label = itemLabel(slot.key);
  let text: string;
  switch (lock.kind) {
    case "locked":
      text = `It opens once you have answered ${
        lock.left === 1 ? "the last question" : `the ${lock.left} questions left`
      }, so it cannot give an answer away.`;
      break;
    case "coming":
      text =
        slot.state.kind === "loading"
          ? `Loading the ${label} from the bank...`
          : `The agent is writing the ${label}. It opens here when it is ready.`;
      break;
    case "open":
      text = `The ${label} is ready, with the pages it is based on.`;
      break;
    case "missed":
      text = `The ${label} was left out. ${lock.message}`;
      break;
  }
  return (
    <div className="pixel-border flex flex-col gap-4 rounded-sm bg-surface px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <p className={`text-sm ${lock.kind === "missed" ? "text-slate" : "text-ink/90"}`}>{text}</p>
      {lock.kind !== "missed" && (
        <button
          type="button"
          onClick={onOpen}
          disabled={lock.kind !== "open"}
          className={`${PRIMARY_BUTTON} shrink-0 px-5 py-3.5 text-[10px]`}
        >
          Read the explanation
        </button>
      )}
    </div>
  );
}

/** The three questions, in the order they are played, and where each one is. */
function QuestionStrip({
  slots,
  current,
  answered,
}: {
  slots: readonly Slot[];
  current: number | null;
  answered: ReadonlySet<number>;
}) {
  function state(slot: Slot): string {
    switch (slot.state.kind) {
      case "ready":
        return answered.has(slot.state.item.id) ? "answered" : "ready";
      case "missed":
        return "left out";
      case "loading":
        return "loading";
      case "researching":
        return "researching";
      case "waiting":
        return "waiting";
    }
  }
  return (
    <div className="on-scene flex flex-wrap items-baseline gap-x-5 gap-y-2">
      <h2 className="font-heading text-xl font-bold">Questions</h2>
      <ol className="flex flex-wrap gap-x-4 gap-y-1">
        {slots.map((slot, index) => (
          <li
            key={slot.key}
            aria-current={index === current ? "step" : undefined}
            className={`pixel-bullet font-pixel text-[8px] uppercase ${
              index === current ? "text-teal" : "text-ink"
            }`}
          >
            {slot.difficulty} <span className="text-ink/80">{state(slot)}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Nothing to show from this search: the bank is free, so offer it. */
function BankLinks() {
  const link = "text-teal underline underline-offset-4 hover:text-ink";
  return (
    <p className="scene-note mx-auto text-center text-sm">
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
  status: SearchStatus;
  difficulty: Difficulty;
  tooLong: boolean;
  onRetry: () => void;
}

/** One line under the topic box: what GO will do, or why it is not available. */
function Hint({ state, status, difficulty, tooLong, onRetry }: HintProps) {
  const base = "scene-note mt-3 min-h-5 text-sm";
  if (state.kind === "loading") {
    return <p className={base}>Loading topics...</p>;
  }
  if (state.kind === "failed") {
    return (
      <p className={base}>
        Could not load the topics.{" "}
        <button type="button" onClick={onRetry} className="text-teal underline underline-offset-4">
          Try again
        </button>
      </p>
    );
  }
  if (tooLong) {
    // Not rust, which is under 4.5:1 on the chip.
    return (
      <p className={`${base} font-medium`}>
        Keep the topic under {MAX_TOPIC_CHARS} characters.
      </p>
    );
  }
  const level = difficulty.toUpperCase();
  switch (status.kind) {
    case "empty":
      return (
        <p className={base}>
          Any astronomy or space topic. The agent writes a question at each level, the {level} one
          first in about 20 seconds, then the explanation at {level}.
        </p>
      );
    case "new":
      return (
        <p className={base}>
          Not in the bank yet. GO uses one search: a question at each level, {level} first, then
          the explanation at {level}, about 80 seconds in all.
        </p>
      );
    case "partial":
      return (
        <p className={base}>
          {status.topic.name} is in the bank, but not all of it. GO makes only the{" "}
          {status.missing === 1 ? "missing item" : `${status.missing} missing items`} with one
          search; the rest is shown free.
        </p>
      );
    case "complete":
      return (
        <p className={base}>
          {status.topic.name} is in the bank at every level, so GO shows it here for free and
          uses no search.
        </p>
      );
  }
}
