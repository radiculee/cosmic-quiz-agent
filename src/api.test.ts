import { describe, expect, it } from "vitest";

import { takeLines } from "./api";

describe("takeLines", () => {
  it("keeps an unfinished line for the next chunk", () => {
    expect(takeLines('{"a":1}\n{"b":')).toEqual([['{"a":1}'], '{"b":']);
    expect(takeLines('{"b":2}\n')).toEqual([['{"b":2}'], ""]);
  });

  it("skips blank lines", () => {
    expect(takeLines("\n\n{}\n")).toEqual([["{}"], ""]);
  });
});
