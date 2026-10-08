/**
 * The player's profile, kept in this browser only (no accounts, see DESIGN.md): all-time points
 * and answers, trophy tiers, finished and live runs, and what has been seen or played, so
 * questions and topics do not repeat. Every update is a pure function returning the new profile
 * and what it earned; reading and writing storage never throws.
 *
 * Version 2 (2026-10-08) replaced badges with tiered trophies. A version 1 profile is read once
 * and carried over: every badge becomes the same trophy at bronze. The version 1 entry is left
 * as it was.
 */
import { type AnswerScore, type Run } from "./game";
import {
  answerReached,
  type Award,
  learnReached,
  liveReached,
  rankUp,
  runReached,
  TIERS,
  type Tier,
  TROPHY_IDS,
  type TrophyId,
  type TrophyTiers,
  upgrades,
  withAwards,
} from "./trophies";
import type { Difficulty } from "./types";

export interface Profile {
  points: number;
  answered: number;
  correct: number;
  bestStreak: number;
  trophies: TrophyTiers;
  /** Quiz runs answered to the last question. */
  finishedRuns: number;
  /** Searches on the web page that made at least one live item (Web researcher). Named for the
   * single-item live runs it counted before 2026-10-08; kept so saved profiles carry over. */
  liveRuns: number;
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
  trophies: {},
  finishedRuns: 0,
  liveRuns: 0,
  seenItems: [],
  played: { easy: [], medium: [], hard: [] },
  learned: [],
};

export const SEEN_LIMIT = 500;
export const STORAGE_KEY = "cosmic-quiz:profile:v2";
export const V1_STORAGE_KEY = "cosmic-quiz:profile:v1";
const TROPHY_SET = new Set<string>(TROPHY_IDS);
const TIER_SET = new Set<string>(TIERS);

function remember<T>(list: readonly T[], value: T, limit: number = SEEN_LIMIT): T[] {
  return [value, ...list.filter((entry) => entry !== value)].slice(0, limit);
}

/** Apply what an update reached: new trophy tiers, then a rank-up if the points crossed one. */
function settle(before: Profile, after: Profile, reached: TrophyTiers): [Profile, Award[]] {
  const awards = upgrades(after.trophies, reached);
  const rank = rankUp(before.points, after.points);
  const profile = awards.length > 0 ? { ...after, trophies: withAwards(after.trophies, awards) } : after;
  return [profile, rank ? [...awards, rank] : awards];
}

/** After a quiz answer. `streak` includes this answer. */
export function afterAnswer(
  profile: Profile,
  difficulty: Difficulty,
  itemId: number,
  topic: string,
  score: AnswerScore,
  correct: boolean,
  streak: number,
): [Profile, Award[]] {
  const updated: Profile = {
    ...profile,
    points: profile.points + score.total,
    answered: profile.answered + 1,
    correct: profile.correct + (correct ? 1 : 0),
    bestStreak: Math.max(profile.bestStreak, streak),
    seenItems: remember(profile.seenItems, itemId),
    played: { ...profile.played, [difficulty]: remember(profile.played[difficulty], topic) },
  };
  return settle(profile, updated, answerReached(updated.correct, streak));
}

/** After the last question of a run, timed by the run clock. A run ended early changes nothing:
 * its answers were already counted one by one, and it earns no full-run trophies. */
export function afterRun(profile: Profile, run: Run, seconds: number): [Profile, Award[]] {
  const reached = runReached(run, seconds);
  if (Object.keys(reached).length === 0) {
    return [profile, []];
  }
  return settle(profile, { ...profile, finishedRuns: profile.finishedRuns + 1 }, reached);
}

/** After reading a LEARN item. */
export function afterLearn(profile: Profile, itemId: number, topic: string): [Profile, Award[]] {
  const updated: Profile = {
    ...profile,
    seenItems: remember(profile.seenItems, itemId),
    learned: remember(profile.learned, topic),
  };
  return settle(profile, updated, learnReached(updated.learned.length));
}

/** After a search on the web page made its first live item (published or held for review).
 * Called once per search, whatever it went on to make. */
export function afterLiveRun(profile: Profile): [Profile, Award[]] {
  const updated: Profile = { ...profile, liveRuns: profile.liveRuns + 1 };
  return settle(profile, updated, liveReached(updated.liveRuns));
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

function isRecord(value: unknown): value is object {
  return typeof value === "object" && value !== null;
}

function isTrophyId(value: string): value is TrophyId {
  return TROPHY_SET.has(value);
}

function isTier(value: unknown): value is Tier {
  return typeof value === "string" && TIER_SET.has(value);
}

/** Version 2 trophies: an object of trophy id to tier, keeping only valid pairs. */
function trophiesOf(value: unknown): TrophyTiers {
  const tiers: TrophyTiers = {};
  if (isRecord(value)) {
    for (const [id, tier] of Object.entries(value)) {
      if (isTrophyId(id) && isTier(tier)) {
        tiers[id] = tier;
      }
    }
  }
  return tiers;
}

/** Version 1 badges: a list of ids, each now the trophy of the same name at bronze. */
function trophiesFromBadges(value: unknown): TrophyTiers {
  const tiers: TrophyTiers = {};
  for (const id of stringList(value)) {
    if (isTrophyId(id)) {
      tiers[id] = "bronze";
    }
  }
  return tiers;
}

/** A saved entry as an object, or null if it is missing, corrupt or storage is blocked. */
function read(storage: Pick<Storage, "getItem">, key: string): object | null {
  try {
    const saved: unknown = JSON.parse(storage.getItem(key) ?? "null");
    return isRecord(saved) ? saved : null;
  } catch {
    return null;
  }
}

/** The fields both versions share, keeping every valid one. */
function common(saved: object): Omit<Profile, "trophies" | "finishedRuns" | "liveRuns"> {
  const count = (key: string) => {
    const value = field(saved, key);
    return isCount(value) ? value : 0;
  };
  const played = field(saved, "played");
  const playedFor = (difficulty: Difficulty) =>
    isRecord(played) ? stringList(field(played, difficulty)) : [];
  return {
    points: count("points"),
    answered: count("answered"),
    correct: Math.min(count("correct"), count("answered")),
    bestStreak: count("bestStreak"),
    seenItems: countList(field(saved, "seenItems")).slice(0, SEEN_LIMIT),
    played: { easy: playedFor("easy"), medium: playedFor("medium"), hard: playedFor("hard") },
    learned: stringList(field(saved, "learned")),
  };
}

/** The saved profile: version 2 if there is one, else version 1 carried over, else a fresh one
 * (also when storage is blocked, as in some private windows, or the entry is corrupt). */
export function loadProfile(storage: Pick<Storage, "getItem"> | undefined): Profile {
  if (!storage) {
    return EMPTY_PROFILE;
  }
  const saved = read(storage, STORAGE_KEY);
  if (saved) {
    const count = (key: string) => {
      const value = field(saved, key);
      return isCount(value) ? value : 0;
    };
    return {
      ...common(saved),
      trophies: trophiesOf(field(saved, "trophies")),
      finishedRuns: count("finishedRuns"),
      liveRuns: count("liveRuns"),
    };
  }
  const old = read(storage, V1_STORAGE_KEY);
  if (old) {
    return {
      ...common(old),
      trophies: trophiesFromBadges(field(old, "badges")),
      finishedRuns: 0,
      liveRuns: 0,
    };
  }
  return EMPTY_PROFILE;
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
