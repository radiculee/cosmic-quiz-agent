/**
 * The player's profile: all-time points and answers, trophy tiers, finished and live runs, and
 * what has been seen or played, so questions and topics do not repeat. Every update is a pure
 * function returning the new profile and what it earned; reading and writing storage never
 * throws.
 *
 * Version 2 (2026-10-08) replaced badges with tiered trophies. A version 1 profile is read once
 * and carried over: every badge becomes the same trophy at bronze. The version 1 entry is left
 * as it was.
 *
 * Version 3 (2026-11-01) adds optional accounts (docs/SESSIONS.md, Decisions, 2026-10-30). Each
 * update also records what happened as an event with its own id, in `log`, so an account can
 * rebuild the profile by replaying its history through these same updates (`replay`). A guest's
 * browser keeps its events; a version 2 profile, which has none, is carried over as a baseline.
 * On sign-in the guest's baseline and events are added to the account (inserting a row that is
 * already there does nothing, so adding twice changes nothing), and only then does the browser
 * start a fresh guest with a new guest id. The version 2 entry is left as it was.
 */
import { type AnswerScore, RUN_LENGTHS, type Run, runCorrect } from "./game";
import {
  answerReached,
  type Award,
  learnReached,
  liveReached,
  rankUp,
  runReached,
  TIERS,
  type Tier,
  tierIndex,
  TROPHY_IDS,
  type TrophyId,
  type TrophyTiers,
  upgrades,
  withAwards,
} from "./trophies";
import type { Difficulty } from "./types";

/** When something happened, and its id: a UUID made in the browser, the row's key on the server. */
export interface Stamp {
  id: string;
  /** ISO 8601. */
  at: string;
}

export interface AnswerEvent extends Stamp {
  kind: "answer";
  itemId: number;
  topic: string;
  difficulty: Difficulty;
  correct: boolean;
  /** The option picked and the seconds taken, when the page passes them. */
  choice: number | null;
  seconds: number | null;
  /** The streak including this answer, and the points it earned. */
  streak: number;
  points: number;
}

export interface ReadEvent extends Stamp {
  kind: "read";
  itemId: number;
  topic: string;
}

export interface RunEvent extends Stamp {
  kind: "run";
  difficulty: Difficulty;
  length: number;
  correct: number;
  seconds: number;
}

export interface SearchEvent extends Stamp {
  kind: "search";
}

export type ProfileEvent = AnswerEvent | ReadEvent | RunEvent | SearchEvent;

