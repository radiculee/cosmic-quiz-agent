import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, fetchItem, type ResearchRequest, streamResearch } from "../api";
import { searchOutcome } from "../outcome";
import { AgentLog, type LogLine, type LogOutcome } from "../components/AgentLog";
import { LearnCard } from "../components/LearnCard";
import { Link } from "../components/Link";
import { QuizCard } from "../components/QuizCard";
import { SearchProgress } from "../components/SearchProgress";
import { type ExplanationsAction, WebResults } from "../components/WebResults";
import { SegmentedControl } from "../components/SegmentedControl";
import { HeaderSettings } from "../components/HeaderSettings";
import { TopicInput } from "../components/TopicInput";
import { type AnswerScore, scoreAnswer } from "../game";
import { isPlainObject } from "../guards";
import { afterAnswer, afterLearn, afterLiveRun } from "../profile";
import { GLOBAL_CAP_NOTICE, quotaLine, quotaShort } from "../quota";
import { navigate, PATHS, useLocation, usePageTitle } from "../router";
import { startsOffScreen } from "../scroll";
import {
  ended,
  type ExplanationLock,
  explanationLock,
  explanationSlots,
  firstReady,
  fromPlan,
  itemLabel,
  measured,
  missed,
  nextOpen,
  progressed,
  questionSlots,
  resolved,
  type Search,
  type Slot,
  started,
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
import { resultsDue, webScore } from "../webResults";
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
  lines: LogLine[];
  outcome: LogOutcome | null;
}

/** The log's title until the agent has picked a topic. */
const SURPRISE_TOPIC = "Surprise me";
/** Under an explanation the search did not make: what happens next (decided 2026-10-28). */
const MADE_OVERNIGHT =
  "The agent tries again overnight, and the topic joins Learn and Quiz once every level is ready.";

