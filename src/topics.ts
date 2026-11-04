import {
  type BankTopic,
  DIFFICULTIES,
  type Difficulty,
  type Mode,
  type TopicFact,
  type TopicImage,
} from "./types";

export const MAX_SUGGESTIONS = 8;

const THE = "the ";

function normalize(text: string): string {
  return text.trim().replace(/\s+/g, " ").toLowerCase();
}

/**
 * What two topic names are compared by: ignoring case, extra spaces and one leading "The", so
 * "The Big Bang" and "Big Bang" are one topic. Stored and shown names keep their "The".
 *
 * `topic_key` in agent/bank.py is the same rule, and both test files hold the same cases. "The"
 * alone has nothing after it, so it stays "the": it cannot become empty and match everything.
 */
export function topicKey(name: string): string {
  const tidied = normalize(name);
  return tidied.startsWith(THE) ? tidied.slice(THE.length) : tidied;
}

/**
 * The bank topic with this name, by `topicKey`, if there is one. The name as typed wins if the
 * bank has both spellings, as in `topic_named` (agent/bank.py).
 */
export function findTopic(topics: readonly BankTopic[], name: string): BankTopic | undefined {
  const typed = normalize(name);
  const wanted = topicKey(name);
  if (!wanted) {
    return undefined;
  }
  return (
    topics.find((topic) => normalize(topic.name) === typed) ??
    topics.find((topic) => topicKey(topic.name) === wanted)
  );
}

/** Whether a topic has a published item at this mode and difficulty. */
export function isPlayable(topic: BankTopic, mode: Mode, difficulty: Difficulty): boolean {
  return topic[mode].includes(difficulty);
}

/** Topics whose name contains the query (every one for an empty query): those starting with it
 * first, then alphabetical. "Starting with it" ignores a leading "The" on either side, but the
 * query keeps its "The" for "contains": "the m" finds "Mars" and "The Moon", not "Comets". */
function matching(topics: readonly BankTopic[], query: string): BankTopic[] {
  const typed = normalize(query);
  const wanted = topicKey(query);
  const starts = (name: string): boolean =>
    normalize(name).startsWith(typed) || topicKey(name).startsWith(wanted);
  return topics
    .filter((topic) => normalize(topic.name).includes(typed) || starts(topic.name))
    .sort((a, b) => {
      const aStarts = starts(a.name) ? 0 : 1;
      const bStarts = starts(b.name) ? 0 : 1;
      return aStarts - bStarts || a.name.localeCompare(b.name);
    });
}

/** Topics playable at this mode and difficulty whose name contains the query. */
export function filterTopics(
  topics: readonly BankTopic[],
  query: string,
  mode: Mode,
  difficulty: Difficulty,
): BankTopic[] {
  return matching(
    topics.filter((topic) => isPlayable(topic, mode, difficulty)),
    query,
  );
}

/** Suggestions for what the player has typed: the first few of `filterTopics`. */
export function suggest(
  topics: readonly BankTopic[],
  query: string,
  mode: Mode,
  difficulty: Difficulty,
): BankTopic[] {
  return filterTopics(topics, query, mode, difficulty).slice(0, MAX_SUGGESTIONS);
}

/** Suggestions from every topic in the bank, whatever it has: the web page's topic box, where a
 * bank topic is shown free and only its gaps are researched. */
export function suggestAny(topics: readonly BankTopic[], query: string): BankTopic[] {
  return matching(topics, query).slice(0, MAX_SUGGESTIONS);
}

/**
 * A random topic playable at this mode and difficulty: never the current one if avoidable, and
 * one not in `avoid` (already played or learned) while any is left.
 */
export function randomTopic(
  topics: readonly BankTopic[],
  mode: Mode,
  difficulty: Difficulty,
  current: string,
  random: () => number = Math.random,
  avoid: readonly string[] = [],
): BankTopic | undefined {
  const playable = topics.filter((topic) => isPlayable(topic, mode, difficulty));
  const others = playable.filter((topic) => topicKey(topic.name) !== topicKey(current));
  const avoided = new Set(avoid.map(topicKey));
  const fresh = others.filter((topic) => !avoided.has(topicKey(topic.name)));
  const pool = fresh.length > 0 ? fresh : others.length > 0 ? others : playable;
  return pool[Math.floor(random() * pool.length)];
}

