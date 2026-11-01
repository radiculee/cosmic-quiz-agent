import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SearchProgress } from "./components/SearchProgress";
import type { Slot } from "./search";
import type { Item } from "./types";

const slots: Slot[] = [
  {
    key: "quiz-easy",
    mode: "quiz",
    difficulty: "easy",
    source: "live",
    estimate_seconds: 20,
    state: {
      kind: "researching",
      progress: { stage: "read", status: "Reading nasa.gov", startedAt: 0, at: 4 },
    },
  },
  {
    key: "quiz-medium",
    mode: "quiz",
    difficulty: "medium",
    source: "live",
    estimate_seconds: 25,
    state: { kind: "waiting" },
  },
  {
    key: "learn-easy",
    mode: "learn",
    difficulty: "easy",
    source: "bank",
    state: { kind: "ready", item: { id: 1 } as Item },
  },
];

function render(detailsOpen = false): string {
  return renderToStaticMarkup(
    <SearchProgress slots={slots} detailsOpen={detailsOpen} onToggleDetails={() => {}} />,
  );
}

describe("SearchProgress", () => {
  it("has one row per item, in the order given, each with its label", () => {
    const html = render();
    expect(html.match(/<li class="py-3/g)).toHaveLength(3);
    expect(html.indexOf("EASY question")).toBeLessThan(html.indexOf("MEDIUM question"));
    expect(html.indexOf("MEDIUM question")).toBeLessThan(html.indexOf("EASY explanation"));
  });

  it("names the real work a run reported and the step it is on", () => {
    const html = render();
    expect(html).toContain("Reading nasa.gov");
    expect(html).toContain("step 2 of 4");
  });

  it("shows the time left from the estimate, and a bank item has none", () => {
    const html = render();
    expect(html).toContain("About 20 s left");
    expect(html).toContain("About 25 s left");
    expect(html).toContain("Ready, from the bank");
  });

  it("puts the log behind a Show details button that reports its state", () => {
    expect(render(false)).toContain('aria-expanded="false"');
    expect(render(false)).toContain("Show details");
    expect(render(true)).toContain('aria-expanded="true"');
    expect(render(true)).toContain("Hide details");
  });
});
