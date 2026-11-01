import { describe, expect, it } from "vitest";

import { searchOutcome, UNAVAILABLE_MESSAGE } from "./outcome";
import type { Search, Slot } from "./search";
import type { Item } from "./types";

function search(state: Slot["state"]): Search {
  const slot: Slot = { key: "quiz-easy", mode: "quiz", difficulty: "easy", source: "live", state };
  return { id: 1, ended: true, slots: [slot] } as unknown as Search;
}

const missed = search({ kind: "missed", message: "x" });

describe("searchOutcome", () => {
  it("says the agent is unavailable when the stream said so and nothing was made", () => {
    expect(searchOutcome(missed, true)).toEqual({ kind: "nothing", message: UNAVAILABLE_MESSAGE });
    expect(UNAVAILABLE_MESSAGE).toBe(
      "The agent is unavailable just now. This search was not counted. Topics in the bank are still free to play.",
    );
  });

  it("keeps the usual text for every other case", () => {
    expect(searchOutcome(missed, false).message).toMatch(/could not back any of it/);
    const made = search({ kind: "ready", item: { id: 1, status: "published" } as Item });
    expect(searchOutcome(made, false).kind).toBe("done");
    expect(searchOutcome(made, true).message).toMatch(/^Made 1 of 1/);
  });
});
