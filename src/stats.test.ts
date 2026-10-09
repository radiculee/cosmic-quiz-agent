import { describe, expect, it } from "vitest";

import {
  addCounts,
  agreement,
  ALL_RUNS,
  bankParts,
  cacheHitRatio,
  callBins,
  claimRows,
  confidenceBins,
  filterSummary,
  formatCount,
  formatPercent,
  formatSeconds,
  formatUsd,
  gateParts,
  gridHint,
  gridRange,
  headline,
  madeCounts,
  outcomeParts,
  reviewReasons,
  searchTotals,
  statsQuery,
  tokenTotals,
  topRows,
} from "./stats";
import { fromPlan, missed, resolved } from "./search";
import { sampleReply, sampleRun } from "./testing/samples";
import { DIFFICULTIES, MODES, type PlannedItem, type QuizQuestion } from "./types";

describe("statsQuery", () => {
  it("leaves out every filter set to all", () => {
    expect(statsQuery(ALL_RUNS)).toBe("");
  });

  it("names the filters in a fixed order, with the database's words", () => {
    expect(statsQuery({ mode: "quiz", level: "hard", source: "live", range: "7d" })).toBe(
      "mode=quiz&difficulty=hard&source=on_demand&days=7",
    );
    expect(statsQuery({ ...ALL_RUNS, range: "30d", source: "curator" })).toBe(
      "source=curator&days=30",
    );
  });
});

describe("formatting", () => {
  it("writes counts in full, then compact", () => {
    expect(formatCount(1284)).toBe("1,284");
    expect(formatCount(12_940)).toBe("12.9K");
    expect(formatCount(1_250_000)).toBe("1.3M");
  });

  it("gives dollars enough digits to mean something", () => {
    expect(formatUsd(5.333)).toBe("$5.33");
    expect(formatUsd(0.0544)).toBe("$0.054");
    expect(formatUsd(0.00262)).toBe("$0.0026");
    expect(formatUsd(0)).toBe("$0");
    expect(formatUsd(-0.004)).toBe("-$0.0040");
  });

  it("writes seconds, with a dash for nothing measured", () => {
    expect(formatSeconds(2.14)).toBe("2.1 s");
    expect(formatSeconds(123.4)).toBe("123 s");
    expect(formatSeconds(null)).toBe("-");
  });

  it("writes shares, never dividing by zero", () => {
    expect(formatPercent(51, 100)).toBe("51%");
    expect(formatPercent(1, 400)).toBe("<1%");
    expect(formatPercent(0, 0)).toBe("-");
  });
});

describe("the agent tab", () => {
  const { stats } = sampleReply();

  it("leads with runs, the gate's publish count, cost per item and the median run", () => {
    // ($0.08 + $0.016 + $0.0004) over 2 published items.
    expect(headline(stats)).toEqual({
      runs: 4,
      published: 2,
      costPerPublished: expect.closeTo(0.0482, 6) as number,
      medianRun: 20,
    });
  });

  it("splits outcomes and decisions with a meaning-based tone per part", () => {
    expect(outcomeParts(stats).map((part) => [part.label, part.value, part.tone])).toEqual([
      ["Answered", 3, "good"],
      ["Budget ran out", 0, "doubt"],
      ["Failed the code checks", 1, "bad"],
      ["No answer", 0, "neutral"],
      ["Model error", 0, "neutral"],
    ]);
    expect(gateParts(stats.volume.gate).map((part) => part.value)).toEqual([2, 1, 1]);
    expect(bankParts(stats).map((part) => part.label)).toEqual([
      "Published",
      "Review",
      "Discarded",
      "Retired",
    ]);
  });

  it("adds tokens over the models and works out the cache hit", () => {
    const tokens = tokenTotals(stats);
    expect(tokens).toEqual({ input: 1000, output: 100, cacheWrite: 1000, cacheRead: 8000 });
    expect(cacheHitRatio(tokens)).toBe(0.8);
    expect(cacheHitRatio({ input: 0, output: 0, cacheWrite: 0, cacheRead: 0 })).toBeNull();
  });

  it("fills the gaps in the model-call bins, so the axis is continuous", () => {
    expect(callBins(stats)).toEqual([
      { label: "3", value: 2 },
      { label: "4", value: 0 },
      { label: "5", value: 2 },
    ]);
  });

  it("labels Jev's confidence bins by where they start", () => {
    const bins = confidenceBins(stats);
    expect(bins.map((bin) => bin.label)).toEqual([
      "0.0",
      "0.1",
      "0.2",
      "0.3",
      "0.4",
      "0.5",
      "0.6",
      "0.7",
      "0.8",
      "0.9",
    ]);
    expect(bins.at(-1)?.value).toBe(16);
  });

  it("counts agreement on the diagonal only", () => {
    expect(agreement(stats)).toEqual({ same: 2, total: 3 });
  });

  it("lays out Jev's claims by kind, with every verdict", () => {
    const rows = claimRows(stats);
    expect(rows.map((row) => row.kind)).toEqual(["correct_answer", "distractor", "sentence"]);
    expect(rows[1]?.counts).toEqual({ supports: 0, contradicts: 5, says_nothing: 1 });
  });

  it("lists only the review reasons that happened, most common first", () => {
    expect(reviewReasons(stats)).toEqual([{ label: "Haiku doubted the explanation", value: 1 }]);
  });

  it("folds a long tail into Other, but never a single row", () => {
    const rows = [5, 4, 3, 2, 1].map((value) => ({ label: `site ${value}`, value }));
    expect(topRows(rows, 3).at(-1)).toEqual({ label: "Other", value: 3 });
    expect(topRows(rows.slice(0, 4), 3)).toHaveLength(4);
  });
});

