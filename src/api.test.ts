import { describe, expect, it } from "vitest";

import { ApiError, isResearchEvent, reportFailureMessage, takeLines } from "./api";
import { sampleRun } from "./testing/samples";

describe("takeLines", () => {
  it("keeps an unfinished line for the next chunk", () => {
    expect(takeLines('{"a":1}\n{"b":')).toEqual([['{"a":1}'], '{"b":']);
    expect(takeLines('{"b":2}\n')).toEqual([['{"b":2}'], ""]);
  });

  it("skips blank lines", () => {
    expect(takeLines("\n\n{}\n")).toEqual([["{}"], ""]);
  });
});

const QUESTION = {
  id: 7,
  mode: "quiz",
  difficulty: "easy",
  topic: "Pulsars",
  question: "Q?",
  options: ["a", "b", "c", "d"],
  status: "published",
};

describe("research events", () => {
  it("accepts a plan of named items", () => {
    const plan = {
      type: "plan",
      topic: "Pulsars",
      items: [
        { key: "learn-medium", mode: "learn", difficulty: "medium", source: "live" },
        { key: "quiz-easy", mode: "quiz", difficulty: "easy", source: "bank" },
      ],
    };
    expect(isResearchEvent(plan)).toBe(true);
    const mislabelled = { ...plan, items: [{ ...plan.items[0], key: "quiz-medium" }] };
    expect(isResearchEvent(mislabelled)).toBe(false);
  });

  it("accepts log lines about the search or one of its items", () => {
    const line = {
      type: "log",
      key: "quiz-easy",
      label: "fetch_page",
      detail: "en.wikipedia.org/wiki/Pulsar",
      tone: "info",
      verdict: null,
      confidence: null,
      seconds: 3.1,
    };
    expect(isResearchEvent(line)).toBe(true);
    expect(isResearchEvent({ ...line, key: null })).toBe(true);
    expect(isResearchEvent({ ...line, key: "quiz-impossible" })).toBe(false);
  });

  it("accepts a result only for the item its key names", () => {
    const result = { type: "result", key: "quiz-easy", item: QUESTION, reveal_token: "t" };
    expect(isResearchEvent(result)).toBe(true);
    expect(isResearchEvent({ ...result, key: "quiz-hard" })).toBe(false);
  });

  it("accepts missed items and refuses the reasons the server no longer sends", () => {
    const missedItem = {
      type: "missed",
      key: "quiz-hard",
      reason: "skipped",
      message: "Not started. The search ran out of time.",
    };
    expect(isResearchEvent(missedItem)).toBe(true);
    expect(isResearchEvent({ ...missedItem, reason: "lost" })).toBe(false);
    expect(isResearchEvent({ type: "fallback", reason: "limit", message: "m" })).toBe(true);
    expect(isResearchEvent({ type: "fallback", reason: "in_bank", message: "m" })).toBe(false);
  });
});

describe("a run's figures", () => {
  it("accepts figures for the run the key names, and nothing else", () => {
    const stats = sampleRun();
    expect(isResearchEvent({ type: "stats", key: "quiz-medium", stats })).toBe(true);
    expect(isResearchEvent({ type: "stats", key: "quiz-easy", stats })).toBe(false);
    expect(isResearchEvent({ type: "stats", key: "quiz-medium", stats: { ...stats, cost: null } })).toBe(
      false,
    );
  });
});

describe("reportFailureMessage", () => {
  it("passes on the server's words for the daily limit", () => {
    const limit = new ApiError("You have sent 10 reports today, the daily limit.", 429);
    expect(reportFailureMessage(limit)).toBe("You have sent 10 reports today, the daily limit.");
  });

  it("keeps any other failure general", () => {
    const general = "The report could not be sent. Try again in a moment.";
    expect(reportFailureMessage(new ApiError("There is no such item.", 404))).toBe(general);
    expect(reportFailureMessage(new TypeError("Failed to fetch"))).toBe(general);
  });
});
