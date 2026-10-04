/**
 * The game rules: points, streaks, the run clock's speed bonus, ranks, badges and how a run
 * picks its topics. Pure functions, so every rule is unit-tested (game.test.ts).
 */
import { isPlayable } from "./topics";
import type { BankTopic, Difficulty } from "./types";

export const RUN_LENGTH = 10;

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

// --- Badges -----------------------------------------------------------------------------------

export const BADGES = [
  { id: "first-light", name: "First light", how: "Answer a question correctly." },
  { id: "hot-streak", name: "Hot streak", how: "Answer 5 questions in a row correctly." },
  { id: "perfect-run", name: "Perfect run", how: "Finish a run with 10 out of 10." },
  { id: "hard-mode", name: "Hard mode", how: "Finish a perfect run on HARD." },
  { id: "speed-runner", name: "Speed runner", how: "Finish a 10-question run in under 2 minutes." },
  { id: "explorer", name: "Explorer", how: "Learn 10 different topics in LEARN mode." },
] as const;

export type BadgeId = (typeof BADGES)[number]["id"];

export const SPEED_RUNNER_SECONDS = 120;
export const EXPLORER_TOPICS = 10;

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

/**
 * The topics for a new QUIZ run: the chosen topic first, then topics this browser has not played
 * at this difficulty, then (only if needed) ones it has. No topic appears twice.
 */
export function planRun(
  topics: readonly BankTopic[],
  difficulty: Difficulty,
  first: string,
  played: readonly string[],
  random: () => number = Math.random,
): Run {
  const playable = topics.filter((topic) => isPlayable(topic, "quiz", difficulty));
  const others = playable.filter((topic) => topic.name !== first);
  const playedSet = new Set(played);
  const fresh = shuffled(
    others.filter((topic) => !playedSet.has(topic.name)),
    random,
  );
  const seen = shuffled(
    others.filter((topic) => playedSet.has(topic.name)),
    random,
  );
  const length = Math.min(RUN_LENGTH, playable.length);
  const rest = [...fresh, ...seen].slice(0, Math.max(0, length - 1)).map((topic) => topic.name);
  const chosen = [first, ...rest];
  const firstIsRepeat = playedSet.has(first);
  return {
    difficulty,
    topics: chosen,
    results: [],
    streak: 0,
    bestStreak: 0,
    points: 0,
    repeats: firstIsRepeat || rest.some((name) => playedSet.has(name)),
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

export function isRunFinished(run: Run): boolean {
  return run.results.length >= run.topics.length;
}

export function runCorrect(run: Run): number {
  return run.results.filter((result) => result.correct).length;
}

/** Badges a finished run earns. */
export function runBadges(run: Run, seconds: number): BadgeId[] {
  const perfect = run.topics.length === RUN_LENGTH && runCorrect(run) === RUN_LENGTH;
  const earned: BadgeId[] = [];
  if (perfect) earned.push("perfect-run");
  if (perfect && run.difficulty === "hard") earned.push("hard-mode");
  if (run.topics.length === RUN_LENGTH && seconds < SPEED_RUNNER_SECONDS) {
    earned.push("speed-runner");
  }
  return earned;
}

/** "1:23.4" from milliseconds. */
export function formatClock(ms: number): string {
  const tenths = Math.floor(ms / 100);
  const minutes = Math.floor(tenths / 600);
  const seconds = Math.floor((tenths % 600) / 10);
  return `${minutes}:${String(seconds).padStart(2, "0")}.${tenths % 10}`;
}
