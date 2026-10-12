import { describe, expect, it } from "vitest";

import { atEnd, END_SLACK, startsOffScreen, stillFollowing } from "./scroll";

describe("atEnd", () => {
  it("is true at the end of the box and within the slack of it", () => {
    expect(atEnd({ scrollTop: 600, scrollHeight: 1000, clientHeight: 400 })).toBe(true);
    expect(atEnd({ scrollTop: 600 - END_SLACK, scrollHeight: 1000, clientHeight: 400 })).toBe(true);
  });

  it("is false once the reader has scrolled up to read earlier lines", () => {
    expect(atEnd({ scrollTop: 600 - END_SLACK - 1, scrollHeight: 1000, clientHeight: 400 })).toBe(
      false,
    );
    expect(atEnd({ scrollTop: 0, scrollHeight: 1000, clientHeight: 400 })).toBe(false);
  });

  it("is true for a box that does not overflow yet", () => {
    expect(atEnd({ scrollTop: 0, scrollHeight: 300, clientHeight: 384 })).toBe(true);
  });
});

describe("stillFollowing", () => {
  it("keeps following when the log's own scroll is reported after more lines arrived", () => {
    // The log put the box at 600; two more lines (60 px) came before the scroll event.
    expect(stillFollowing({ scrollTop: 600, scrollHeight: 1060, clientHeight: 400 }, 600)).toBe(
      true,
    );
  });

  it("stops once the reader scrolls up from where the log put it", () => {
    expect(stillFollowing({ scrollTop: 450, scrollHeight: 1060, clientHeight: 400 }, 600)).toBe(
      false,
    );
    expect(stillFollowing({ scrollTop: 0, scrollHeight: 1060, clientHeight: 400 }, 600)).toBe(false);
  });

  it("follows again once the reader scrolls back to the end", () => {
    expect(stillFollowing({ scrollTop: 660, scrollHeight: 1060, clientHeight: 400 }, 600)).toBe(
      true,
    );
  });
});

describe("startsOffScreen", () => {
  it("is false for a top anywhere on the screen", () => {
    expect(startsOffScreen(0, 844)).toBe(false);
    expect(startsOffScreen(500, 844)).toBe(false);
    expect(startsOffScreen(843, 844)).toBe(false);
  });

  it("is true above the screen and below it", () => {
    expect(startsOffScreen(-1, 844)).toBe(true);
    expect(startsOffScreen(-900, 844)).toBe(true);
    expect(startsOffScreen(844, 844)).toBe(true);
  });
});
