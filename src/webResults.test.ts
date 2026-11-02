import { describe, expect, it } from "vitest";

import type { Slot } from "./search";
import type { Item } from "./types";
import { resultsDue, scoreText, webScore } from "./webResults";

const ready = (id: number, difficulty: Slot["difficulty"]): Slot => ({
  key: `quiz-${difficulty}`,
  mode: "quiz",
  difficulty,
  source: "live",
  state: { kind: "ready", item: { id } as Item },
});
const waiting: Slot = {
  key: "quiz-hard",
  mode: "quiz",
  difficulty: "hard",
  source: "live",
  state: { kind: "waiting" },
};
const missed: Slot = { ...waiting, state: { kind: "missed", message: "x" } };

describe("webScore", () => {
  it("counts correct and incorrect among the questions answered", () => {
    const score = webScore(new Set([1, 2, 3]), new Set([1, 3]));
    expect(score).toEqual({ answered: 3, correct: 2, incorrect: 1 });
    expect(scoreText(score)).toBe("2 of 3");
  });

  it("counts only questions answered", () => {
    expect(webScore(new Set([1]), new Set([1, 2, 3]))).toEqual({
      answered: 1,
      correct: 1,
      incorrect: 0,
    });
    expect(webScore(new Set(), new Set())).toEqual({ answered: 0, correct: 0, incorrect: 0 });
  });
});

describe("resultsDue", () => {
  const easy = ready(1, "easy");
  const medium = ready(2, "medium");

  it("is due once every question that was not left out is answered", () => {
    expect(resultsDue([easy, medium, ready(3, "hard")], new Set([1, 2, 3]))).toBe(true);
    expect(resultsDue([easy, medium, missed], new Set([1, 2]))).toBe(true);
  });

  it("waits while a question is unanswered or still on its way", () => {
    expect(resultsDue([easy, medium], new Set([1]))).toBe(false);
    expect(resultsDue([easy, medium, waiting], new Set([1, 2]))).toBe(false);
  });

  it("keeps the usual flow when no question was made or answered", () => {
    expect(resultsDue([], new Set())).toBe(false);
    expect(resultsDue([missed, missed], new Set())).toBe(false);
    expect(resultsDue([easy], new Set())).toBe(false);
  });
});
