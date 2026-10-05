import { describe, expect, it } from "vitest";

import {
  answerInRun,
  formatClock,
  isRunFinished,
  planRun,
  rankFor,
  runBadges,
  scoreAnswer,
  streakMultiplier,
} from "./game";
import {
  afterAnswer,
  afterLearn,
  afterRun,
  EMPTY_PROFILE,
  loadProfile,
  saveProfile,
} from "./profile";
import type { BankTopic } from "./types";

function topic(name: string): BankTopic {
  return { name, kind: "evergreen", learn: ["easy"], quiz: ["easy", "hard"] };
}

const TOPICS = Array.from({ length: 14 }, (_, i) => topic(`Topic ${i + 1}`));

describe("points", () => {
  it("scores by difficulty, streak and speed", () => {
    expect(streakMultiplier(2)).toBe(1);
    expect(streakMultiplier(3)).toBe(1.5);
    expect(streakMultiplier(7)).toBe(2);
    expect(scoreAnswer("easy", true, 1, 20)).toEqual({
      base: 100,
      multiplier: 1,
      speedBonus: 0,
      total: 100,
    });
    expect(scoreAnswer("hard", true, 3, 10).total).toBe(450 + 75);
    expect(scoreAnswer("medium", false, 0, 1).total).toBe(0);
  });
});

describe("ranks", () => {
  it("climbs with points and reports progress to the next rank", () => {
    expect(rankFor(0)).toMatchObject({ name: "Stargazer", progress: 0 });
    expect(rankFor(2_000)).toMatchObject({ name: "Cadet", progress: 0.5 });
    expect(rankFor(50_000)).toEqual({ name: "Cosmologist", next: null, progress: 1 });
  });
});

describe("runs", () => {
  it("plans 10 distinct topics, the chosen one first and unplayed ones before played", () => {
    const played = ["Topic 2", "Topic 3", "Topic 4", "Topic 5"];
    const run = planRun(TOPICS, "easy", "Topic 1", played, () => 0.3);

    expect(run.topics).toHaveLength(10);
    expect(run.topics[0]).toBe("Topic 1");
    expect(new Set(run.topics).size).toBe(10);
    // 13 others, 9 unplayed: the 9 places after the first are all unplayed.
    expect(run.topics.slice(1).some((name) => played.includes(name))).toBe(false);
    expect(run.repeats).toBe(false);
  });

  it("puts a custom topic first and fills the run from the bank", () => {
    const run = planRun(TOPICS.slice(0, 4), "easy", "Black holes", [], () => 0.5);

    expect(run.topics[0]).toBe("Black holes");
    expect(run.topics).toHaveLength(5);
    expect(new Set(run.topics).size).toBe(5);
  });

  it("repeats played topics only when it must, and says so", () => {
    const few = TOPICS.slice(0, 4);
    const run = planRun(few, "easy", "Topic 1", ["Topic 2"], () => 0.5);

    expect(run.topics).toHaveLength(4);
    expect(run.repeats).toBe(true);
  });

  it("tracks streaks, points and the end of the run", () => {
    let run = planRun(TOPICS.slice(0, 3), "easy", "Topic 1", []);
    for (const correct of [true, true, true]) {
      run = answerInRun(run, run.results.length + 1, "t", correct, 30).run;
    }
    expect(run.streak).toBe(3);
    expect(run.points).toBe(100 + 100 + 150);
    expect(isRunFinished(run)).toBe(true);
  });

  it("awards run badges only for full runs", () => {
    let run = planRun(TOPICS, "hard", "Topic 1", []);
    for (let i = 0; i < 10; i += 1) {
      run = answerInRun(run, i, "t", true, 5).run;
    }
    expect(runBadges(run, 100)).toEqual(["perfect-run", "hard-mode", "speed-runner"]);
    const short = planRun(TOPICS.slice(0, 2), "hard", "Topic 1", []);
    expect(runBadges(short, 10)).toEqual([]);
  });

  it("formats the clock", () => {
    expect(formatClock(83_456)).toBe("1:23.4");
    expect(formatClock(0)).toBe("0:00.0");
  });
});

describe("profile", () => {
  it("adds points, remembers what was seen and awards badges once", () => {
    const score = scoreAnswer("easy", true, 5, 30);
    const [profile, earned] = afterAnswer(EMPTY_PROFILE, "easy", 7, "Quasars", score, true, 5);
    expect(profile.points).toBe(200);
    expect(profile.seenItems).toEqual([7]);
    expect(profile.played.easy).toEqual(["Quasars"]);
    expect(earned).toEqual(["first-light", "hot-streak"]);
    const [, again] = afterAnswer(profile, "easy", 8, "Auroras", score, true, 6);
    expect(again).toEqual([]);
  });

  it("counts learned topics towards Explorer", () => {
    let profile = EMPTY_PROFILE;
    let earned: string[] = [];
    for (let i = 0; i < 10; i += 1) {
      [profile, earned] = afterLearn(profile, i, `Topic ${i}`);
    }
    expect(earned).toEqual(["explorer"]);
    expect(afterLearn(profile, 1, "Topic 1")[0].learned).toHaveLength(10);
  });

  it("gives run badges after a finished run", () => {
    let run = planRun(TOPICS, "easy", "Topic 1", []);
    for (let i = 0; i < 10; i += 1) {
      run = answerInRun(run, i, "t", true, 30).run;
    }
    expect(afterRun(EMPTY_PROFILE, run, 300)[1]).toEqual(["perfect-run"]);
  });

  it("survives corrupt, partial or blocked storage", () => {
    const data = new Map<string, string>();
    const storage = {
      getItem: (key: string) => data.get(key) ?? null,
      setItem: (key: string, value: string) => void data.set(key, value),
    };
    const [profile] = afterAnswer(EMPTY_PROFILE, "hard", 3, "Quasars", scoreAnswer("hard", true, 1, 5), true, 1);
    saveProfile(storage, profile);
    expect(loadProfile(storage)).toEqual(profile);

    data.set("cosmic-quiz:profile:v1", '{"points": 50, "badges": ["first-light", "made-up"], "seenItems": [1, -2, "x"]}');
    expect(loadProfile(storage)).toMatchObject({ points: 50, badges: ["first-light"], seenItems: [1] });
    data.set("cosmic-quiz:profile:v1", "{broken");
    expect(loadProfile(storage)).toEqual(EMPTY_PROFILE);
    const blocked = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(loadProfile(blocked)).toEqual(EMPTY_PROFILE);
    expect(() => saveProfile(blocked, profile)).not.toThrow();
  });
});
