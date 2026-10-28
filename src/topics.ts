import { type BankTopic, DIFFICULTIES, type Difficulty, type Mode } from "./types";

export const MAX_SUGGESTIONS = 8;

function normalize(text: string): string {
  return text.trim().replace(/\s+/g, " ").toLowerCase();
}

/** The bank topic with this name, ignoring case and extra spaces, if there is one. */
export function findTopic(topics: readonly BankTopic[], name: string): BankTopic | undefined {
  const wanted = normalize(name);
  return wanted ? topics.find((topic) => normalize(topic.name) === wanted) : undefined;
}

/** Whether a topic has a published item at this mode and difficulty. */
export function isPlayable(topic: BankTopic, mode: Mode, difficulty: Difficulty): boolean {
  return topic[mode].includes(difficulty);
}

/** Topics whose name contains the query (every one for an empty query): those starting with it
 * first, then alphabetical. */
function matching(topics: readonly BankTopic[], query: string): BankTopic[] {
  const wanted = normalize(query);
  return topics
    .filter((topic) => normalize(topic.name).includes(wanted))
    .sort((a, b) => {
      const aStarts = normalize(a.name).startsWith(wanted) ? 0 : 1;
      const bStarts = normalize(b.name).startsWith(wanted) ? 0 : 1;
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
  const others = playable.filter((topic) => normalize(topic.name) !== normalize(current));
  const avoided = new Set(avoid.map(normalize));
  const fresh = others.filter((topic) => !avoided.has(normalize(topic.name)));
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
