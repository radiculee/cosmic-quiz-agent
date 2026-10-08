import { describe, expect, it } from "vitest";

import {
  answerInRun,
  availableLength,
  formatClock,
  isRunFinished,
  lengthNote,
  planRun,
  quizTopicCount,
  rankFor,
  runAccuracy,
  scoreAnswer,
  streakMultiplier,
} from "./game";
import type { BankTopic } from "./types";

function topic(name: string): BankTopic {
  return { name, kind: "evergreen", learn: ["easy"], quiz: ["easy", "hard"] };
}

const TOPICS = Array.from({ length: 34 }, (_, i) => topic(`Topic ${i + 1}`));

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

describe("run lengths", () => {
  it("counts the topics a difficulty can fill", () => {
    expect(quizTopicCount(TOPICS, "easy")).toBe(34);
    expect(quizTopicCount(TOPICS, "medium")).toBe(0);
  });

  it("offers a length only when the bank has that many topics, falling back to the longest", () => {
    expect(availableLength(30, 30)).toBe(30);
    expect(availableLength(23, 30)).toBe(10);
    expect(availableLength(23, 60)).toBe(10);
    expect(availableLength(60, 60)).toBe(60);
    expect(availableLength(45, 60)).toBe(30);
    expect(availableLength(9, 10)).toBeNull();
  });

  it("says why a length is closed, in the words of the decision", () => {
    expect(lengthNote("hard", 23)).toBe(
      "HARD: 23 of 30 questions so far. 30 and 60 open as the bank grows.",
    );
    expect(lengthNote("easy", 30)).toBe(
      "EASY: 30 of 60 questions so far. 60 opens as the bank grows.",
    );
    expect(lengthNote("medium", 7)).toBe(
      "MEDIUM: 7 of 10 questions so far. 10, 30 and 60 open as the bank grows.",
    );
    expect(lengthNote("easy", 60)).toBeNull();
  });
});

describe("runs", () => {
  it("plans distinct topics of the chosen length, unplayed ones first", () => {
    const played = TOPICS.slice(0, 20).map((t) => t.name);
    const run = planRun(TOPICS, "easy", 10, played, () => 0.3);

    expect(run.topics).toHaveLength(10);
    expect(new Set(run.topics).size).toBe(10);
    // 14 unplayed topics: all 10 places go to them.
    expect(run.topics.some((name) => played.includes(name))).toBe(false);
    expect(run.repeats).toBe(false);
  });

  it("fills a long run with played topics only when it must, and says so", () => {
    const played = TOPICS.slice(0, 20).map((t) => t.name);
    const run = planRun(TOPICS, "easy", 30, played, () => 0.5);

    expect(run.topics).toHaveLength(30);
    expect(new Set(run.topics).size).toBe(30);
    // The 14 unplayed topics come first.
    expect(run.topics.slice(0, 14).some((name) => played.includes(name))).toBe(false);
    expect(run.repeats).toBe(true);
  });

  it("never repeats a topic, so a run is shorter only if the bank is", () => {
    const run = planRun(TOPICS.slice(0, 4), "hard", 10, []);

    expect(run.topics).toHaveLength(4);
    expect(planRun(TOPICS, "medium", 10, []).topics).toEqual([]);
  });

  it("tracks streaks, points, accuracy and the end of the run", () => {
    let run = planRun(TOPICS.slice(0, 3), "easy", 10, []);
    expect(runAccuracy(run)).toBe(0);
    for (const correct of [true, true, true]) {
      run = answerInRun(run, run.results.length + 1, "t", correct, 30).run;
    }
    expect(run.streak).toBe(3);
    expect(run.points).toBe(100 + 100 + 150);
    expect(runAccuracy(run)).toBe(1);
    expect(isRunFinished(run)).toBe(true);
  });

  it("is not finished while questions are left", () => {
    let run = planRun(TOPICS, "easy", 10, []);
    run = answerInRun(run, 1, "t", false, 5).run;

    expect(isRunFinished(run)).toBe(false);
    expect(run.streak).toBe(0);
    expect(runAccuracy(run)).toBe(0);
  });

  it("formats the clock", () => {
    expect(formatClock(83_456)).toBe("1:23.4");
    expect(formatClock(0)).toBe("0:00.0");
  });
});
