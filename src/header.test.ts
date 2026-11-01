import { describe, expect, it } from "vitest";

import { sectionOf } from "./components/SiteHeader";

describe("sectionOf", () => {
  it("puts the Learn pages under Learn", () => {
    expect(sectionOf("learn")).toBe("learn");
    expect(sectionOf("learn-topic")).toBe("learn");
  });

  it("puts Mission Control under Web with the web page", () => {
    expect(sectionOf("explore")).toBe("web");
    expect(sectionOf("explore-stats")).toBe("web");
  });

  it("marks Quiz, and nothing on the other pages", () => {
    expect(sectionOf("quiz")).toBe("quiz");
    expect(sectionOf("home")).toBeNull();
    expect(sectionOf("trophies")).toBeNull();
    expect(sectionOf("privacy")).toBeNull();
    expect(sectionOf("not-found")).toBeNull();
  });
});
