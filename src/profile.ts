/**
 * The player's profile, kept in this browser only (no accounts, see DESIGN.md): all-time points
 * and answers, badges, and what has been seen or played, so questions and topics do not repeat.
 * Every update is a pure function; reading and writing storage never throws.
 */
import {
  type AnswerScore,
  BADGES,
  type BadgeId,
  EXPLORER_TOPICS,
  type Run,
  runBadges,
} from "./game";
import type { Difficulty } from "./types";

export interface Profile {
  points: number;
  answered: number;
  correct: number;
  bestStreak: number;
  badges: BadgeId[];
  /** Item ids shown in this browser, newest first; sent to the API so they are skipped. */
  seenItems: number[];
  /** Topics played in QUIZ, per difficulty, newest first. */
  played: Record<Difficulty, string[]>;
  /** Topics read in LEARN. */
  learned: string[];
}

export const EMPTY_PROFILE: Profile = {
  points: 0,
  answered: 0,
  correct: 0,
  bestStreak: 0,
  badges: [],
  seenItems: [],
  played: { easy: [], medium: [], hard: [] },
  learned: [],
};

export const SEEN_LIMIT = 500;
const STORAGE_KEY = "cosmic-quiz:profile:v1";
const BADGE_IDS = new Set<string>(BADGES.map((badge) => badge.id));

function remember<T>(list: readonly T[], value: T, limit: number = SEEN_LIMIT): T[] {
  return [value, ...list.filter((entry) => entry !== value)].slice(0, limit);
}

function withBadges(profile: Profile, earned: readonly BadgeId[]): [Profile, BadgeId[]] {
  const fresh = earned.filter((id) => !profile.badges.includes(id));
  return fresh.length === 0 ? [profile, []] : [{ ...profile, badges: [...profile.badges, ...fresh] }, fresh];
}

/** After a quiz answer. Returns the new profile and any badges it just earned. */
export function afterAnswer(
  profile: Profile,
  difficulty: Difficulty,
  itemId: number,
  topic: string,
  score: AnswerScore,
  correct: boolean,
  streak: number,
): [Profile, BadgeId[]] {
  const updated: Profile = {
    ...profile,
    points: profile.points + score.total,
    answered: profile.answered + 1,
    correct: profile.correct + (correct ? 1 : 0),
    bestStreak: Math.max(profile.bestStreak, streak),
    seenItems: remember(profile.seenItems, itemId),
    played: { ...profile.played, [difficulty]: remember(profile.played[difficulty], topic) },
  };
  const earned: BadgeId[] = [];
  if (correct) earned.push("first-light");
  if (streak >= 5) earned.push("hot-streak");
  return withBadges(updated, earned);
}

/** After a finished run: the run's badges. */
export function afterRun(profile: Profile, run: Run, seconds: number): [Profile, BadgeId[]] {
  return withBadges(profile, runBadges(run, seconds));
}

/** After reading a LEARN item. */
export function afterLearn(profile: Profile, itemId: number, topic: string): [Profile, BadgeId[]] {
  const updated: Profile = {
    ...profile,
    seenItems: remember(profile.seenItems, itemId),
    learned: remember(profile.learned, topic),
  };
  return withBadges(updated, updated.learned.length >= EXPLORER_TOPICS ? ["explorer"] : []);
}

// --- Storage ----------------------------------------------------------------------------------

function isCount(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function countList(value: unknown): number[] {
  return Array.isArray(value) ? value.filter(isCount) : [];
}

function field(source: object, key: string): unknown {
  return (source as Record<string, unknown>)[key];
}

/** The saved profile, keeping every valid field; a fresh one if there is none or storage is
 * blocked (private windows). */
export function loadProfile(storage: Pick<Storage, "getItem"> | undefined): Profile {
  let saved: unknown;
  try {
    saved = JSON.parse(storage?.getItem(STORAGE_KEY) ?? "null");
  } catch {
    return EMPTY_PROFILE;
  }
  if (typeof saved !== "object" || saved === null) {
    return EMPTY_PROFILE;
  }
  const count = (key: string) => {
    const value = field(saved, key);
    return isCount(value) ? value : 0;
  };
  const played = field(saved, "played");
  const playedFor = (difficulty: Difficulty) =>
    typeof played === "object" && played !== null ? stringList(field(played, difficulty)) : [];
  return {
    points: count("points"),
    answered: count("answered"),
    correct: Math.min(count("correct"), count("answered")),
    bestStreak: count("bestStreak"),
    badges: stringList(field(saved, "badges")).filter((id): id is BadgeId => BADGE_IDS.has(id)),
    seenItems: countList(field(saved, "seenItems")).slice(0, SEEN_LIMIT),
    played: { easy: playedFor("easy"), medium: playedFor("medium"), hard: playedFor("hard") },
    learned: stringList(field(saved, "learned")),
  };
}

/** Save the profile; silently skipped when storage is blocked or full. */
export function saveProfile(storage: Pick<Storage, "setItem"> | undefined, profile: Profile) {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(profile));
  } catch {
    // The profile is a convenience; the game works without it.
  }
}

/** The browser's localStorage, or undefined where accessing it throws. */
export function browserStorage(): Storage | undefined {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}