/** What the game shows: totals, trophies, and what has been seen or played. */
export interface Totals {
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

export interface Profile extends Totals {
  /** What happened, oldest first, not yet stored anywhere else: a guest's history, or a
   * signed-in player's newest events until they are queued for the server. */
  log: ProfileEvent[];
}

export const EMPTY_TOTALS: Totals = {
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

export const EMPTY_PROFILE: Profile = { ...EMPTY_TOTALS, log: [] };

export const SEEN_LIMIT = 500;
export const STORAGE_KEY = "cosmic-quiz:profile:v2";
export const V1_STORAGE_KEY = "cosmic-quiz:profile:v1";
export const GUEST_KEY = "cosmic-quiz:profile:v3";
/** A signed-in player's cache in this browser, one per account: this plus ":" and the user id. */
export const ACCOUNT_KEY = "cosmic-quiz:account:v1";
/** A guest keeps at most this many events; older ones are folded into the baseline. */
export const GUEST_LOG_LIMIT = 5_000;
const TROPHY_SET = new Set<string>(TROPHY_IDS);
const TIER_SET = new Set<string>(TIERS);
const DIFFICULTIES: readonly Difficulty[] = ["easy", "medium", "hard"];

let lastStampMs = 0;

/** A new id and the time now, for an event. Times only go up, so two events in the same
 * millisecond (an answer and the end of its run) still replay in the order they happened. */
export function newStamp(): Stamp {
  const ms = Math.max(Date.now(), lastStampMs + 1);
  lastStampMs = ms;
  return { id: crypto.randomUUID(), at: new Date(ms).toISOString() };
}

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

/** The option picked and the seconds taken, for the record (not used in scoring here). */
export interface AnswerDetail {
  choice?: number;
  seconds?: number;
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
  detail: AnswerDetail = {},
  stamp: Stamp = newStamp(),
): [Profile, Award[]] {
  const event: AnswerEvent = {
    ...stampOf(stamp),
    kind: "answer",
    itemId,
    topic,
    difficulty,
    correct,
    choice: detail.choice ?? null,
    seconds: detail.seconds ?? null,
    streak,
    points: score.total,
  };
  const updated: Profile = {
    ...profile,
    points: profile.points + score.total,
    answered: profile.answered + 1,
    correct: profile.correct + (correct ? 1 : 0),
    bestStreak: Math.max(profile.bestStreak, streak),
    seenItems: remember(profile.seenItems, itemId),
    played: { ...profile.played, [difficulty]: remember(profile.played[difficulty], topic) },
    log: [...profile.log, event],
  };
  return settle(profile, updated, answerReached(updated.correct, streak));
}

/** After the last question of a run, timed by the run clock. A run ended early changes nothing:
 * its answers were already counted one by one, and it earns no full-run trophies. */
export function afterRun(
  profile: Profile,
  run: Run,
  seconds: number,
  stamp: Stamp = newStamp(),
): [Profile, Award[]] {
  const reached = runReached(run, seconds);
  if (Object.keys(reached).length === 0) {
    return [profile, []];
  }
  const event: RunEvent = {
    ...stampOf(stamp),
    kind: "run",
    difficulty: run.difficulty,
    length: run.topics.length,
    correct: runCorrect(run),
    seconds,
  };
  // Every run the game plans is 10, 30 or 60 questions, the lengths the server accepts.
  const recorded = (RUN_LENGTHS as readonly number[]).includes(event.length);
  const updated: Profile = {
    ...profile,
    finishedRuns: profile.finishedRuns + 1,
    log: recorded ? [...profile.log, event] : profile.log,
  };
  return settle(profile, updated, reached);
}

/** After reading a LEARN item. */
export function afterLearn(
  profile: Profile,
  itemId: number,
  topic: string,
  stamp: Stamp = newStamp(),
): [Profile, Award[]] {
  const event: ReadEvent = { ...stampOf(stamp), kind: "read", itemId, topic };
  const updated: Profile = {
    ...profile,
    seenItems: remember(profile.seenItems, itemId),
    learned: remember(profile.learned, topic),
    log: [...profile.log, event],
  };
  return settle(profile, updated, learnReached(updated.learned.length));
}

/** After a search on the web page made its first live item (published or held for review).
 * Called once per search, whatever it went on to make. */
export function afterLiveRun(profile: Profile, stamp: Stamp = newStamp()): [Profile, Award[]] {
  const event: SearchEvent = { ...stampOf(stamp), kind: "search" };
  const updated: Profile = {
    ...profile,
    liveRuns: profile.liveRuns + 1,
    log: [...profile.log, event],
  };
  return settle(profile, updated, liveReached(updated.liveRuns));
}

function stampOf(stamp: Stamp): Stamp {
  return { id: stamp.id, at: stamp.at };
}

// --- Replay -----------------------------------------------------------------------------------

/** A profile's totals, without its log. */
export function totalsOf(profile: Profile): Totals {
  const { log: _log, ...totals } = profile;
  return totals;
}

function joined<T>(lists: readonly (readonly T[])[], limit?: number): T[] {
  const seen = new Set<T>();
  const all: T[] = [];
  for (const list of lists) {
    for (const value of list) {
      if (!seen.has(value)) {
        seen.add(value);
        all.push(value);
      }
    }
  }
  return limit === undefined ? all : all.slice(0, limit);
}

/** Several baselines as one: counts add up, the best streak and each trophy's tier are the
 * highest, and the lists are joined without repeats. */
export function combineBaselines(baselines: readonly Totals[]): Totals {
  const sum = (pick: (totals: Totals) => number) =>
    baselines.reduce((total, baseline) => total + pick(baseline), 0);
  const trophies: TrophyTiers = {};
  for (const baseline of baselines) {
    for (const id of TROPHY_IDS) {
      const tier = baseline.trophies[id];
      if (tier && tierIndex(tier) > tierIndex(trophies[id])) {
        trophies[id] = tier;
      }
    }
  }
  const played = (difficulty: Difficulty) => joined(baselines.map((b) => b.played[difficulty]));
  return {
    points: sum((b) => b.points),
    answered: sum((b) => b.answered),
    correct: sum((b) => b.correct),
    bestStreak: baselines.reduce((best, b) => Math.max(best, b.bestStreak), 0),
    trophies,
    finishedRuns: sum((b) => b.finishedRuns),
    liveRuns: sum((b) => b.liveRuns),
    seenItems: joined(
      baselines.map((b) => b.seenItems),
      SEEN_LIMIT,
    ),
    played: { easy: played("easy"), medium: played("medium"), hard: played("hard") },
    learned: joined(baselines.map((b) => b.learned)),
  };
}

/** A finished run as runReached reads it: its length, difficulty and how many were right. */
function asRun(event: RunEvent): Run {
  const zero: AnswerScore = { base: 0, multiplier: 1, speedBonus: 0, total: 0 };
  return {
    difficulty: event.difficulty,
    topics: Array.from({ length: event.length }, () => ""),
    results: Array.from({ length: event.length }, (_, index) => ({
      itemId: 0,
      topic: "",
      correct: index < event.correct,
      seconds: 0,
      score: zero,
    })),
    streak: 0,
    bestStreak: 0,
    points: 0,
    repeats: false,
  };
}

/** One event applied through the update that recorded it. */
function apply(profile: Profile, event: ProfileEvent): Profile {
  switch (event.kind) {
    case "answer": {
      // Only the total is read; the stored points are the ones the game awarded at the time.
      const score: AnswerScore = { base: 0, multiplier: 1, speedBonus: 0, total: event.points };
      const { difficulty, itemId, topic, correct, streak } = event;
      return afterAnswer(profile, difficulty, itemId, topic, score, correct, streak, {}, event)[0];
    }
    case "read":
      return afterLearn(profile, event.itemId, event.topic, event)[0];
    case "run":
      return afterRun(profile, asRun(event), event.seconds, event)[0];
    case "search":
      return afterLiveRun(profile, event)[0];
  }
}

/** Events in the order they happened, each once (by id). */
export function inOrder(events: readonly ProfileEvent[]): ProfileEvent[] {
  const unique = new Map<string, ProfileEvent>();
  for (const event of events) {
    if (!unique.has(event.id)) {
      unique.set(event.id, event);
    }
  }
  return [...unique.values()].sort((a, b) =>
    a.at === b.at ? (a.id < b.id ? -1 : a.id > b.id ? 1 : 0) : a.at < b.at ? -1 : 1,
  );
}

/**
 * What a history adds up to: its baselines, then every event in the order it happened (each
 * once), through the same updates the game uses, so points, streaks, trophies and the topics
 * played, read and seen come out as they would have in one browser. No award is shown for a
 * replay.
 */
export function replay(baselines: readonly Totals[], events: readonly ProfileEvent[]): Totals {
  let profile: Profile = { ...combineBaselines(baselines), log: [] };
  for (const event of inOrder(events)) {
    profile = { ...apply(profile, event), log: [] };
  }
  return totalsOf(profile);
}

/** Whether a baseline holds anything worth adding to an account. */
export function hasProgress(totals: Totals): boolean {
  return (
    totals.answered > 0 ||
    totals.finishedRuns > 0 ||
    totals.liveRuns > 0 ||
    totals.learned.length > 0 ||
    totals.seenItems.length > 0 ||
    Object.keys(totals.trophies).length > 0
  );
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

function isDifficulty(value: unknown): value is Difficulty {
  return typeof value === "string" && (DIFFICULTIES as readonly string[]).includes(value);
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
function common(saved: object): Omit<Totals, "trophies" | "finishedRuns" | "liveRuns"> {
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

/** Totals saved as version 2 (or later), keeping every valid field. */
function savedTotals(saved: object): Totals {
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

/** The saved version 2 profile, else version 1 carried over, else a fresh one (also when
 * storage is blocked, as in some private windows, or the entry is corrupt). Read by loadGuest,
 * which carries it over into version 3. */
export function loadProfile(storage: Pick<Storage, "getItem"> | undefined): Profile {
  if (!storage) {
    return EMPTY_PROFILE;
  }
  const saved = read(storage, STORAGE_KEY);
  if (saved) {
    return { ...savedTotals(saved), log: [] };
  }
  const old = read(storage, V1_STORAGE_KEY);
  if (old) {
    return {
      ...common(old),
      trophies: trophiesFromBadges(field(old, "badges")),
      finishedRuns: 0,
      liveRuns: 0,
      log: [],
    };
  }
  return EMPTY_PROFILE;
}

/** Save a version 2 profile (kept for the tests of carrying version 2 over). */
export function saveProfile(storage: Pick<Storage, "setItem"> | undefined, profile: Profile) {
  write(storage, STORAGE_KEY, totalsOf(profile));
}

function write(storage: Pick<Storage, "setItem"> | undefined, key: string, value: unknown) {
  try {
    storage?.setItem(key, JSON.stringify(value));
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

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value);
}

function isTimeText(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

function isTopic(value: unknown): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= 200;
}

function isSeconds(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

/** A saved or fetched event, or null if any field is missing or wrong. Fields are named as in
 * the browser (`itemId`); fetched rows are renamed first (`eventOfRow`). */
export function eventOf(value: unknown): ProfileEvent | null {
  if (!isRecord(value)) {
    return null;
  }
  const get = (key: string) => field(value, key);
  const id = get("id");
  const at = get("at");
  if (!isUuid(id) || !isTimeText(at)) {
    return null;
  }
  const stamp = { id: id.toLowerCase(), at: new Date(at).toISOString() };
  switch (get("kind")) {
    case "answer": {
      const [itemId, topic, difficulty, correct, choice, seconds, streak, points] = [
        get("itemId"),
        get("topic"),
        get("difficulty"),
        get("correct"),
        get("choice"),
        get("seconds"),
        get("streak"),
        get("points"),
      ];
      const choiceOk = choice === null || (isCount(choice) && choice <= 3);
      const secondsOk = seconds === null || isSeconds(seconds);
      if (
        isCount(itemId) &&
        isTopic(topic) &&
        isDifficulty(difficulty) &&
        typeof correct === "boolean" &&
        choiceOk &&
        secondsOk &&
        isCount(streak) &&
        isCount(points)
      ) {
        return {
          ...stamp,
          kind: "answer",
          itemId,
          topic,
          difficulty,
          correct,
          choice: choice as number | null,
          seconds: seconds as number | null,
          streak,
          points,
        };
      }
      return null;
    }
    case "read": {
      const itemId = get("itemId");
      const topic = get("topic");
      return isCount(itemId) && isTopic(topic) ? { ...stamp, kind: "read", itemId, topic } : null;
    }
    case "run": {
      const [difficulty, length, correct, seconds] = [
        get("difficulty"),
        get("length"),
        get("correct"),
        get("seconds"),
      ];
      if (isDifficulty(difficulty) && isCount(length) && isCount(correct) && isSeconds(seconds)) {
        return correct <= length
          ? { ...stamp, kind: "run", difficulty, length, correct, seconds }
          : null;
      }
      return null;
    }
    case "search":
      return { ...stamp, kind: "search" };
    default:
      return null;
  }
}

function eventList(value: unknown): ProfileEvent[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map(eventOf).filter((event): event is ProfileEvent => event !== null);
}

// --- The guest ----------------------------------------------------------------------------------

/** A guest's progress in this browser. */
export interface GuestRecord {
  /** Keys the baseline on the server, so each guest's baseline is added once. */
  guestId: string;
  /** What this browser held before it kept a history (a version 2 profile), if anything. */
  baseline: Totals | null;
  profile: Profile;
}

export function freshGuest(newId: () => string): GuestRecord {
  return { guestId: newId(), baseline: null, profile: EMPTY_PROFILE };
}

/** The guest saved in this browser: version 3, or an older profile carried over as a
 * baseline with a new guest id, or a fresh guest. */
export function loadGuest(
  storage: Pick<Storage, "getItem"> | undefined,
  newId: () => string,
): GuestRecord {
  const saved = storage ? read(storage, GUEST_KEY) : null;
  if (saved) {
    const guestId = field(saved, "guestId");
    const baseline = field(saved, "baseline");
    const profile = field(saved, "profile");
    return {
      guestId: isUuid(guestId) ? guestId.toLowerCase() : newId(),
      baseline: isRecord(baseline) ? savedTotals(baseline) : null,
      profile: isRecord(profile)
        ? { ...savedTotals(profile), log: eventList(field(profile, "log")) }
        : EMPTY_PROFILE,
    };
  }
  const older = totalsOf(loadProfile(storage));
  if (hasProgress(older)) {
    return { guestId: newId(), baseline: older, profile: { ...older, log: [] } };
  }
  return freshGuest(newId);
}

export function saveGuest(storage: Pick<Storage, "setItem"> | undefined, guest: GuestRecord) {
  write(storage, GUEST_KEY, guest);
}

/** A guest whose log has grown past the limit, with its oldest events folded into the
 * baseline, so a long-playing guest never fills the browser's storage. */
export function foldGuest(guest: GuestRecord, limit: number = GUEST_LOG_LIMIT): GuestRecord {
  const extra = guest.profile.log.length - limit;
  if (extra <= 0) {
    return guest;
  }
  const oldest = guest.profile.log.slice(0, extra);
  const baseline = replay(guest.baseline ? [guest.baseline] : [], oldest);
  return { ...guest, baseline, profile: { ...guest.profile, log: guest.profile.log.slice(extra) } };
}

// --- The account on the server -----------------------------------------------------------------

/** Migration 011's tables. */
export type Table =
  | "player_answers"
  | "player_reads"
  | "player_runs"
  | "player_searches"
  | "player_baselines";

const TABLE_OF: Record<ProfileEvent["kind"], Table> = {
  answer: "player_answers",
  read: "player_reads",
  run: "player_runs",
  search: "player_searches",
};

/** The SQLSTATE migration 011 refuses a row over its account's cap with. */
export const ROW_CAP_ERROR = "CQ001";

/** How an insert went: stored (or already there), refused for good by the row cap, or failed
 * in a way worth trying again (offline, a server error, an expired session). */
export type InsertResult = "stored" | "capped" | "failed";

/** A row for the server: the table it goes to and its columns. */
export interface OutRow {
  table: Table;
  key: string;
  row: Record<string, unknown>;
}

/** Reads and writes of the signed-in player's own rows (row-level security does the rest). */
export interface AccountRemote {
  insert(table: Table, rows: readonly Record<string, unknown>[]): Promise<InsertResult>;
  /** Every row of a table, or null if it could not be read. */
  readAll(table: Table): Promise<Record<string, unknown>[] | null>;
}

/** An event as a row of its table (`user_id` is filled in by the database). */
export function eventRow(event: ProfileEvent): OutRow {
  const base = { id: event.id, at: event.at };
  const table = TABLE_OF[event.kind];
  switch (event.kind) {
    case "answer":
      return {
        table,
        key: event.id,
        row: {
          ...base,
          item_id: event.itemId,
          topic: event.topic,
          difficulty: event.difficulty,
          choice: event.choice,
          correct: event.correct,
          seconds: event.seconds,
          streak: event.streak,
          points: event.points,
        },
      };
    case "read":
      return { table, key: event.id, row: { ...base, item_id: event.itemId, topic: event.topic } };
    case "run":
      return {
        table,
        key: event.id,
        row: {
          ...base,
          difficulty: event.difficulty,
          length: event.length,
          correct: event.correct,
          seconds: event.seconds,
        },
      };
    case "search":
      return { table, key: event.id, row: base };
  }
}

/** A guest's baseline as a row of player_baselines. */
export function baselineRow(guestId: string, totals: Totals): OutRow {
  return {
    table: "player_baselines",
    key: `baseline:${guestId}`,
    row: {
      guest_id: guestId,
      points: totals.points,
      answered: totals.answered,
      correct: totals.correct,
      best_streak: totals.bestStreak,
      finished_runs: totals.finishedRuns,
      live_runs: totals.liveRuns,
      trophies: totals.trophies,
      played: totals.played,
      learned: totals.learned,
      seen_items: totals.seenItems,
    },
  };
}

/** A fetched row of an event table as an event, or null if it does not parse. */
export function eventOfRow(table: Table, row: Record<string, unknown>): ProfileEvent | null {
  const kinds: Record<Table, ProfileEvent["kind"] | null> = {
    player_answers: "answer",
    player_reads: "read",
    player_runs: "run",
    player_searches: "search",
    player_baselines: null,
  };
  const kind = kinds[table];
  if (!kind) {
    return null;
  }
  return eventOf({ ...row, kind, itemId: row.item_id });
}

/** A fetched baseline row as totals. */
export function baselineOfRow(row: Record<string, unknown>): Totals {
  return savedTotals({
    ...row,
    bestStreak: row.best_streak,
    finishedRuns: row.finished_runs,
    liveRuns: row.live_runs,
    seenItems: row.seen_items,
  });
}

const EVENT_TABLES: readonly Table[] = [
  "player_answers",
  "player_reads",
  "player_runs",
  "player_searches",
];

/** An account's whole history, or null if any part could not be read. */
async function readHistory(
  remote: AccountRemote,
): Promise<{ baselines: Totals[]; events: ProfileEvent[] } | null> {
  const [baselineRows, ...eventRows] = await Promise.all([
    remote.readAll("player_baselines"),
    ...EVENT_TABLES.map((table) => remote.readAll(table)),
  ]);
  if (!baselineRows || eventRows.some((rows) => rows === null)) {
    return null;
  }
  const events = EVENT_TABLES.flatMap((table, index) =>
    (eventRows[index] ?? []).map((row) => eventOfRow(table, row)),
  ).filter((event): event is ProfileEvent => event !== null);
  return { baselines: baselineRows.map(baselineOfRow), events };
}

/** The most rows sent in one request. */
const BATCH = 500;

/**
 * Send rows, table by table, in batches. Returns the keys that are done: stored, already there,
 * or refused for good by the row cap (dropped; `onCapped` hears of it). A batch that fails is
 * tried again one row at a time, so one row cannot hold back the rest; rows that still fail
 * stay for the next try.
 */
export async function sendRows(
  remote: AccountRemote,
  rows: readonly OutRow[],
  onCapped: (table: Table) => void,
): Promise<Set<string>> {
  const done = new Set<string>();
  const tables = [...new Set(rows.map((row) => row.table))];
  for (const table of tables) {
    const mine = rows.filter((row) => row.table === table);
    for (let start = 0; start < mine.length; start += BATCH) {
      const batch = mine.slice(start, start + BATCH);
      const result = await remote.insert(
        table,
        batch.map((row) => row.row),
      );
      if (result === "stored") {
        batch.forEach((row) => done.add(row.key));
        continue;
      }
      for (const row of batch) {
        const single = batch.length === 1 ? result : await remote.insert(table, [row.row]);
        if (single === "stored") {
          done.add(row.key);
        } else if (single === "capped") {
          done.add(row.key);
          onCapped(table);
        }
      }
    }
  }
  return done;
}

/** A signed-in player's cache in this browser: the profile last shown, and the events not yet
 * stored on the server. */
interface AccountCache {
  totals: Totals;
  outbox: ProfileEvent[];
}

function loadAccountCache(
  storage: Pick<Storage, "getItem"> | undefined,
  userId: string,
): AccountCache | null {
  const saved = storage ? read(storage, `${ACCOUNT_KEY}:${userId}`) : null;
  if (!saved) {
    return null;
  }
  const totals = field(saved, "totals");
  return {
    totals: isRecord(totals) ? savedTotals(totals) : EMPTY_TOTALS,
    outbox: eventList(field(saved, "outbox")),
  };
}

// --- The profile store ---------------------------------------------------------------------------

/** One of the pure updates above: the new profile and what it earned. */
export type ProfileUpdate = (profile: Profile) => [Profile, Award[]];

export interface ProfileStoreDeps {
  storage: Pick<Storage, "getItem" | "setItem" | "removeItem"> | undefined;
  /** The account's rows on the server, or null when accounts are off. */
  remote: AccountRemote | null;
  newId: () => string;
  /** Run `task` after `ms` milliseconds (a retry). */
  schedule: (task: () => void, ms: number) => void;
  warn: (message: string) => void;
  /** How many events a guest keeps before folding the oldest (GUEST_LOG_LIMIT by default). */
  guestLogLimit?: number;
}

export interface ProfileStore {
  profile(): Profile;
  subscribe(listener: () => void): () => void;
  update(change: ProfileUpdate): Award[];
  /** A player signed in: add the guest's progress to the account, then show the account. */
  signIn(userId: string): Promise<void>;
  /** Back to a guest. */
  signOut(): void;
  /** Send whatever is waiting. */
  flush(): Promise<void>;
}

/** Wait before trying to send again after a failure. */
export const RETRY_MS = 30_000;

/**
 * The page's profile: a guest's from this browser, or a signed-in player's from the server.
 *
 * Signed in, the profile shown is the replay of the account's history plus what is waiting to
 * be sent: the guest's progress until it has been added (then the browser starts a fresh guest
 * with a new guest id) and the outbox of events played since. Each update adds its events to
 * the outbox, which is sent at once and again on failure.
 */
export function createProfileStore(deps: ProfileStoreDeps): ProfileStore {
  let guest = loadGuest(deps.storage, deps.newId);
  let shown: Profile = guest.profile;
  let account: { userId: string; outbox: ProfileEvent[]; guestPending: boolean } | null = null;
  let signingIn: Promise<void> | null = null;
  let flushing: Promise<void> | null = null;
  let again = false;
  let retrying = false;
  const warned = new Set<Table>();
  const listeners = new Set<() => void>();

  function show(next: Profile) {
    shown = next;
    for (const listener of listeners) {
      listener();
    }
  }

  function saveAccount() {
    if (account) {
      write(deps.storage, `${ACCOUNT_KEY}:${account.userId}`, {
        totals: totalsOf(shown),
        outbox: account.outbox,
      });
    }
  }

  function onCapped(table: Table) {
    if (!warned.has(table)) {
      warned.add(table);
      deps.warn(`Progress not saved: this account reached its daily limit for ${table}.`);
    }
  }

  function retryLater() {
    if (!retrying) {
      retrying = true;
      deps.schedule(() => {
        retrying = false;
        void flush();
      }, RETRY_MS);
    }
  }

  /** The guest's rows: its baseline, if it holds anything, then its events. */
  function guestRows(): OutRow[] {
    const rows = guest.profile.log.map(eventRow);
    return guest.baseline && hasProgress(guest.baseline)
      ? [baselineRow(guest.guestId, guest.baseline), ...rows]
      : rows;
  }

  async function sendOnce(): Promise<boolean> {
    const remote = deps.remote;
    if (!remote || !account) {
      return true;
    }
    const current = account;
    if (current.guestPending) {
      const rows = guestRows();
      const done = await sendRows(remote, rows, onCapped);
      if (rows.every((row) => done.has(row.key))) {
        // Added: this browser starts a fresh guest with a new id, so a later guest's
        // baseline is never taken for this one's.
        current.guestPending = false;
        guest = freshGuest(deps.newId);
        saveGuest(deps.storage, guest);
      } else {
        return false;
      }
    }
    if (current.outbox.length > 0) {
      const sending = current.outbox;
      const done = await sendRows(remote, sending.map(eventRow), onCapped);
      // Events played while this was sending stay for the next round (flush runs again).
      current.outbox = current.outbox.filter((event) => !done.has(event.id));
      saveAccount();
      return sending.every((event) => done.has(event.id));
    }
    return true;
  }

  function flush(): Promise<void> {
    if (flushing) {
      again = true;
      return flushing;
    }
    flushing = (async () => {
      do {
        again = false;
        const ok = await sendOnce();
        if (!ok) {
          retryLater();
          break;
        }
      } while (again);
    })().finally(() => {
      flushing = null;
    });
    return flushing;
  }

  async function startAccount(userId: string): Promise<void> {
    const remote = deps.remote;
    if (!remote) {
      return;
    }
    const cache = loadAccountCache(deps.storage, userId);
    const guestPending = guestRows().length > 0;
    account = { userId, outbox: cache?.outbox ?? [], guestPending };
    const pending = () => [
      ...(account?.guestPending ? guest.profile.log : []),
      ...(account?.outbox ?? []),
    ];
    const pendingBaselines = (): Totals[] =>
      account?.guestPending && guest.baseline && hasProgress(guest.baseline)
        ? [guest.baseline]
        : [];
    // Show the cache at once, if there is one, while the server is read.
    if (cache) {
      show({ ...replay([cache.totals, ...pendingBaselines()], pending()), log: [] });
    }
    await flush();
    const history = await readHistory(remote);
    if (!account || account.userId !== userId) {
      return;
    }
    if (history) {
      const baselines = [...history.baselines, ...pendingBaselines()];
      show({ ...replay(baselines, [...history.events, ...pending()]), log: [] });
    } else if (!cache) {
      show({ ...replay(pendingBaselines(), pending()), log: [] });
      retryLater();
    }
    saveAccount();
  }

  function signOut() {
    if (!account) {
      return;
    }
    if (account.outbox.length === 0) {
      try {
        deps.storage?.removeItem(`${ACCOUNT_KEY}:${account.userId}`);
      } catch {
        // Nothing to remove where storage is blocked.
      }
    }
    account = null;
    signingIn = null;
    show(guest.profile);
  }

  return {
    profile: () => shown,
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    update(change) {
      const [next, earned] = change(shown);
      if (account) {
        account.outbox = [...account.outbox, ...next.log];
        show({ ...next, log: [] });
        saveAccount();
        void flush();
      } else {
        guest = foldGuest({ ...guest, profile: next }, deps.guestLogLimit ?? GUEST_LOG_LIMIT);
        show(guest.profile);
        saveGuest(deps.storage, guest);
      }
      return earned;
    },
    signIn(userId) {
      if (account?.userId === userId && signingIn) {
        return signingIn;
      }
      if (account && account.userId !== userId) {
        signOut();
      }
      signingIn = startAccount(userId);
      return signingIn;
    },
    signOut,
    flush,
  };
}

// --- The browser's remote ------------------------------------------------------------------------

/** What a fetch needs: a Supabase project and the signed-in player's access token. */
export interface RemoteConfig {
  url: string;
  key: string;
  token: () => Promise<string | null>;
  fetch: typeof fetch;
}

const PAGE = 1000;

/** The signed-in player's rows through Supabase's REST API, with the publishable key and the
 * player's token; row-level security limits every read and write to their own rows. */
export function accountRemote(config: RemoteConfig): AccountRemote {
  async function headers(): Promise<Record<string, string> | null> {
    const token = await config.token();
    return token ? { apikey: config.key, Authorization: `Bearer ${token}` } : null;
  }
  return {
    async insert(table, rows) {
      const auth = await headers();
      if (!auth) {
        return "failed";
      }
      try {
        const response = await config.fetch(`${config.url}/rest/v1/${table}`, {
          method: "POST",
          headers: {
            ...auth,
            "Content-Type": "application/json",
            // A row already there (the same id, or the same guest's baseline) is skipped.
            Prefer: "resolution=ignore-duplicates,return=minimal",
          },
          body: JSON.stringify(rows),
        });
        if (response.ok) {
          return "stored";
        }
        const body: unknown = await response.json().catch(() => null);
        return isRecord(body) && field(body, "code") === ROW_CAP_ERROR ? "capped" : "failed";
      } catch {
        return "failed";
      }
    },
    async readAll(table) {
      const auth = await headers();
      if (!auth) {
        return null;
      }
      const order = table === "player_baselines" ? "guest_id.asc" : "at.asc,id.asc";
      const rows: Record<string, unknown>[] = [];
      try {
        for (;;) {
          const query = `select=*&order=${order}&limit=${PAGE}&offset=${rows.length}`;
          const response = await config.fetch(`${config.url}/rest/v1/${table}?${query}`, {
            headers: auth,
          });
          if (!response.ok) {
            return null;
          }
          const page: unknown = await response.json();
          if (!Array.isArray(page)) {
            return null;
          }
          rows.push(...page.filter((row): row is Record<string, unknown> => isRecord(row)));
          if (page.length < PAGE) {
            return rows;
          }
        }
      } catch {
        return null;
      }
    },
  };
}