describe("a live search", () => {
  it("adds every run's figures together", () => {
    const totals = searchTotals([
      sampleRun(),
      sampleRun({ mode: "learn", status: "discarded", pages_by_domain: { "arxiv.org": 3 } }),
    ]);
    expect(totals.runs).toBe(2);
    expect(totals.modelCalls).toBe(6);
    expect(totals.toolCalls).toBe(6);
    expect(totals.toolErrors).toBe(2);
    expect(totals.pages).toBe(5);
    expect(totals.jevChecks).toBe(20);
    expect(totals.anthropicUsd).toBeCloseTo(0.05, 6);
    expect(totals.typesafeUsd).toBeCloseTo(0.0002, 8);
    expect(totals.seconds).toBeCloseTo(35.2, 6);
    expect(totals.pagesByDomain).toEqual([
      { label: "arxiv.org", value: 3 },
      { label: "en.wikipedia.org", value: 1 },
      { label: "nasa.gov", value: 1 },
    ]);
  });

  it("has nothing to add for a search with no runs yet", () => {
    const totals = searchTotals([]);
    expect(totals.runs).toBe(0);
    expect(totals.pagesByDomain).toEqual([]);
  });

  it("adds name-to-count maps, biggest first and then by name", () => {
    expect(addCounts([{ b: 1, a: 1 }, { b: 2 }])).toEqual([
      { label: "b", value: 3 },
      { label: "a", value: 1 },
    ]);
  });
});

describe("the first view's words", () => {
  it("names the filter choice on its button", () => {
    expect(filterSummary(ALL_RUNS)).toBe("All runs, all time");
    expect(filterSummary({ mode: "quiz", level: "hard", source: "live", range: "7d" })).toBe(
      "Quiz, hard, live runs, last 7 days",
    );
    expect(filterSummary({ ...ALL_RUNS, range: "30d" })).toBe("All runs, last 30 days");
  });

  it("finds the mode and level published most and least", () => {
    const { stats } = sampleReply();
    const base = stats.grid[0];
    if (!base) {
      throw new Error("the sample has a grid cell");
    }
    const grid = [
      { ...base, mode: "learn" as const, difficulty: "easy" as const, runs: 10, published: 8 },
      { ...base, mode: "learn" as const, difficulty: "hard" as const, runs: 10, published: 3 },
      { ...base, mode: "quiz" as const, difficulty: "easy" as const, runs: 0, published: 0 },
    ];
    const range = gridRange({ ...stats, grid });
    expect(range?.high.difficulty).toBe("easy");
    expect(range?.low.difficulty).toBe("hard");
    expect(gridRange({ ...stats, grid: [] })).toBeNull();
    expect(gridHint({ ...stats, grid })).toBe(
      "From 30% published (learn hard) to 80% (learn easy)",
    );
  });

  it("says so when every cell publishes the same share", () => {
    const { stats } = sampleReply();
    const base = stats.grid[0];
    if (!base) {
      throw new Error("the sample has a grid cell");
    }
    const grid = MODES.flatMap((mode) =>
      DIFFICULTIES.map((difficulty) => ({ ...base, mode, difficulty, runs: 4, published: 2 })),
    );
    // 1 of 2 is the same share as 2 of 4; the first of equal cells is kept for both ends.
    grid[0] = { ...base, mode: "learn", difficulty: "easy", runs: 2, published: 1 };
    const range = gridRange({ ...stats, grid });
    expect(range?.high).toBe(grid[0]);
    expect(range?.low).toBe(grid[0]);
    expect(gridHint({ ...stats, grid })).toBe("50% published in every cell");
    expect(gridHint({ ...stats, grid: grid.slice(0, 4) })).toBe(
      "50% published in every cell with runs",
    );
    expect(gridHint({ ...stats, grid: grid.slice(0, 1) })).toBe(
      "Only learn easy has runs: 50% published",
    );
    expect(gridHint({ ...stats, grid: [] })).toBe("No runs yet");
  });

  it("counts what a search made out of what it set out to make", () => {
    const plan: PlannedItem[] = [
      { key: "learn-medium", mode: "learn", difficulty: "medium", source: "live" },
      { key: "quiz-medium", mode: "quiz", difficulty: "medium", source: "live" },
      { key: "quiz-easy", mode: "quiz", difficulty: "easy", source: "bank" },
      { key: "quiz-hard", mode: "quiz", difficulty: "hard", source: "live" },
    ];
    const question = (difficulty: "medium" | "hard", status: "published" | "review"): QuizQuestion => ({
      id: difficulty === "medium" ? 2 : 3,
      mode: "quiz",
      difficulty,
      topic: "Pulsars",
      question: "Q?",
      options: ["a", "b", "c", "d"],
      status,
    });
    let search = fromPlan(1, "Pulsars", plan);
    expect(madeCounts(search)).toEqual({ made: 0, planned: 3, review: 0, leftOut: 0 });
    search = resolved(search, "quiz-medium", question("medium", "published"));
    search = resolved(search, "quiz-hard", question("hard", "review"));
    search = missed(search, "learn-medium", "discarded");
    expect(madeCounts(search)).toEqual({ made: 2, planned: 3, review: 1, leftOut: 1 });
  });
});
