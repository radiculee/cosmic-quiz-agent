import { describe, expect, it } from "vitest";

import { EVAL_HISTORY } from "./evals";
import { isEvalHistory, isRunStats, isStatsReply } from "./shapes";
import { sampleReply, sampleRun } from "./testing/samples";

describe("a live run's figures", () => {
  it("accepts what agent/run_stats.py sends", () => {
    expect(isRunStats(sampleRun())).toBe(true);
    expect(isRunStats(sampleRun({ status: null, haiku: null, jev: null }))).toBe(true);
  });

  it("refuses figures of another shape", () => {
    expect(isRunStats({ ...sampleRun(), outcome: "exploded" })).toBe(false);
    expect(isRunStats({ ...sampleRun(), tool_calls: { fetch_page: "two" } })).toBe(false);
    expect(isRunStats({ ...sampleRun(), model_calls: -1 })).toBe(false);
    const { steps: _steps, ...withoutSteps } = sampleRun();
    expect(isRunStats(withoutSteps)).toBe(false);
  });
});

describe("the agent's statistics", () => {
  it("accepts what /api/stats sends", () => {
    expect(isStatsReply(sampleReply())).toBe(true);
  });

  it("accepts a saving below zero, when cache writes cost more than the reads saved", () => {
    const reply = sampleReply();
    expect(isStatsReply({ ...reply, caching: { ...reply.caching, saved_usd: -0.001 } })).toBe(true);
  });

  it("refuses a reply missing a count, with an unknown key, or with the wrong bins", () => {
    const reply = sampleReply();
    const { review: _review, ...gate } = reply.stats.volume.gate as Record<string, number>;
    expect(isStatsReply({ ...reply, stats: { ...reply.stats, volume: { ...reply.stats.volume, gate } } })).toBe(
      false,
    );
    const outcomes = { ...reply.stats.volume.outcomes, exploded: 1 };
    expect(
      isStatsReply({ ...reply, stats: { ...reply.stats, volume: { ...reply.stats.volume, outcomes } } }),
    ).toBe(false);
    const verifiers = {
      ...reply.stats.verifiers,
      jev_confidence: { bins: [1, 2, 3], exactly_one: 0 },
    };
    expect(isStatsReply({ ...reply, stats: { ...reply.stats, verifiers } })).toBe(false);
  });
});

describe("the eval history", () => {
  it("is built into the page in the shape the export writes", () => {
    expect(EVAL_HISTORY).not.toBeNull();
    expect(EVAL_HISTORY?.generation.length).toBeGreaterThan(0);
  });

  it("refuses a history of another shape", () => {
    expect(isEvalHistory({ generation: [{ run: "x" }], ontopic: [] })).toBe(false);
    expect(isEvalHistory({ generation: [] })).toBe(false);
  });
});