export type TopicStatus =
  | { kind: "empty" }
  | { kind: "ready"; topic: BankTopic }
  | { kind: "unknown" }
  | { kind: "elsewhere"; topic: BankTopic; difficulties: Difficulty[] };

/** What the typed topic means at this mode and difficulty, for the GO button and the hint. */
export function topicStatus(
  topics: readonly BankTopic[],
  query: string,
  mode: Mode,
  difficulty: Difficulty,
): TopicStatus {
  if (!normalize(query)) {
    return { kind: "empty" };
  }
  const topic = findTopic(topics, query);
  if (!topic) {
    return { kind: "unknown" };
  }
  if (isPlayable(topic, mode, difficulty)) {
    return { kind: "ready", topic };
  }
  return { kind: "elsewhere", topic, difficulties: topic[mode] };
}

export type SearchStatus =
  | { kind: "empty" }
  | { kind: "new" }
  | { kind: "partial"; topic: BankTopic; missing: number }
  | { kind: "complete"; topic: BankTopic };

/**
 * What a live search for the typed topic would do (agent/ondemand.py `plan_search`): it makes a
 * question and an explanation at each level, leaving out what the bank has. "complete" is free
 * and does not use a search. The bank lists only complete topics (api/topics.py), so "partial"
 * is for a topic loaded before one of its items was hidden.
 */
export function searchStatus(topics: readonly BankTopic[], query: string): SearchStatus {
  if (!normalize(query)) {
    return { kind: "empty" };
  }
  const topic = findTopic(topics, query);
  if (!topic) {
    return { kind: "new" };
  }
  const missing = (["learn", "quiz"] as const).reduce(
    (count, mode) => count + DIFFICULTIES.filter((level) => !isPlayable(topic, mode, level)).length,
    0,
  );
  return missing === 0 ? { kind: "complete", topic } : { kind: "partial", topic, missing };
}

/** The categories a fact card can have, as the Curator's image fill assigns them
 * (curator/images.py CATEGORIES). "space" is for a topic none of them fits. */
export const FACT_CATEGORIES = [
  "black-hole",
  "galaxy",
  "cosmology",
  "particle",
  "mission",
  "star",
  "planet",
  "small-body",
  "space",
] as const;
export type FactCategory = (typeof FACT_CATEGORIES)[number];

/** Where a topic's pictures live on this site. Anything else is refused, so a bad row can never
 * make a visitor's browser contact another host. */
const MEDIA_PREFIX = "/media/";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isLocalMedia(value: unknown): value is string {
  return isString(value) && value.startsWith(MEDIA_PREFIX) && !value.includes("..");
}

function isTopicImage(value: unknown): value is TopicImage {
  return (
    isRecord(value) &&
    isLocalMedia(value.src) &&
    (value.preview === undefined || isLocalMedia(value.preview)) &&
    typeof value.width === "number" &&
    typeof value.height === "number" &&
    value.width > 0 &&
    value.height > 0 &&
    isString(value.credit) &&
    isString(value.licence) &&
    isString(value.page_url) &&
    (value.source === "wikipedia" || value.source === "nasa")
  );
}

function isTopicFact(value: unknown): value is TopicFact {
  return isRecord(value) && isString(value.category) && isString(value.text);
}

export type TopicVisual =
  | { kind: "image"; image: TopicImage }
  | { kind: "fact"; fact: TopicFact; category: FactCategory }
  | { kind: "none" };

/**
 * What a topic card draws: the picture if the topic has a complete one, else its fact, else
 * nothing (the Curator's image fill has not reached it, or the bank has no pictures yet).
 * `/api/topics` is checked only for its older fields (src/api.ts), so the new ones are checked
 * here; a malformed picture counts as none rather than breaking the card.
 */
export function topicVisual(topic: BankTopic): TopicVisual {
  if (isTopicImage(topic.image)) {
    return { kind: "image", image: topic.image };
  }
  if (isTopicFact(topic.fact)) {
    const category = FACT_CATEGORIES.find((known) => known === topic.fact?.category) ?? "space";
    return { kind: "fact", fact: topic.fact, category };
  }
  return { kind: "none" };
}
