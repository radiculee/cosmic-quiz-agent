import { describe, expect, it } from "vitest";

import { irishTime, quotaLine, quotaShort } from "./quota";
import type { Quota } from "./types";

// The visitor's count resets at midnight UTC (agent/limits.py).
const SUMMER_RESET = "2026-10-09T00:00:00Z";
const WINTER_RESET = "2026-10-26T00:00:00Z";

function quota(remaining: number, globalOpen = true): Quota {
  return { remaining, limit: 2, resets_at: SUMMER_RESET, global_open: globalOpen };
}

describe("the reset time", () => {
  it("is shown in Irish time, so it follows the clocks going back on 25 October", () => {
    expect(irishTime(SUMMER_RESET)).toBe("01:00");
    expect(irishTime(WINTER_RESET)).toBe("00:00");
  });
});

describe("quota wording", () => {
  it("counts down on the web page and names the reset", () => {
    expect(quotaLine(quota(1))).toBe("1 of 2 left today, resets at 01:00 Irish time.");
    expect(quotaLine(quota(0))).toBe(
      "You have used today's 2 live searches. The count resets at 01:00 Irish time.",
    );
  });

  it("is short on the home page card", () => {
    expect(quotaShort(quota(2))).toBe("2 of 2 left today");
    expect(quotaShort(quota(0))).toBe("None left today");
    expect(quotaShort(quota(2, false))).toBe("Paused for now");
  });
});
