import { describe, expect, it } from "vitest";

import { answerInRun, planRun, type Run, type RunLength } from "./game";
import {
  answerReached,
  type BankCounts,
  learnReached,
  liveReached,
  notYetPossible,
  rankUp,
  runReached,
  TIER_COUNT,
  tierFor,
  tiersEarned,
  TROPHIES,
  TROPHY_IDS,
  upgrades,
  withAwards,
} from "./trophies";
import type { BankTopic, Difficulty } from "./types";

const TOPICS: BankTopic[] = Array.from({ length: 60 }, (_, i) => ({
  name: `Topic ${i + 1}`,
  kind: "evergreen",
  learn: [],
  quiz: ["easy", "medium", "hard"],
}));

/** A finished run: `correct` right answers first, then wrong ones, each in `seconds`. */
function playedRun(
  length: RunLength,
  difficulty: Difficulty,
  correct: number,
  seconds = 5,
): Run {
  let run = planRun(TOPICS, difficulty, length, []);
  for (let i = 0; i < length; i += 1) {
    run = answerInRun(run, i, `Topic ${i + 1}`, i < correct, seconds).run;
  }
  return run;
}

describe("the list", () => {
  it("has eight trophies of three tiers, each with its own sentence", () => {
    expect(TROPHIES.map((t) => t.id)).toEqual([...TROPHY_IDS]);
    expect(TIER_COUNT).toBe(24);
    const sentences = TROPHIES.flatMap((t) => t.goals.map((goal) => t.how(goal)));
    expect(new Set(sentences).size).toBe(24);
    expect(TROPHIES[0]?.how(1)).toBe("Answer 1 question correctly.");
  });
});

describe("tiers", () => {
  it("is the highest goal met", () => {
    expect(tierFor([1, 50, 250], 0)).toBeNull();
    expect(tierFor([1, 50, 250], 1)).toBe("bronze");
    expect(tierFor([1, 50, 250], 249)).toBe("silver");
    expect(tierFor([1, 50, 250], 900)).toBe("gold");
  });

  it("follows correct answers and streaks", () => {
    expect(answerReached(0, 0)).toEqual({});
    expect(answerReached(50, 5)).toEqual({ "first-light": "silver", "hot-streak": "bronze" });
    expect(answerReached(250, 20)).toEqual({ "first-light": "gold", "hot-streak": "gold" });
  });

  it("follows topics read and live runs", () => {
    expect(learnReached(9)).toEqual({});
    expect(learnReached(20)).toEqual({ explorer: "silver" });
    expect(liveReached(1)).toEqual({ "web-researcher": "bronze" });
    expect(liveReached(10)).toEqual({ "web-researcher": "gold" });
  });
});

describe("run trophies", () => {
  it("take the run's length as the tier", () => {
    expect(runReached(playedRun(10, "easy", 6, 30), 300)).toEqual({ finisher: "bronze" });
    expect(runReached(playedRun(30, "easy", 30, 30), 900)).toEqual({
      finisher: "silver",
      "perfect-run": "silver",
    });
    expect(runReached(playedRun(60, "hard", 60, 5), 300)).toEqual({
      finisher: "gold",
      "perfect-run": "gold",
      "speed-runner": "gold",
      "hard-mode": "gold",
    });
  });

  it("give Speed runner for 12 seconds a question or less with at least 70% right", () => {
    expect(runReached(playedRun(10, "easy", 7), 120)["speed-runner"]).toBe("bronze");
    expect(runReached(playedRun(10, "easy", 7), 120.1)["speed-runner"]).toBeUndefined();
    // Racing through on guesses does not earn it.
    expect(runReached(playedRun(10, "easy", 6), 30)["speed-runner"]).toBeUndefined();
    expect(runReached(playedRun(30, "easy", 21), 360)["speed-runner"]).toBe("silver");
    expect(runReached(playedRun(30, "easy", 20), 360)["speed-runner"]).toBeUndefined();
  });

  it("give Hard mode only for a perfect run on HARD", () => {
    expect(runReached(playedRun(10, "medium", 10), 600)["hard-mode"]).toBeUndefined();
    expect(runReached(playedRun(10, "hard", 9), 600)["hard-mode"]).toBeUndefined();
    expect(runReached(playedRun(10, "hard", 10), 600)["hard-mode"]).toBe("bronze");
  });

  it("are not given for a run ended early", () => {
    let run = planRun(TOPICS, "hard", 10, []);
    for (let i = 0; i < 9; i += 1) {
      run = answerInRun(run, i, "t", true, 1).run;
    }
    expect(runReached(run, 9)).toEqual({});
  });
});

describe("what is new", () => {
  it("lists only higher tiers, in the list's order, and never lowers one", () => {
    const current = { "first-light": "silver", explorer: "bronze" } as const;
    const awards = upgrades(current, {
      explorer: "silver",
      "first-light": "bronze",
      "hot-streak": "bronze",
    });

    expect(awards).toEqual([
      { kind: "trophy", id: "hot-streak", tier: "bronze" },
      { kind: "trophy", id: "explorer", tier: "silver" },
    ]);
    expect(withAwards(current, awards)).toEqual({
      "first-light": "silver",
      "hot-streak": "bronze",
      explorer: "silver",
    });
    expect(upgrades(current, current)).toEqual([]);
  });

  it("counts earned tiers, a gold counting all three", () => {
    expect(tiersEarned({})).toBe(0);
    expect(tiersEarned({ "first-light": "gold", finisher: "bronze" })).toBe(4);
  });

  it("notices a rank-up and names the rank's threshold", () => {
    expect(rankUp(900, 950)).toBeNull();
    expect(rankUp(900, 1_100)).toEqual({ kind: "rank", name: "Cadet", points: 1_000 });
    expect(rankUp(900, 3_500)).toEqual({ kind: "rank", name: "Navigator", points: 3_000 });
  });
});

describe("tiers the bank cannot support yet", () => {
  // The bank on 2026-10-08.
  const counts: BankCounts = { quiz: { easy: 30, medium: 26, hard: 23 }, learnTopics: 31 };

  it("names the shortfall for runs too long for any difficulty", () => {
    expect(notYetPossible("finisher", "silver", counts)).toBeNull();
    expect(notYetPossible("finisher", "gold", counts)).toBe(
      "Needs 60 questions at one level: EASY has 30 so far.",
    );
    expect(notYetPossible("speed-runner", "gold", counts)).not.toBeNull();
  });

  it("needs a run long enough for a streak", () => {
    expect(notYetPossible("hot-streak", "gold", counts)).toBeNull();
    expect(
      notYetPossible("hot-streak", "gold", { ...counts, quiz: { easy: 29, medium: 26, hard: 23 } }),
    ).toBe("Needs 30 questions at one level: EASY has 29 so far.");
  });

  it("counts only HARD for Hard mode, and LEARN topics for Explorer", () => {
    expect(notYetPossible("hard-mode", "bronze", counts)).toBeNull();
    expect(notYetPossible("hard-mode", "silver", counts)).toBe("Needs 30 HARD questions: 23 so far.");
    expect(notYetPossible("explorer", "gold", counts)).toBeNull();
    expect(notYetPossible("explorer", "gold", { ...counts, learnTopics: 12 })).toBe(
      "Needs 30 LEARN topics: 12 so far.",
    );
    expect(notYetPossible("first-light", "gold", counts)).toBeNull();
    expect(notYetPossible("web-researcher", "gold", counts)).toBeNull();
  });
});
