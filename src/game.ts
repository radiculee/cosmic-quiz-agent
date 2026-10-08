/**
 * The game rules: points, streaks, the run clock's speed bonus, ranks, run lengths and how a run
 * picks its topics. Pure functions, so every rule is unit-tested (game.test.ts). Trophies are in
 * trophies.ts.
 */
import { isPlayable } from "./topics";
import type { BankTopic, Difficulty } from "./types";

/** A quiz run is 10, 30 or 60 questions, each on a different topic. */
export const RUN_LENGTHS = [10, 30, 60] as const;
export type RunLength = (typeof RUN_LENGTHS)[number];

// --- Points -----------------------------------------------------------------------------------

export const BASE_POINTS: Record<Difficulty, number> = { easy: 100, medium: 200, hard: 300 };
/** Answering within this many seconds earns the speed bonus. */
export const SPEED_BONUS_SECONDS = 15;
const SPEED_BONUS_SHARE = 0.25;

/** x1.5 from 3 correct in a row, x2 from 5. */
export function streakMultiplier(streak: number): number {
  if (streak >= 5) return 2;
  if (streak >= 3) return 1.5;
  return 1;
}

export interface AnswerScore {
  base: number;
  multiplier: number;
  speedBonus: number;
  total: number;
}

/** Points for one answer. `streak` is the streak including this answer. */
export function scoreAnswer(
  difficulty: Difficulty,
  correct: boolean,
  streak: number,
  seconds: number,
): AnswerScore {
  if (!correct) {
    return { base: 0, multiplier: 1, speedBonus: 0, total: 0 };
  }
  const base = BASE_POINTS[difficulty];
  const multiplier = streakMultiplier(streak);
  const speedBonus = seconds <= SPEED_BONUS_SECONDS ? Math.round(base * SPEED_BONUS_SHARE) : 0;
  return { base, multiplier, speedBonus, total: Math.round(base * multiplier) + speedBonus };
}

// --- Ranks ------------------------------------------------------------------------------------

export const RANKS = [
  { name: "Stargazer", points: 0 },
  { name: "Cadet", points: 1_000 },
  { name: "Navigator", points: 3_000 },
  { name: "Astronomer", points: 7_500 },
  { name: "Astrophysicist", points: 15_000 },
  { name: "Cosmologist", points: 30_000 },
] as const;

export type RankName = (typeof RANKS)[number]["name"];

export interface RankProgress {
  name: RankName;
  next: { name: RankName; points: number } | null;
  /** Share of the way from this rank to the next, 0 to 1 (1 at the top rank). */
  progress: number;
}

export function rankFor(points: number): RankProgress {
  let index = 0;
  RANKS.forEach((rank, i) => {
    if (points >= rank.points) index = i;
  });
  const current = RANKS[index] ?? RANKS[0];
  const next = RANKS[index + 1];
  if (!next) {
    return { name: current.name, next: null, progress: 1 };
  }
  const progress = (points - current.points) / (next.points - current.points);
  return { name: current.name, next: { name: next.name, points: next.points }, progress };
}

// --- Runs -------------------------------------------------------------------------------------

export interface AnswerResult {
  itemId: number;
  topic: string;
  correct: boolean;
  seconds: number;
  score: AnswerScore;
}

export interface Run {
  difficulty: Difficulty;
  topics: string[];
  results: AnswerResult[];
  streak: number;
  bestStreak: number;
  points: number;
  /** True when the bank had too few unplayed topics, so some are repeats. */
  repeats: boolean;
}

function shuffled<T>(items: readonly T[], random: () => number): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    const a = copy[i];
    const b = copy[j];
    if (a !== undefined && b !== undefined) {
      copy[i] = b;
      copy[j] = a;
    }
  }
  return copy;
}

/** How many topics have a quiz question at this difficulty: the longest run the bank can fill
 * without repeating a topic. */
