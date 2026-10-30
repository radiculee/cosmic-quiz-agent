import { describe, expect, it } from "vitest";

import { editDistance, knownPaths, redirectFor, suggestionsFor } from "./closeMatch";
import type { BankTopic } from "./types";

function topic(name: string): BankTopic {
  return { name, kind: "evergreen", learn: ["easy"], quiz: ["easy"] };
}

const TOPICS = [topic("Antimatter"), topic("Black holes"), topic("Europa's hidden ocean")];
const PATHS = knownPaths(TOPICS);

describe("editDistance", () => {
  it("counts insertions, deletions, replacements and swaps", () => {
    expect(editDistance("learn", "learn")).toBe(0);
    expect(editDistance("lern", "learn")).toBe(1);
    expect(editDistance("lerarn", "learn")).toBe(1);
    expect(editDistance("laern", "learn")).toBe(1);
    expect(editDistance("", "quiz")).toBe(4);
  });
});

describe("knownPaths", () => {
  it("lists the pages and a path for each topic, without the home page", () => {
    expect(PATHS).toContain("/learn");
    expect(PATHS).toContain("/learn/antimatter");
    expect(PATHS).toContain("/learn/europas-hidden-ocean");
    expect(PATHS).not.toContain("/");
  });
});

describe("redirectFor", () => {
  it("sends a near miss to the page it meant", () => {
    expect(redirectFor("/lern", PATHS)).toBe("/learn");
    expect(redirectFor("/quizz", PATHS)).toBe("/quiz");
    expect(redirectFor("/privcy/", PATHS)).toBe("/privacy");
  });

  it("sends a mistyped topic to the topic", () => {
    expect(redirectFor("/learn/antimater", PATHS)).toBe("/learn/antimatter");
    expect(redirectFor("/Learn/Black-Hole", PATHS)).toBe("/learn/black-holes");
  });

  it("leaves a path that is far from everything, or already right", () => {
    expect(redirectFor("/zzzzzz", PATHS)).toBeNull();
    expect(redirectFor("/learn", PATHS)).toBeNull();
    expect(redirectFor("/learn/dark-matter-halos-of-spiral-galaxies", PATHS)).toBeNull();
  });

  it("does not guess between two equally close paths", () => {
    expect(redirectFor("/ab", ["/aa", "/bb"])).toBeNull();
  });
});

describe("suggestionsFor", () => {
  it("offers the nearest paths first, at most three", () => {
    const found = suggestionsFor("/learn/black", PATHS);
    expect(found[0]).toBe("/learn/black-holes");
    expect(found.length).toBeLessThanOrEqual(3);
  });

  it("offers nothing for a path unlike any", () => {
    expect(suggestionsFor("/qwertyuiopasdf", PATHS)).toEqual([]);
  });
});
