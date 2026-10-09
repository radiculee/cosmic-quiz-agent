import { describe, expect, it } from "vitest";

import { columnLayout, fillRatio, horizontalBar, splitLayout, verticalBar } from "./geometry";

describe("bar shapes", () => {
  it("rounds only the data end of a horizontal bar", () => {
    expect(horizontalBar(0, 0, 100, 12)).toBe(
      "M0,0 H96 A4,4 0 0 1 100,4 V8 A4,4 0 0 1 96,12 H0 Z",
    );
  });

  it("shrinks the rounding to fit a very short bar", () => {
    expect(horizontalBar(0, 0, 2, 12)).toBe("M0,0 H0 A2,2 0 0 1 2,2 V10 A2,2 0 0 1 0,12 H0 Z");
  });

  it("rounds only the top of a column", () => {
    expect(verticalBar(10, 100, 20, 50)).toBe(
      "M10,100 V54 A4,4 0 0 1 14,50 H26 A4,4 0 0 1 30,54 V100 Z",
    );
  });
});

describe("splitLayout", () => {
  it("shares the width by value with a 2px gap between parts", () => {
    expect(splitLayout([3, 1], 102)).toEqual([
      { index: 0, x: 0, width: 75 },
      { index: 1, x: 77, width: 25 },
    ]);
  });

  it("leaves out empty parts and keeps a sliver for a tiny one", () => {
    const segments = splitLayout([1000, 0, 1], 202);
    expect(segments.map((segment) => segment.index)).toEqual([0, 2]);
    expect(segments[1]?.width).toBe(2);
    const last = segments.at(-1);
    expect(last ? last.x + last.width : 0).toBeCloseTo(202, 6);
  });

  it("draws nothing for an empty whole or no width", () => {
    expect(splitLayout([0, 0], 100)).toEqual([]);
    expect(splitLayout([1], 0)).toEqual([]);
  });
});

describe("columnLayout", () => {
  it("caps columns at 24px, centred in their band", () => {
    expect(columnLayout(2, 100)).toEqual([
      { x: 13, width: 24 },
      { x: 63, width: 24 },
    ]);
  });

  it("keeps a 2px gap when the bands are narrow", () => {
    const [first, second] = columnLayout(10, 100);
    expect(first?.width).toBe(8);
    expect(second && first ? second.x - (first.x + first.width) : 0).toBe(2);
  });
});

describe("fillRatio", () => {
  it("stops at the cap", () => {
    expect(fillRatio(5.33, 10)).toBeCloseTo(0.533, 6);
    expect(fillRatio(12, 10)).toBe(1);
    expect(fillRatio(1, 0)).toBe(0);
  });
});
