/**
 * Trophies: eight achievements, each with bronze, silver and gold tiers (decided 2026-10-08,
 * docs/PLAN.md Session 8). They replace the v1 badges, which carry over as bronze.
 *
 * Everything here is pure: given what just happened, which tiers it reaches, and which of those
 * are new. The profile (profile.ts) stores the tiers; the pop-up (TrophyPopup) shows what is new.
 */
import { isRunFinished, RANKS, rankFor, type RankName, RUN_LENGTHS, type Run, runCorrect } from "./game";
import type { Difficulty } from "./types";

export const TIERS = ["bronze", "silver", "gold"] as const;
export type Tier = (typeof TIERS)[number];

/** Bronze, silver and gold goals, in that order. */
type Goals = readonly [number, number, number];

export const TROPHY_IDS = [
  "first-light",
  "hot-streak",
  "finisher",
  "perfect-run",
  "speed-runner",
  "hard-mode",
  "explorer",
  "web-researcher",
] as const;
export type TrophyId = (typeof TROPHY_IDS)[number];

/** The tier reached for each trophy that has one. */
export type TrophyTiers = Partial<Record<TrophyId, Tier>>;

export const FIRST_LIGHT_GOALS: Goals = [1, 50, 250];
export const HOT_STREAK_GOALS: Goals = [5, 10, 20];
/** Finisher, Perfect run, Speed runner and Hard mode: the run's length decides the tier. */
export const RUN_GOALS: Goals = RUN_LENGTHS;
export const EXPLORER_GOALS: Goals = [10, 20, 30];
export const WEB_RESEARCHER_GOALS: Goals = [1, 3, 10];
/** Speed runner: 12 seconds a question or less on average (2 minutes for 10, as the v1 badge)... */
export const SPEED_RUNNER_SECONDS = 12;
/** ...with at least 70% right, so racing through on guesses does not earn it. */
export const SPEED_RUNNER_PERCENT = 70;

