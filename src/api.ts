import {
  type BankTopic,
  DIFFICULTIES,
  type Difficulty,
  type Item,
  type LearnItem,
  type Mode,
  type OptionCheck,
  type QuizAnswer,
  type QuizQuestion,
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

function isBankTopic(value: unknown): value is BankTopic {
  return (
    isRecord(value) &&
    isString(value.name) &&
    (value.kind === "evergreen" || value.kind === "news") &&
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
    isListOf(value.options, isString)
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
    isSourceCheck(value.source_check)
  );
}

function isQuizAnswer(value: unknown): value is QuizAnswer {
  return (
    isRecord(value) &&
    isNumber(value.id) &&
    isNumber(value.correct_index) &&
    isString(value.explanation) &&
    isListOf(value.sources, isSource) &&
    isSourceCheck(value.source_check)
  );
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

/** The answer to a quiz item, fetched once the player has answered. */
export async function fetchAnswer(id: number, signal?: AbortSignal): Promise<QuizAnswer> {
  const body = await request(`/api/reveal?id=${id}`, signalOnly(signal));
  if (isQuizAnswer(body)) {
    return body;
  }
  throw new ApiError("/api/reveal answered in an unexpected shape");
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
