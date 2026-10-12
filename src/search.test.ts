import { describe, expect, it } from "vitest";

import {
  ended,
  explanationLock,
  explanationSlot,
  fromPlan,
  itemLabel,
  madeAnything,
  measured,
  missed,
  nextOpen,
  questionSlots,
  resolved,
  started,
  summarize,
  summaryLine,
} from "./search";
import { sampleRun } from "./testing/samples";
import type { LearnItem, PlannedItem, QuizQuestion } from "./types";

// A MEDIUM search on a topic the bank has an EASY question for: the questions first, the
// explanation last (agent/ondemand.py plan_search).
const PLAN: PlannedItem[] = [
  { key: "quiz-medium", mode: "quiz", difficulty: "medium", source: "live" },
  { key: "quiz-easy", mode: "quiz", difficulty: "easy", source: "bank" },
  { key: "quiz-hard", mode: "quiz", difficulty: "hard", source: "live" },
  { key: "learn-medium", mode: "learn", difficulty: "medium", source: "live" },
];

const EXPLANATION: LearnItem = {
  id: 1,
  mode: "learn",
  difficulty: "medium",
  topic: "Pulsars",
  explanation: "...",
  sources: [],
  source_check: { options: [], sentences: 0, sentences_supported: 0 },
  status: "published",
  doubts: [],
};

function question(id: number, difficulty: QuizQuestion["difficulty"]): QuizQuestion {
  return {
    id,
    mode: "quiz",
    difficulty,
    topic: "Pulsars",
    question: "Q?",
    options: ["a", "b", "c", "d"],
    status: "published",
  };
}

describe("a search's slots", () => {
  it("start waiting for live items and loading for bank items", () => {
    const search = fromPlan(1, "Pulsars", PLAN);

    expect(search.slots.map((slot) => slot.state.kind)).toEqual([
      "waiting",
      "loading",
      "waiting",
      "waiting",
    ]);
    expect(explanationSlot(search)?.key).toBe("learn-medium");
    expect(questionSlots(search).map((slot) => slot.key)).toEqual([
      "quiz-medium",
      "quiz-easy",
      "quiz-hard",
    ]);
  });

  it("follow the stream: researching, then ready or left out", () => {
    let search = fromPlan(1, "Pulsars", PLAN);
    search = started(search, "learn-medium");
    expect(explanationSlot(search)?.state.kind).toBe("researching");

    search = resolved(search, "learn-medium", EXPLANATION);
    search = started(search, "learn-medium"); // a late log line does not undo it
    expect(explanationSlot(search)?.state).toEqual({
      kind: "ready",
      item: EXPLANATION,
      revealToken: undefined,
    });

    search = missed(search, "quiz-medium", "Not backed by its sources.");
    search = resolved(search, "quiz-hard", question(3, "hard"), "token");
    const states = questionSlots(search).map((slot) => slot.state);
    expect(states[0]).toEqual({ kind: "missed", message: "Not backed by its sources." });
    expect(states[2]).toEqual({ kind: "ready", item: question(3, "hard"), revealToken: "token" });
  });

  it("leave out live items that never came when the stream ends, but keep loading bank items", () => {
    let search = fromPlan(1, "Pulsars", PLAN);
    search = resolved(search, "learn-medium", EXPLANATION);
    search = ended(search, "The search ended before this was made.");

    expect(search.ended).toBe(true);
    expect(search.slots.map((slot) => slot.state.kind)).toEqual([
      "missed",
      "loading",
      "missed",
      "ready",
    ]);
  });

  it("ignore events about items the plan does not have", () => {
    const search = fromPlan(1, "Pulsars", PLAN);
    expect(resolved(search, "learn-easy", EXPLANATION)).toEqual(search);
  });
});

describe("the question order", () => {
  it("skips questions that were left out", () => {
    let search = fromPlan(1, "Pulsars", PLAN);
    search = missed(search, "quiz-medium", "x");
    const questions = questionSlots(search);

    expect(nextOpen(questions, 0)).toBe(1); // the EASY question from the bank
    expect(nextOpen(questions, 2)).toBe(2); // HARD, still being researched
    expect(nextOpen(questions, 3)).toBeNull();
  });
});