export interface Trophy {
  id: TrophyId;
  name: string;
  goals: Goals;
  /** How to earn the tier with this goal, as a sentence. */
  how: (goal: number) => string;
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

export const TROPHIES: readonly Trophy[] = [
  {
    id: "first-light",
    name: "First light",
    goals: FIRST_LIGHT_GOALS,
    how: (goal) => `Answer ${plural(goal, "question", "questions")} correctly.`,
  },
  {
    id: "hot-streak",
    name: "Hot streak",
    goals: HOT_STREAK_GOALS,
    how: (goal) => `Answer ${goal} questions in a row correctly.`,
  },
  {
    id: "finisher",
    name: "Finisher",
    goals: RUN_GOALS,
    how: (goal) => `Finish a ${goal}-question run.`,
  },
  {
    id: "perfect-run",
    name: "Perfect run",
    goals: RUN_GOALS,
    how: (goal) => `Finish a ${goal}-question run with ${goal} out of ${goal}.`,
  },
  {
    id: "speed-runner",
    name: "Speed runner",
    goals: RUN_GOALS,
    how: (goal) =>
      `Finish a ${goal}-question run averaging ${SPEED_RUNNER_SECONDS} seconds a question or ` +
      `less, with at least ${SPEED_RUNNER_PERCENT}% right.`,
  },
  {
    id: "hard-mode",
    name: "Hard mode",
    goals: RUN_GOALS,
    how: (goal) => `Finish a ${goal}-question run on HARD with ${goal} out of ${goal}.`,
  },
  {
    id: "explorer",
    name: "Explorer",
    goals: EXPLORER_GOALS,
    how: (goal) => `Read ${goal} different topics in LEARN.`,
  },
  {
    id: "web-researcher",
    name: "Web researcher",
    goals: WEB_RESEARCHER_GOALS,
    how: (goal) => `Research ${plural(goal, "new topic", "new topics")} live on the web page.`,
  },
];

export function trophy(id: TrophyId): Trophy {
  const found = TROPHIES.find((entry) => entry.id === id);
  if (!found) {
    throw new Error(`unknown trophy ${id}`);
  }
  return found;
}

/** 0 for bronze to 2 for gold; -1 for no tier. */
export function tierIndex(tier: Tier | null | undefined): number {
  return tier ? TIERS.indexOf(tier) : -1;
}

/** The highest tier whose goal `value` meets, if any. */
export function tierFor(goals: Goals, value: number): Tier | null {
  let reached: Tier | null = null;
  for (const [index, tier] of TIERS.entries()) {
    const goal = goals[index];
    if (goal !== undefined && value >= goal) {
      reached = tier;
    }
  }
  return reached;
}

function reachedOnly(entries: [TrophyId, Tier | null][]): TrophyTiers {
  const tiers: TrophyTiers = {};
  for (const [id, tier] of entries) {
    if (tier) {
      tiers[id] = tier;
    }
  }
  return tiers;
}

// --- What an event reaches --------------------------------------------------------------------

/** After a quiz answer: all-time correct answers, and the streak including this answer. */
export function answerReached(correctTotal: number, streak: number): TrophyTiers {
  return reachedOnly([
    ["first-light", tierFor(FIRST_LIGHT_GOALS, correctTotal)],
    ["hot-streak", tierFor(HOT_STREAK_GOALS, streak)],
  ]);
}

/** After a finished run, timed by the run clock. A run ended early reaches nothing. */
export function runReached(run: Run, seconds: number): TrophyTiers {
  const length = run.topics.length;
  if (length === 0 || !isRunFinished(run)) {
    return {};
  }
  const correct = runCorrect(run);
  const lengthTier = tierFor(RUN_GOALS, length);
  const perfect = correct === length;
  const fast =
    seconds <= SPEED_RUNNER_SECONDS * length && correct * 100 >= length * SPEED_RUNNER_PERCENT;
  return reachedOnly([
    ["finisher", lengthTier],
    ["perfect-run", perfect ? lengthTier : null],
    ["speed-runner", fast ? lengthTier : null],
    ["hard-mode", perfect && run.difficulty === "hard" ? lengthTier : null],
  ]);
}

/** After reading a LEARN topic: how many different topics have been read. */
export function learnReached(topicsRead: number): TrophyTiers {
  return reachedOnly([["explorer", tierFor(EXPLORER_GOALS, topicsRead)]]);
}

/** After a live run that produced a result: how many there have been. */
export function liveReached(liveRuns: number): TrophyTiers {
  return reachedOnly([["web-researcher", tierFor(WEB_RESEARCHER_GOALS, liveRuns)]]);
}

// --- What is new ------------------------------------------------------------------------------

/** Something to celebrate in the pop-up. */
export type Award =
  | { kind: "trophy"; id: TrophyId; tier: Tier }
  | { kind: "rank"; name: RankName; points: number };

/** The trophies `reached` takes to a higher tier than `current`, in the trophy list's order. A
 * tier is never lowered. */
export function upgrades(current: TrophyTiers, reached: TrophyTiers): Award[] {
  return TROPHY_IDS.flatMap((id): Award[] => {
    const tier = reached[id];
    return tier && tierIndex(tier) > tierIndex(current[id]) ? [{ kind: "trophy", id, tier }] : [];
  });
}

/** `current` with the trophy awards applied. */
export function withAwards(current: TrophyTiers, awards: readonly Award[]): TrophyTiers {
  const next = { ...current };
  for (const award of awards) {
    if (award.kind === "trophy" && tierIndex(award.tier) > tierIndex(next[award.id])) {
      next[award.id] = award.tier;
    }
  }
  return next;
}

/** A rank-up, if the points moved into a higher rank. */
export function rankUp(pointsBefore: number, pointsAfter: number): Award | null {
  const after = rankFor(pointsAfter);
  if (after.name === rankFor(pointsBefore).name) {
    return null;
  }
  const points = RANKS.find((rank) => rank.name === after.name)?.points ?? pointsAfter;
  return { kind: "rank", name: after.name, points };
}

/** Tiers earned so far, out of every tier there is. */
export function tiersEarned(tiers: TrophyTiers): number {
  return TROPHY_IDS.reduce((total, id) => total + tierIndex(tiers[id]) + 1, 0);
}

export const TIER_COUNT = TROPHY_IDS.length * TIERS.length;

// --- What the bank allows yet -------------------------------------------------------------------

/** What the bank holds, for saying which tiers cannot be earned yet. */
export interface BankCounts {
  /** Topics with a quiz question at each difficulty (the longest run without repeats). */
  quiz: Record<Difficulty, number>;
  /** Topics with an explanation at any difficulty. */
  learnTopics: number;
}

/**
 * Why a tier cannot be earned with the bank as it is, or null if it can. Runs never repeat a
 * topic, so a 60-question run needs 60 topics at one difficulty; a streak of 20 needs a run of
 * at least 20 questions.
 */
export function notYetPossible(id: TrophyId, tier: Tier, counts: BankCounts): string | null {
  const goal = trophy(id).goals[tierIndex(tier)] ?? 0;
  const levels: Difficulty[] = ["easy", "medium", "hard"];
  const best = levels.reduce((top, level) => (counts.quiz[level] > counts.quiz[top] ? level : top));
  const runNeeding = (questions: number): string | null => {
    const length = RUN_LENGTHS.find((option) => option >= questions);
    if (length === undefined || counts.quiz[best] >= length) {
      return null;
    }
    return `Needs ${length} questions at one level: ${best.toUpperCase()} has ${counts.quiz[best]} so far.`;
  };
  switch (id) {
    case "hot-streak":
    case "finisher":
    case "perfect-run":
    case "speed-runner":
      return runNeeding(goal);
    case "hard-mode":
      return counts.quiz.hard >= goal
        ? null
        : `Needs ${goal} HARD questions: ${counts.quiz.hard} so far.`;
    case "explorer":
      return counts.learnTopics >= goal
        ? null
        : `Needs ${goal} LEARN topics: ${counts.learnTopics} so far.`;
    case "first-light":
    case "web-researcher":
      return null;
  }
}
