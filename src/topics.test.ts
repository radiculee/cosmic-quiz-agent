import { describe, expect, it } from "vitest";

import {
  filterTopics,
  findTopic,
  randomTopic,
  searchStatus,
  suggest,
  suggestAny,
  topicStatus,
} from "./topics";
import type { BankTopic } from "./types";

const TOPICS: BankTopic[] = [
  { name: "Quasars", kind: "evergreen", learn: ["easy", "medium", "hard"], quiz: ["hard"] },
  { name: "Dark energy", kind: "evergreen", learn: ["easy"], quiz: ["easy", "medium"] },
  { name: "Sagittarius A*", kind: "evergreen", learn: ["medium"], quiz: ["easy"] },
  { name: "Magnetars", kind: "evergreen", learn: ["easy"], quiz: ["easy"] },
];

describe("findTopic", () => {
  it("ignores case and extra spaces", () => {
    expect(findTopic(TOPICS, "  dark   ENERGY ")?.name).toBe("Dark energy");
    expect(findTopic(TOPICS, "")).toBeUndefined();
  });
});

describe("suggest", () => {
  it("lists only topics playable at the mode and difficulty, prefix matches first", () => {
    const names = suggest(TOPICS, "a", "quiz", "easy").map((t) => t.name);
    expect(names).toEqual(["Dark energy", "Magnetars", "Sagittarius A*"]);
    expect(suggest(TOPICS, "ma", "quiz", "easy").map((t) => t.name)).toEqual([
      "Magnetars",
    ]);
  });

  it("shows everything playable for an empty query", () => {
    expect(suggest(TOPICS, "", "learn", "easy")).toHaveLength(3);
  });
});

describe("filterTopics", () => {
  it("lists every match for the grid, with no cap", () => {
    const many: BankTopic[] = Array.from({ length: 12 }, (_, i) => ({
      name: `Nebula ${String(i).padStart(2, "0")}`,
      kind: "evergreen",
      learn: ["easy"],
      quiz: [],
    }));
    expect(filterTopics(many, "neb", "learn", "easy")).toHaveLength(12);
    expect(suggest(many, "neb", "learn", "easy")).toHaveLength(8);
    expect(filterTopics(TOPICS, "", "learn", "easy").map((t) => t.name)).toEqual([
      "Dark energy",
      "Magnetars",
      "Quasars",
    ]);
  });
});

describe("randomTopic", () => {
  it("picks a playable topic other than the current one", () => {
    const picked = randomTopic(TOPICS, "quiz", "easy", "Dark energy", () => 0);
    expect(picked?.name).toBe("Sagittarius A*");
  });

  it("prefers topics not yet played, then any other", () => {
    expect(randomTopic(TOPICS, "quiz", "easy", "", () => 0, ["Dark energy"])?.name).toBe(
      "Sagittarius A*",
    );
    const all = ["Dark energy", "Sagittarius A*", "Magnetars"];
    expect(randomTopic(TOPICS, "quiz", "easy", "Magnetars", () => 0, all)?.name).toBe(
      "Dark energy",
    );
  });

  it("falls back to the current topic when it is the only one", () => {
    expect(randomTopic(TOPICS, "quiz", "hard", "Quasars", () => 0.5)?.name).toBe("Quasars");
    expect(randomTopic(TOPICS, "learn", "hard", "", () => 0)?.name).toBe("Quasars");
  });
});

describe("topicStatus", () => {
  it("tells ready, unknown and available-elsewhere apart", () => {
    expect(topicStatus(TOPICS, "", "quiz", "easy").kind).toBe("empty");
    expect(topicStatus(TOPICS, "quasars", "quiz", "hard").kind).toBe("ready");
    expect(topicStatus(TOPICS, "Pulsars", "quiz", "hard").kind).toBe("unknown");
    expect(topicStatus(TOPICS, "Quasars", "quiz", "easy")).toEqual({
      kind: "elsewhere",
      topic: TOPICS[0],
      difficulties: ["hard"],
    });
  });
});

describe("suggestAny", () => {
  it("suggests every bank topic that matches, whatever it has", () => {
    expect(suggestAny(TOPICS, "a").map((t) => t.name)).toEqual([
      "Dark energy",
      "Magnetars",
      "Quasars",
      "Sagittarius A*",
    ]);
  });
});

describe("searchStatus", () => {
  it("counts what a search would make: a question and an explanation at each level", () => {
    expect(searchStatus(TOPICS, " ")).toEqual({ kind: "empty" });
    expect(searchStatus(TOPICS, "Pulsars")).toEqual({ kind: "new" });
    // Quasars: explanations at every level, but a question only at HARD.
    expect(searchStatus(TOPICS, "quasars")).toEqual({
      kind: "partial",
      topic: TOPICS[0],
      missing: 2,
    });
    // Sagittarius A*: an explanation only at MEDIUM and a question only at EASY.
    expect(searchStatus(TOPICS, "Sagittarius A*")).toMatchObject({ missing: 4 });
  });

  it("is complete, and so free, only when the bank has every item", () => {
    const full: BankTopic = {
      name: "Pulsars",
      kind: "custom",
      learn: ["easy", "medium", "hard"],
      quiz: ["easy", "medium", "hard"],
    };
    expect(searchStatus([full], "pulsars")).toEqual({ kind: "complete", topic: full });
    const noHardExplanation: BankTopic = { ...full, learn: ["easy", "medium"] };
    expect(searchStatus([noHardExplanation], "pulsars")).toMatchObject({
      kind: "partial",
      missing: 1,
    });
  });
});