/** Under the landing page's buttons: what a search does and how long it takes. */
const HOW_IT_WORKS =
  "It reads NASA, ESA, arXiv and Wikipedia live, writes a question and an explanation at each level, and checks each against the pages it read. The first question usually takes under a minute, and the whole topic a minute or two. The explanations open once you have answered the questions.";

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
 * time: a question at each level, then an explanation at each level, easiest first (docs/PLAN.md
 * "Universal topics", 2026-10-28; there is no level to choose). SURPRISE ME asks the agent to
 * pick a topic the bank does not have yet, then runs the same search. Steps stream as an agent
 * log; each question is shown as it is ready, with its sources and source check once answered.
 * The explanations sit behind a button that opens only once every question has been answered,
 * so they can never give an answer away; then a tab per level shows each one, and reading one
 * counts towards Explorer. What a search did not make, the daily Curator makes overnight. What
 * the bank already has is shown alongside, free, and a topic the bank has in full uses no
 * search. Each visitor has 2 searches a day (5 in the launch week; the quota comes from
 * /api/quota).
 *
 * The window scrolls only when the player asks for it: GO, moving to the next question (only if
 * it starts off screen) and opening the explanations. The agent log scrolls its own box.
 *
 * The address can carry a topic (`?topic=...`, from the Learn page's "research it live" link);
 * it only fills the form, so a link can never spend a search. An old link's `difficulty` is
 * ignored.
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
  statsOpen,
}: PageProps & { statsOpen: boolean }) {
  usePageTitle(statsOpen ? "Mission Control" : "Explore");
  const location = useLocation();
  // As long as the server accepts (api/research.py); the hint asks for less than that.
  const [query, setQuery] = useState(() =>
    (location.searchParams.get("topic") ?? "").slice(0, 200),
  );
  const [search, setSearch] = useState<Search | null>(null);
  const [log, setLog] = useState<LiveLog | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [questionAt, setQuestionAt] = useState(0);
  const [answered, setAnswered] = useState<ReadonlySet<number>>(new Set());
  // Of those, the questions answered right, for the result card.
  const [right, setRight] = useState<ReadonlySet<number>>(new Set());
  const [explanationOpen, setExplanationOpen] = useState(false);
  // The agent log sits behind "Show details" in the progress rows; each search starts it closed.
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [explanationLevel, setExplanationLevel] = useState<Difficulty>("easy");
  const [quotaState, refreshQuota] = useQuota();
  const request = useRef<AbortController | null>(null);
  const viewRef = useRef<HTMLDivElement>(null);
  const questionsRef = useRef<HTMLElement>(null);
  const explanationRef = useRef<HTMLElement>(null);
  const scrolledFor = useRef<number | null>(null);
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
  const status = searchStatus(topics, query);
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
  const canSurprise = !streaming && liveAllowed;

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
  const explanations = search ? explanationSlots(search) : [];
  const shownExplanation = explanations.find((slot) => slot.difficulty === explanationLevel);
  const lock = search ? explanationLock(search, answered) : undefined;
  const resultsShown = resultsDue(questions, answered);

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

  // The first question, the moment it is ready: its card goes to the top. Once for each search,
  // so the page never moves again on its own.
  const searchId = search?.id ?? null;
  useEffect(() => {
    if (searchId !== null && currentQuestion && scrolledFor.current !== searchId) {
      scrolledFor.current = searchId;
      questionsRef.current?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
    }
  }, [searchId, currentQuestion]);

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

  /** A search for `topic`, or for one the agent picks when it is null (SURPRISE ME). */
  function research(topic: string | null) {
    const asked: ResearchRequest = topic === null ? { surprise: true } : { topic };
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
    setRight(new Set());
    setExplanationOpen(false);
    setExplanationLevel("easy");
    setDetailsOpen(false);
    setUnavailable(false);
    setLog({ id: searchId, topic: topic ?? SURPRISE_TOPIC, lines: [], outcome: null });
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
          if (topic === null) {
            setQuery(event.topic); // the agent's pick, so the box says what is being researched
          }
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
        case "progress":
          patch((s) => progressed(s, event.key, event.stage, event.status, event.seconds));
          break;
        case "result":
          patch((s) => resolved(s, event.key, event.item, event.reveal_token ?? undefined));
          onLiveItem();
          break;
        case "end":
          setUnavailable(event.unavailable);
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

    streamResearch(asked, onEvent, signal)
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

  function surprise() {
    if (canSurprise) {
      research(null);
    }
  }

  /** One question on its own: scored like a quiz answer, with no streak and no run. */
  function onAnswered(
    question: QuizQuestion,
    correct: boolean,
    seconds: number,
    choice: number,
  ): AnswerScore {
    const streak = correct ? 1 : 0;
    const score = scoreAnswer(question.difficulty, correct, streak, seconds);
    const awards = updateProfile((p) =>
      afterAnswer(p, question.difficulty, question.id, question.topic, score, correct, streak, {
        seconds,
        choice,
      }),
    );
    setAnswered((ids) => new Set(ids).add(question.id));
    if (correct) {
      setRight((ids) => new Set(ids).add(question.id));
    }
    awaitingAnswer.current = false;
    celebrate([...deferred.current, ...awards]);
    deferred.current = [];
    return score;
  }

  /** Reading an explanation counts towards Explorer (once per item, see afterLearn). */
  function read(slot: Slot | undefined) {
    if (slot?.state.kind === "ready") {
      const item = slot.state.item;
      award(updateProfile((p) => afterLearn(p, item.id, item.topic)));
    }
  }

  /** The explanations, once their lock is open, starting on the easiest one that is ready. */
  function openExplanation() {
    const first = firstReady(explanations);
    if (lock?.kind !== "open" || !first) {
      return;
    }
    if (explanationOpen) {
      explanationRef.current?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
      return;
    }
    reveal.current = "explanation";
    setExplanationOpen(true);
    setExplanationLevel(first.difficulty);
    read(first);
  }

  function showLevel(level: Difficulty) {
    setExplanationLevel(level);
    read(explanations.find((slot) => slot.difficulty === level));
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
    ? (log.outcome ?? (search?.ended ? searchOutcome(search, unavailable) : { kind: "running" }))
    : null;
  const hasLive = search !== null && search.slots.some((slot) => slot.source === "live");
  const showItems =
    search !== null &&
    (!search.ended ||
      search.slots.some((slot) => slot.source === "bank" || slot.state.kind === "ready"));

  // Before a search the page has one job, so the topic box sits in the page right above GO. Once a
  // search or its log is on the page, the box goes back to the sticky header (with the short
  // quota), so the next search starts without a scroll to the top. Only one box exists at a time.
  const landing = search === null && log === null;
  const topicBox = (
    <TopicInput
      value={query}
      suggestions={suggestions}
      disabled={topicsState.kind !== "loaded"}
      placeholder="A new topic, e.g. Pulsars"
      onChange={setQuery}
      onSubmit={go}
      small={!landing}
    />
  );
  const quotaNote = quota?.global_open && (
    <p role="status" className="scene-note mt-6 max-w-md text-center text-sm">
      {quotaLine(quota)}
    </p>
  );

  return (
    <div className="flex flex-col items-center">
      <PageHeading title="Explore">
        Research any astronomy or space topic that is not in the bank yet.
      </PageHeading>

      {landing ? (
        <div className="mt-8 w-full max-w-xl">{topicBox}</div>
      ) : (
        <HeaderSettings>
          <div className="flex items-center gap-3">
            {topicBox}
            {quota && (
              <span className="shrink-0 font-pixel text-[8px] uppercase text-slate">
                {quotaShort(quota)}
              </span>
            )}
          </div>
        </HeaderSettings>
      )}

      {/* The hint explains what GO will do, so it stays beside GO; it says nothing for an empty box. */}
      {status.kind !== "empty" || typed > MAX_TOPIC_CHARS || topicsState.kind !== "loaded" ? (
        <div className="mt-3 w-full max-w-xl">
          <Hint
            state={topicsState}
            status={status}
            tooLong={typed > MAX_TOPIC_CHARS}
            onRetry={retryTopics}
          />
        </div>
      ) : null}

      <div className="mt-6 flex flex-col items-center gap-1">
        <button
          type="button"
          onClick={go}
          disabled={!canGo}
          className={`${PRIMARY_BUTTON} px-12 py-4 text-[11px]`}
        >
          Go
        </button>
        <button
          type="button"
          onClick={surprise}
          disabled={!canSurprise}
          title="The agent picks a topic the bank does not have yet. Uses one search."
          className="on-scene min-h-11 px-4 font-pixel text-[9px] uppercase underline underline-offset-4 hover:no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:opacity-60 disabled:no-underline"
        >
          Surprise me
        </button>
      </div>
      {quota && !quota.global_open && (
        <p role="status" className="scene-note mt-3 max-w-md text-center text-sm">
          {GLOBAL_CAP_NOTICE}
        </p>
      )}
      <button
        type="button"
        onClick={openStats}
        className={`${SECONDARY_BUTTON} mt-6 px-4 py-3 text-[9px]`}
      >
        Mission Control
      </button>
      {landing && quotaNote}
      {landing && (
        <p className="scene-note mt-6 max-w-xl text-center text-sm leading-relaxed">{HOW_IT_WORKS}</p>
      )}

      <div ref={viewRef} className="mt-10 w-full scroll-mt-32" aria-live="polite">
        {!search && log && logOutcome && (
          <AgentLog key={log.id} topic={log.topic} lines={log.lines} outcome={logOutcome} />
        )}

        {search && (showItems || hasLive) && (
          <div className="space-y-10">
            <section ref={questionsRef} aria-label="Questions" className="scroll-mt-32">
              {showItems &&
                (currentQuestion && currentSlot && current !== null ? (
                  <div className="mb-4">
                    <SlotTag slot={currentSlot} />
                    <QuizCard
                      key={currentSlot.key}
                      question={currentQuestion}
                      revealToken={currentToken}
                      onAnswered={(correct, seconds, choice) =>
                        onAnswered(currentQuestion, correct, seconds, choice)
                      }
                      {...(resultsShown
                        ? {}
                        : nextButton(
                            questions,
                            current,
                            () => nextQuestion(current + 1),
                            lock,
                            openExplanation,
                            startOver,
                          ))}
                    />
                  </div>
                ) : (
                  current === null && (
                    <p className="mb-4 text-center">
                      <button
                        type="button"
                        onClick={startOver}
                        className={`${PRIMARY_BUTTON} px-6 py-3.5 text-[10px]`}
                      >
                        Another new topic
                      </button>
                    </p>
                  )
                ))}
              {resultsShown && (
                <WebResults
                  score={webScore(answered, right)}
                  explanations={explanationsAction(lock, openExplanation)}
                  onNewTopic={startOver}
                />
              )}
              {hasLive && log && logOutcome && (
                <SearchProgress
                  key={log.id}
                  search={search}
                  message={search.ended && logOutcome.kind !== "running" ? logOutcome.message : null}
                  detailsOpen={detailsOpen}
                  onToggleDetails={() => setDetailsOpen((open) => !open)}
                  details={
                    <>
                      <AgentLog
                        topic={log.topic}
                        lines={log.lines}
                        outcome={logOutcome}
                      />
                      {search.runs.length > 0 && (
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
                    </>
                  }
                />
              )}
            </section>

            {showItems && lock && (
              <section ref={explanationRef} aria-label="Explanations" className="scroll-mt-32">
                <h2 className="on-scene font-heading text-xl font-bold">Explanations</h2>
                <div className="mt-4">
                  {explanationOpen && lock.kind === "open" ? (
                    <>
                      <SegmentedControl
                        label="Explanation level"
                        options={DIFFICULTIES}
                        value={explanationLevel}
                        onChange={showLevel}
                      />
                      <div className="mt-4">
                        {shownExplanation?.state.kind === "ready" &&
                        shownExplanation.state.item.mode === "learn" ? (
                          <>
                            <SlotTag slot={shownExplanation} />
                            <LearnCard
                              key={shownExplanation.key}
                              item={shownExplanation.state.item}
                              nextLabel="Another new topic"
                              onNext={startOver}
                            />
                          </>
                        ) : (
                          shownExplanation && (
                            <SlotNote slot={shownExplanation} afterMissed={MADE_OVERNIGHT} />
                          )
                        )}
                      </div>
                    </>
                  ) : (
                    <ExplanationGate lock={lock} onOpen={openExplanation} />
                  )}
                </div>
              </section>
            )}
          </div>
        )}

        {search?.ended && !showItems && logOutcome?.kind !== "rejected" && <BankLinks />}
        {!search && logOutcome?.kind === "fallback" && <BankLinks />}
      </div>

      {!landing && quotaNote}

      <StatsPanel open={statsOpen} onClose={closeStats} search={search} running={streaming} />
    </div>
  );
}

/** The result card's button for the explanations; none if the search made none. */
function explanationsAction(
  lock: ExplanationLock | undefined,
  onOpen: () => void,
): ExplanationsAction | null {
  if (!lock || lock.kind === "missed") {
    return null;
  }
  return lock.kind === "open"
    ? { label: "Read the explanations", disabled: false, onClick: onOpen }
    : { label: "Explanations: researching", disabled: true, onClick: onOpen };
}

/** The question card's next button: the next question once it is ready; after the last one,
 * the explanations once they open; else a new topic. */
function nextButton(
  questions: readonly Slot[],
  current: number,
  onNextQuestion: () => void,
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
    const level = slot.difficulty.charAt(0).toUpperCase() + slot.difficulty.slice(1);
    return { nextLabel: `${level} question on the way`, onNext: onNextQuestion, nextDisabled: true };
  }
  if (lock && lock.kind !== "missed") {
    if (lock.kind === "open") {
      return { nextLabel: "Read the explanations", onNext: onOpenExplanation, nextDisabled: false };
    }
    return { nextLabel: "Explanations: researching", onNext: onOpenExplanation, nextDisabled: true };
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

/** An item that is not shown (yet): on its way, or left out and why, then `afterMissed`. */
function SlotNote({ slot, afterMissed = "" }: { slot: Slot; afterMissed?: string }) {
  const label = itemLabel(slot.key);
  const text = {
    waiting: `The ${label} is next in line. It appears here when it is ready.`,
    researching: `The agent is researching the ${label}. It appears here when it is ready.`,
    loading: `Loading the ${label} from the bank...`,
    ready: "",
    missed: [
      `The ${label} was left out.`,
      slot.state.kind === "missed" ? slot.state.message : "",
      afterMissed,
    ]
      .filter(Boolean)
      .join(" "),
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

/** The explanations before they are opened: why they are not open yet, or the button that
 * opens them. */
function ExplanationGate({ lock, onOpen }: { lock: ExplanationLock; onOpen: () => void }) {
  let text: string;
  switch (lock.kind) {
    case "locked":
      text = `They open once you have answered ${
        lock.left === 1 ? "the last question" : `the ${lock.left} questions left`
      }, so they cannot give an answer away.`;
      break;
    case "coming":
      text = "The agent is writing the EASY explanation. They open here when it is ready.";
      break;
    case "open":
      text = "Ready, one for each level, with the pages they are based on.";
      break;
    case "missed":
      text = `The explanations were left out. ${lock.message} ${MADE_OVERNIGHT}`;
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
          Read the explanations
        </button>
      )}
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
  tooLong: boolean;
  onRetry: () => void;
}

/** One line under the topic box: what GO will do, or why it is not available. Nothing for an empty box. */
function Hint({ state, status, tooLong, onRetry }: HintProps) {
  const base = "scene-note text-sm";
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
  switch (status.kind) {
    case "empty":
      return null;
    case "new":
      return (
        <p className={base}>
          Not in the bank yet. GO uses one search: a question and an explanation at each level,
          usually a minute or two in all.
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
