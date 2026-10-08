import {
  type BankTopic,
  DIFFICULTIES,
  type Difficulty,
  type Item,
  type ItemKey,
  type LearnItem,
  type Mode,
  MODES,
  type OptionCheck,
  type PlannedItem,
  type Quota,
  type QuizAnswer,
  type QuizQuestion,
  type ResearchEvent,
  type ShownStatus,
  type Source,
  type SourceCheck,
  VERDICTS,
} from "./types";

/** The API failed, or answered with something this version of the app does not expect. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
  }
}

// --- Runtime checks: the browser trusts nothing it has not checked. ---------------------------

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isListOf<T>(value: unknown, check: (entry: unknown) => entry is T): value is T[] {
  return Array.isArray(value) && value.every(check);
}

function isDifficulty(value: unknown): value is Difficulty {
  return isString(value) && (DIFFICULTIES as readonly string[]).includes(value);
}

function isShownStatus(value: unknown): value is ShownStatus {
  return value === "published" || value === "review";
}

function isBankTopic(value: unknown): value is BankTopic {
  return (
    isRecord(value) &&
    isString(value.name) &&
    (value.kind === "evergreen" || value.kind === "news" || value.kind === "custom") &&
    isListOf(value.learn, isDifficulty) &&
    isListOf(value.quiz, isDifficulty)
  );
}

function isSource(value: unknown): value is Source {
  return isRecord(value) && isString(value.url) && isString(value.site) && isString(value.quote);
}

function isOptionCheck(value: unknown): value is OptionCheck {
  return (
    isRecord(value) &&
    isNumber(value.option) &&
    isString(value.verdict) &&
    (VERDICTS as readonly string[]).includes(value.verdict) &&
    isNumber(value.confidence)
  );
}

function isSourceCheck(value: unknown): value is SourceCheck {
  return (
    isRecord(value) &&
    isListOf(value.options, isOptionCheck) &&
    isNumber(value.sentences) &&
    isNumber(value.sentences_supported)
  );
}

function isQuizQuestion(value: unknown): value is QuizQuestion {
  return (
    isRecord(value) &&
    value.mode === "quiz" &&
    isNumber(value.id) &&
    isDifficulty(value.difficulty) &&
    isString(value.topic) &&
    isString(value.question) &&
    isListOf(value.options, isString) &&
    isShownStatus(value.status)
  );
}

function isLearnItem(value: unknown): value is LearnItem {
  return (
    isRecord(value) &&
    value.mode === "learn" &&
    isNumber(value.id) &&
    isDifficulty(value.difficulty) &&
    isString(value.topic) &&
    isString(value.explanation) &&
    isListOf(value.sources, isSource) &&
    isSourceCheck(value.source_check) &&
    isShownStatus(value.status) &&
    isListOf(value.doubts, isString)
  );
}

function isQuizAnswer(value: unknown): value is QuizAnswer {
  return (
    isRecord(value) &&
    isNumber(value.id) &&
    isNumber(value.correct_index) &&
    isString(value.explanation) &&
    isListOf(value.sources, isSource) &&
    isSourceCheck(value.source_check) &&
    isListOf(value.doubts, isString)
  );
}

function isQuota(value: unknown): value is Quota {
  return (
    isRecord(value) &&
    isNumber(value.remaining) &&
    isNumber(value.limit) &&
    isString(value.resets_at) &&
    !Number.isNaN(Date.parse(value.resets_at)) &&
    typeof value.global_open === "boolean"
  );
}

const TONES: readonly unknown[] = ["info", "ok", "warn"];
const FALLBACK_REASONS: readonly unknown[] = ["limit", "unavailable"];
const MISSED_REASONS: readonly unknown[] = ["discarded", "failed", "skipped"];
const ITEM_KEYS: readonly unknown[] = MODES.flatMap((mode) =>
  DIFFICULTIES.map((difficulty): ItemKey => `${mode}-${difficulty}`),
);

function isItemKey(value: unknown): value is ItemKey {
  return ITEM_KEYS.includes(value);
}

function isPlannedItem(value: unknown): value is PlannedItem {
  return (
    isRecord(value) &&
    isItemKey(value.key) &&
    value.key === `${String(value.mode)}-${String(value.difficulty)}` &&
    (value.source === "live" || value.source === "bank")
  );
}

/** Exported for tests. */
export function isResearchEvent(value: unknown): value is ResearchEvent {
  if (!isRecord(value)) {
    return false;
  }
  switch (value.type) {
    case "plan":
      return isString(value.topic) && isListOf(value.items, isPlannedItem);
    case "log":
      return (
        (value.key === null || isItemKey(value.key)) &&
        isString(value.label) &&
        isString(value.detail) &&
        TONES.includes(value.tone) &&
        (value.verdict === null || (VERDICTS as readonly unknown[]).includes(value.verdict)) &&
        (value.confidence === null || isNumber(value.confidence)) &&
        isNumber(value.seconds)
      );
    case "rejected":
    case "error":
      return isString(value.message);
    case "fallback":
      return FALLBACK_REASONS.includes(value.reason) && isString(value.message);
    case "result":
      return (
        (isQuizQuestion(value.item) || isLearnItem(value.item)) &&
        // The item must be the one the key names.
        value.key === `${value.item.mode}-${value.item.difficulty}` &&
        (value.reveal_token === null || isString(value.reveal_token))
      );
    case "missed":
      return (
        isItemKey(value.key) && MISSED_REASONS.includes(value.reason) && isString(value.message)
      );
    default:
      return false;
  }
}