export function quizTopicCount(topics: readonly BankTopic[], difficulty: Difficulty): number {
  return topics.filter((topic) => isPlayable(topic, "quiz", difficulty)).length;
}

/**
 * The run length to play: `wanted` if the bank has that many topics at the difficulty, otherwise
 * the longest one it can fill, or null if it cannot fill even the shortest.
 */
export function availableLength(topicCount: number, wanted: RunLength): RunLength | null {
  const fitting = RUN_LENGTHS.filter((length) => length <= topicCount);
  if (fitting.includes(wanted)) {
    return wanted;
  }
  return fitting.at(-1) ?? null;
}

/**
 * Why some run lengths cannot be picked at a difficulty, or null if all can: "HARD: 23 of 30
 * questions so far. 30 and 60 open as the bank grows."
 */
export function lengthNote(difficulty: Difficulty, topicCount: number): string | null {
  const closed = RUN_LENGTHS.filter((length) => length > topicCount);
  const first = closed[0];
  const last = closed.at(-1);
  if (first === undefined || last === undefined) {
    return null;
  }
  const lengths =
    closed.length === 1 ? String(first) : `${closed.slice(0, -1).join(", ")} and ${last}`;
  const verb = closed.length === 1 ? "opens" : "open";
  return (
    `${difficulty.toUpperCase()}: ${topicCount} of ${first} questions so far. ` +
    `${lengths} ${verb} as the bank grows.`
  );
}

/**
 * The topics for a new QUIZ run of `length` questions: topics this browser has not played at
 * this difficulty first, in random order, then (only if needed) ones it has. No topic appears
 * twice, so a run is shorter than `length` only if the bank has fewer topics.
 */
export function planRun(
  topics: readonly BankTopic[],
  difficulty: Difficulty,
  length: RunLength,
  played: readonly string[],
  random: () => number = Math.random,
): Run {
  const playable = topics.filter((topic) => isPlayable(topic, "quiz", difficulty));
  const playedSet = new Set(played);
  const fresh = shuffled(
    playable.filter((topic) => !playedSet.has(topic.name)),
    random,
  );
  const seen = shuffled(
    playable.filter((topic) => playedSet.has(topic.name)),
    random,
  );
  const chosen = [...fresh, ...seen].slice(0, length).map((topic) => topic.name);
  return {
    difficulty,
    topics: chosen,
    results: [],
    streak: 0,
    bestStreak: 0,
    points: 0,
    repeats: chosen.some((name) => playedSet.has(name)),
  };
}

/** The run after one answer, and the points that answer earned. */
export function answerInRun(
  run: Run,
  itemId: number,
  topic: string,
  correct: boolean,
  seconds: number,
): { run: Run; score: AnswerScore } {
  const streak = correct ? run.streak + 1 : 0;
  const score = scoreAnswer(run.difficulty, correct, streak, seconds);
  return {
    score,
    run: {
      ...run,
      results: [...run.results, { itemId, topic, correct, seconds, score }],
      streak,
      bestStreak: Math.max(run.bestStreak, streak),
      points: run.points + score.total,
    },
  };
}

/** Every question answered. A run the player ended early is not finished, so it earns no
 * full-run trophies (its points are already counted, answer by answer). */
export function isRunFinished(run: Run): boolean {
  return run.results.length >= run.topics.length;
}

export function runCorrect(run: Run): number {
  return run.results.filter((result) => result.correct).length;
}

/** Share of the answered questions that were right, 0 when none were answered. */
export function runAccuracy(run: Run): number {
  return run.results.length === 0 ? 0 : runCorrect(run) / run.results.length;
}

/** "1:23.4" from milliseconds. */
export function formatClock(ms: number): string {
  const tenths = Math.floor(ms / 100);
  const minutes = Math.floor(tenths / 600);
  const seconds = Math.floor((tenths % 600) / 10);
  return `${minutes}:${String(seconds).padStart(2, "0")}.${tenths % 10}`;
}
