import { describe, expect, it } from "vitest";

import {
  barState,
  explanationLine,
  finishedLine,
  questionBars,
  stagesDone,
  stillWorking,
} from "./progress";
import type { Slot } from "./search";
import type { Item } from "./types";

function slot(state: Slot["state"], extra: Partial<Slot> = {}): Slot {
  return {
    key: "quiz-easy",
    mode: "quiz",
    difficulty: "easy",
    source: "live",
    estimate_seconds: 20,
    state,
    ...extra,
  };
}

const item = { id: 1 } as Item;
const running = (stage: "search" | "read" | "write" | "verify"): Slot =>
  slot({ kind: "researching", progress: { stage, status: `At ${stage}`, startedAt: 2, at: 5 } });

describe("stagesDone", () => {
  it("moves with the stage the run reports, and not with time", () => {
    expect(stagesDone(slot({ kind: "waiting" }))).toBe(0);
    expect(stagesDone(slot({ kind: "researching" }))).toBe(0);
    expect(stagesDone(running("search"))).toBe(0);
    expect(stagesDone(running("read"))).toBe(1);
    expect(stagesDone(running("write"))).toBe(2);
    expect(stagesDone(running("verify"))).toBe(3);
  });

  it("is all four once the item is ready, and none for one left out", () => {
    expect(stagesDone(slot({ kind: "ready", item }))).toBe(4);
    expect(stagesDone(slot({ kind: "missed", message: "x" }))).toBe(0);
  });
});

describe("barState", () => {
  it("names the four states", () => {
    expect(barState(slot({ kind: "waiting" }))).toBe("waiting");
    expect(barState(running("read"))).toBe("researching");
    expect(barState(slot({ kind: "ready", item }))).toBe("ready");
    expect(barState(slot({ kind: "missed", message: "x" }))).toBe("left out");
  });

  it("counts a bank item as ready, even while it loads", () => {
    expect(barState(slot({ kind: "loading" }, { source: "bank" }))).toBe("ready");
  });
});

describe("questionBars", () => {
  const slots = [
    slot({ kind: "ready", item }, { key: "quiz-easy", difficulty: "easy" }),
    slot({ kind: "waiting" }, { key: "quiz-medium", difficulty: "medium" }),
    slot({ kind: "waiting" }, { key: "quiz-hard", difficulty: "hard" }),
    slot({ kind: "waiting" }, { key: "learn-easy", mode: "learn", difficulty: "easy" }),
  ];

  it("has one bar for each question and none for an explanation", () => {
    expect(questionBars(slots).map((bar) => bar.level)).toEqual(["Easy", "Medium", "Hard"]);
  });

  it("gives each its word and its fill from the real stage", () => {
    const [easy, medium] = questionBars(slots);
    expect(easy).toMatchObject({ word: "Ready", done: 4, step: null });
    expect(medium).toMatchObject({ word: "Waiting", done: 0 });
    const [midway] = questionBars([running("write")]);
    expect(midway).toMatchObject({ word: "Researching", done: 2, step: "step 3 of 4" });
  });

  it("fills a ready bank item and empties one left out", () => {
    const [bank] = questionBars([slot({ kind: "loading" }, { source: "bank" })]);
    expect(bank).toMatchObject({ word: "Ready", done: 4 });
    const [left] = questionBars([slot({ kind: "missed", message: "x" })]);
    expect(left).toMatchObject({ word: "Left out", done: 0 });
  });
});

describe("explanationLine", () => {
  const explanation = (state: Slot["state"], difficulty: Slot["difficulty"]): Slot =>
    slot(state, { key: `learn-${difficulty}`, mode: "learn", difficulty });

  it("counts the explanations ready out of those this search has", () => {
    const slots = [
      explanation({ kind: "ready", item }, "easy"),
      explanation({ kind: "waiting" }, "medium"),
      explanation({ kind: "waiting" }, "hard"),
    ];
    expect(explanationLine(slots)).toBe("Explanations: 1 of 3 ready");
    expect(explanationLine(slots.slice(0, 2))).toBe("Explanations: 1 of 2 ready");
  });

  it("is null when the search has no explanation", () => {
    expect(explanationLine([slot({ kind: "waiting" })])).toBeNull();
  });
});

describe("finishedLine", () => {
  it("says how much of the search is ready", () => {
    const slots = [
      slot({ kind: "ready", item }),
      slot({ kind: "missed", message: "x" }, { key: "quiz-medium", difficulty: "medium" }),
      slot({ kind: "ready", item }, { key: "learn-easy", mode: "learn" }),
    ];
    expect(finishedLine(slots)).toBe(
      "Search finished: 1 of 2 questions and 1 of 1 explanations ready.",
    );
  });
});

describe("stillWorking", () => {
  it("is true while any item is waiting, running or loading", () => {
    const done = slot({ kind: "ready", item });
    expect(stillWorking([done, slot({ kind: "waiting" })])).toBe(true);
    expect(stillWorking([done, running("read")])).toBe(true);
    expect(stillWorking([done, slot({ kind: "loading" }, { source: "bank" })])).toBe(true);
    expect(stillWorking([done, slot({ kind: "missed", message: "x" })])).toBe(false);
  });
});
