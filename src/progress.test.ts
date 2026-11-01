import { describe, expect, it } from "vitest";

import {
  currentStage,
  stagesDone,
  statusLine,
  stillWorking,
  timeLeft,
  timeLeftText,
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

const running = (stage: "search" | "read" | "write" | "verify", startedAt = 2, at = 5): Slot =>
  slot({ kind: "researching", progress: { stage, status: `At ${stage}`, startedAt, at } });

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
    const item = { id: 1 } as Item;
    expect(stagesDone(slot({ kind: "ready", item }))).toBe(4);
    expect(stagesDone(slot({ kind: "missed", message: "x" }))).toBe(0);
  });
});

describe("currentStage", () => {
  it("is the reported stage of a running item, else none", () => {
    expect(currentStage(running("write"))).toBe("write");
    expect(currentStage(slot({ kind: "researching" }))).toBeNull();
    expect(currentStage(slot({ kind: "waiting" }))).toBeNull();
  });
});

describe("statusLine", () => {
  it("shows the real work the run reported", () => {
    expect(statusLine(running("read"))).toBe("At read");
  });

  it("says where an item stands when it has no work to name", () => {
    expect(statusLine(slot({ kind: "waiting" }))).toBe("Starting");
    expect(statusLine(slot({ kind: "researching" }))).toBe("Starting");
    expect(statusLine(slot({ kind: "loading" }, { source: "bank" }))).toBe("Loading from the bank");
    expect(statusLine(slot({ kind: "missed", message: "x" }))).toBe("Left out");
  });

  it("tells a bank item from a made one when ready", () => {
    const item = { id: 1 } as Item;
    expect(statusLine(slot({ kind: "ready", item }, { source: "bank" }))).toBe(
      "Ready, from the bank",
    );
    expect(statusLine(slot({ kind: "ready", item }))).toBe("Ready");
  });
});

describe("timeLeft", () => {
  it("gives a waiting item its whole estimate", () => {
    expect(timeLeft(slot({ kind: "waiting" }, { estimate_seconds: 20.2 }), 7)).toEqual({
      kind: "left",
      seconds: 21,
    });
  });

  it("counts down from the run's first progress", () => {
    expect(timeLeft(running("read", 2), 2)).toEqual({ kind: "left", seconds: 20 });
    expect(timeLeft(running("read", 2), 12.5)).toEqual({ kind: "left", seconds: 10 });
  });

  it("starts the count when the item is seen running if no progress came yet", () => {
    expect(timeLeft(slot({ kind: "researching" }), 9)).toEqual({ kind: "left", seconds: 20 });
  });

  it("says a run is over its usual time instead of showing zero or less", () => {
    expect(timeLeft(running("verify", 2), 22)).toEqual({ kind: "over" });
    expect(timeLeft(running("verify", 2), 40)).toEqual({ kind: "over" });
  });

  it("shows nothing for a bank item, a finished item or a level with no estimate", () => {
    const item = { id: 1 } as Item;
    expect(timeLeft(slot({ kind: "loading" }, { source: "bank" }), 3)).toBeNull();
    expect(timeLeft(slot({ kind: "ready", item }), 3)).toBeNull();
    expect(timeLeft(running("read", 2, 3), 3)).not.toBeNull();
    expect(timeLeft({ ...running("read"), estimate_seconds: null }, 3)).toBeNull();
    const { estimate_seconds: _unused, ...bare } = running("read");
    expect(timeLeft(bare, 3)).toBeNull();
  });
});

describe("timeLeftText", () => {
  it("words each case", () => {
    expect(timeLeftText({ kind: "left", seconds: 12 })).toBe("About 12 s left");
    expect(timeLeftText({ kind: "over" })).toBe("Taking longer than usual");
    expect(timeLeftText(null)).toBe("");
  });
});

describe("stillWorking", () => {
  it("is true while any item is waiting, running or loading", () => {
    const item = { id: 1 } as Item;
    const done = slot({ kind: "ready", item });
    expect(stillWorking([done, slot({ kind: "waiting" })])).toBe(true);
    expect(stillWorking([done, running("read")])).toBe(true);
    expect(stillWorking([done, slot({ kind: "loading" }, { source: "bank" })])).toBe(true);
    expect(stillWorking([done, slot({ kind: "missed", message: "x" })])).toBe(false);
  });
});
