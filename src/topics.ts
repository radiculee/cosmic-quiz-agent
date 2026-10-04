import type { BankTopic, Difficulty, Mode } from "./types";

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

/**
 * Suggestions for what the player has typed: topics playable at this mode and difficulty whose
 * name contains the query, those starting with it first, then alphabetical.
 */
export function suggest(
  topics: readonly BankTopic[],
  query: string,
  mode: Mode,
  difficulty: Difficulty,
): BankTopic[] {
  const wanted = normalize(query);
  return topics
    .filter((topic) => isPlayable(topic, mode, difficulty))
    .filter((topic) => normalize(topic.name).includes(wanted))
    .sort((a, b) => {
      const aStarts = normalize(a.name).startsWith(wanted) ? 0 : 1;
      const bStarts = normalize(b.name).startsWith(wanted) ? 0 : 1;
      return aStarts - bStarts || a.name.localeCompare(b.name);
    })
    .slice(0, MAX_SUGGESTIONS);
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