// --- Requests ---------------------------------------------------------------------------------

async function request(path: string, init: RequestInit = {}): Promise<unknown> {
  const response = await fetch(path, init);
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // An empty or non-JSON body is reported below with the status.
  }
  if (!response.ok) {
    const message = isRecord(body) && isString(body.error) ? body.error : `HTTP ${response.status}`;
    throw new ApiError(message, response.status);
  }
  return body;
}

function signalOnly(signal?: AbortSignal): RequestInit {
  return signal ? { signal } : {};
}

/** Every topic in the bank. */
export async function fetchTopics(signal?: AbortSignal): Promise<BankTopic[]> {
  const body = await request("/api/topics", signalOnly(signal));
  if (!isRecord(body) || !isListOf(body.topics, isBankTopic)) {
    throw new ApiError("/api/topics answered in an unexpected shape");
  }
  return body.topics;
}

/** A random published item; a quiz item comes without its answer. */
export async function fetchItem(
  topic: string,
  mode: Mode,
  difficulty: Difficulty,
  exclude: readonly number[],
  signal?: AbortSignal,
): Promise<Item> {
  const query = new URLSearchParams({ topic, mode, difficulty, exclude: exclude.join(",") });
  const body = await request(`/api/item?${query.toString()}`, signalOnly(signal));
  if (isQuizQuestion(body) || isLearnItem(body)) {
    return body;
  }
  throw new ApiError("/api/item answered in an unexpected shape");
}

/** The answer to a quiz item, fetched once the player has answered. A live item needs the
 * token its run gave out. */
export async function fetchAnswer(
  id: number,
  revealToken?: string,
  signal?: AbortSignal,
): Promise<QuizAnswer> {
  const query = new URLSearchParams({ id: String(id) });
  if (revealToken) {
    query.set("token", revealToken);
  }
  const body = await request(`/api/reveal?${query.toString()}`, signalOnly(signal));
  if (isQuizAnswer(body)) {
    return body;
  }
  throw new ApiError("/api/reveal answered in an unexpected shape");
}

/** How many live searches this visitor has left today, and whether live research is open. */
export async function fetchQuota(signal?: AbortSignal): Promise<Quota> {
  const body = await request("/api/quota", signalOnly(signal));
  if (isQuota(body)) {
    return body;
  }
  throw new ApiError("/api/quota answered in an unexpected shape");
}

/** Report an item. Resolves to true if this visitor had already reported it. */
export async function reportItem(id: number, reason: string): Promise<boolean> {
  const body = await request("/api/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, reason: reason.trim() || null }),
  });
  return isRecord(body) && body.already === true;
}

/** Split text into complete lines and the unfinished remainder (a stream can end mid-line). */
export function takeLines(buffer: string): [string[], string] {
  const parts = buffer.split("\n");
  const rest = parts.pop() ?? "";
  return [parts.filter((line) => line.trim() !== ""), rest];
}

/**
 * A live search: the explanation at `difficulty` and a question at each level, leaving out what
 * the bank already has. Each event the server streams is checked and passed to `onEvent` as it
 * arrives; the promise settles when the stream ends. Events of an unknown type are skipped, so
 * an older page keeps working against a newer server.
 */
export async function streamResearch(
  topic: string,
  difficulty: Difficulty,
  onEvent: (event: ResearchEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, difficulty }),
    ...signalOnly(signal),
  });
  if (!response.ok || !response.body) {
    let message = `HTTP ${response.status}`;
    try {
      const body: unknown = await response.json();
      if (isRecord(body) && isString(body.error)) {
        message = body.error;
      }
    } catch {
      // Keep the status as the message.
    }
    throw new ApiError(message, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const handle = (line: string) => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      return;
    }
    if (isResearchEvent(parsed)) {
      onEvent(parsed);
    }
  };
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const [lines, rest] = takeLines(buffer);
    lines.forEach(handle);
    buffer = rest;
    if (done) {
      break;
    }
  }
  if (buffer.trim()) {
    handle(buffer);
  }
}