describe("the explanation's lock", () => {
  function allQuestionsReady() {
    let search = fromPlan(1, "Pulsars", PLAN);
    search = resolved(search, "quiz-medium", question(2, "medium"), "token");
    search = resolved(search, "quiz-easy", question(9, "easy"));
    search = resolved(search, "quiz-hard", question(3, "hard"), "token");
    return search;
  }

  it("stays locked while any question is still to answer, ready or still coming", () => {
    const search = fromPlan(1, "Pulsars", PLAN);
    expect(explanationLock(search, new Set())).toEqual({ kind: "locked", left: 3 });

    const ready = resolved(allQuestionsReady(), "learn-medium", EXPLANATION);
    expect(explanationLock(ready, new Set([2, 9]))).toEqual({ kind: "locked", left: 1 });
  });

  it("opens once every question is answered and the explanation is ready", () => {
    const search = allQuestionsReady();
    expect(explanationLock(search, new Set([2, 9, 3]))).toEqual({ kind: "coming" });

    const ready = resolved(search, "learn-medium", EXPLANATION);
    expect(explanationLock(ready, new Set([2, 9, 3]))).toEqual({ kind: "open" });
  });

  it("does not wait for questions that were left out", () => {
    let search = fromPlan(1, "Pulsars", PLAN);
    search = missed(search, "quiz-medium", "x");
    search = resolved(search, "quiz-easy", question(9, "easy"));
    search = missed(search, "quiz-hard", "x");
    search = resolved(search, "learn-medium", EXPLANATION);

    expect(explanationLock(search, new Set())).toEqual({ kind: "locked", left: 1 });
    expect(explanationLock(search, new Set([9]))).toEqual({ kind: "open" });
  });

  it("opens as soon as it is ready when the search made no question", () => {
    let search = fromPlan(1, "Pulsars", PLAN);
    for (const key of ["quiz-medium", "quiz-easy", "quiz-hard"] as const) {
      search = missed(search, key, "x");
    }
    expect(explanationLock(search, new Set())).toEqual({ kind: "coming" });
    expect(explanationLock(resolved(search, "learn-medium", EXPLANATION), new Set())).toEqual({
      kind: "open",
    });
  });

  it("says why when the explanation was left out", () => {
    const search = missed(fromPlan(1, "Pulsars", PLAN), "learn-medium", "Not backed.");
    expect(explanationLock(search, new Set())).toEqual({ kind: "missed", message: "Not backed." });
  });

  it("is undefined for a plan without an explanation", () => {
    const search = fromPlan(1, "Pulsars", PLAN.filter((item) => item.mode === "quiz"));
    expect(explanationLock(search, new Set())).toBeUndefined();
  });
});

describe("the search summary", () => {
  it("counts the live items made and those in review", () => {
    let search = fromPlan(1, "Pulsars", PLAN);
    search = resolved(search, "learn-medium", EXPLANATION);
    search = resolved(search, "quiz-medium", { ...question(2, "medium"), status: "review" });
    search = resolved(search, "quiz-easy", question(9, "easy")); // from the bank: not counted
    search = ended(search, "x");

    expect(summarize(search)).toEqual({ made: 2, review: 1, live: 3 });
    expect(madeAnything(search)).toBe(true);
    expect(summaryLine(summarize(search))).toBe(
      "Made 2 of 3, saved to the bank. One is marked not fully verified and shown only to you until reviewed.",
    );
  });

  it("says so when the search made nothing", () => {
    const search = ended(fromPlan(1, "Pulsars", PLAN), "x");

    expect(madeAnything(search)).toBe(false);
    expect(summaryLine(summarize(search))).toMatch(/could not back any of it/);
  });
});

describe("itemLabel", () => {
  it("names an item by its level and kind", () => {
    expect(itemLabel("learn-medium")).toBe("MEDIUM explanation");
    expect(itemLabel("quiz-easy")).toBe("EASY question");
  });
});

describe("a search's runs", () => {
  it("keeps each run's figures once, in the order they arrived", () => {
    const search = fromPlan(1, "Pulsars", PLAN);
    const first = measured(search, "quiz-medium", sampleRun());
    const both = measured(first, "learn-medium", sampleRun({ mode: "learn" }));
    const again = measured(both, "quiz-medium", sampleRun({ model_calls: 9 }));
    expect(search.runs).toEqual([]);
    expect(again.runs.map((run) => run.key)).toEqual(["learn-medium", "quiz-medium"]);
    expect(again.runs[1]?.stats.model_calls).toBe(9);
  });
});
