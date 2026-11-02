import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SearchProgress } from "./components/SearchProgress";
import type { Search, Slot } from "./search";
import type { Item } from "./types";

const item = { id: 1 } as Item;
const slot = (
  key: Slot["key"],
  difficulty: Slot["difficulty"],
  state: Slot["state"],
): Slot => ({
  key,
  mode: key.startsWith("learn") ? "learn" : "quiz",
  difficulty,
  source: "live",
  state,
});

const working: Search = {
  id: 1,
  topic: "Pulsars",
  runs: [],
  ended: false,
  slots: [
    slot("quiz-easy", "easy", {
      kind: "researching",
      progress: { stage: "read", status: "Reading nasa.gov", startedAt: 0, at: 4 },
    }),
    slot("quiz-medium", "medium", { kind: "waiting" }),
    slot("quiz-hard", "hard", { kind: "waiting" }),
    slot("learn-easy", "easy", { kind: "ready", item }),
    slot("learn-medium", "medium", { kind: "waiting" }),
    slot("learn-hard", "hard", { kind: "waiting" }),
  ],
};

function render(search: Search, detailsOpen = false, message: string | null = null): string {
  return renderToStaticMarkup(
    <SearchProgress
      search={search}
      message={message}
      detailsOpen={detailsOpen}
      onToggleDetails={() => {}}
      details={<p>THE LOG</p>}
    />,
  );
}

describe("SearchProgress", () => {
  it("has three bars, Easy, Medium and Hard, each with one word", () => {
    const html = render(working);
    expect(html.match(/<li /g)).toHaveLength(3);
    expect(html.indexOf("Easy")).toBeLessThan(html.indexOf("Medium"));
    expect(html.indexOf("Medium")).toBeLessThan(html.indexOf("Hard"));
    expect(html).toContain("Researching");
    expect(html.match(/Waiting/g)).toHaveLength(2);
  });

  it("gives a screen reader the step as text, and has no status line or countdown", () => {
    const html = render(working);
    expect(html).toContain("step 2 of 4");
    expect(html).not.toContain("Reading nasa.gov");
    expect(html).not.toContain(" left");
  });

  it("counts the explanations ready below the bars", () => {
    expect(render(working)).toContain("Explanations: 1 of 3 ready");
  });

  it("puts the log behind a Show details button that reports its state", () => {
    expect(render(working, false)).toContain('aria-expanded="false"');
    expect(render(working, false)).toContain("Show details");
    expect(render(working, true)).toContain('aria-expanded="true"');
    expect(render(working, true)).toContain("Hide details");
    expect(render(working, false)).toMatch(/id="search-details" hidden=""/);
    expect(render(working, true)).not.toMatch(/id="search-details" hidden/);
  });

  it("shrinks to one line, with the outcome text, once every item has ended", () => {
    const done: Search = {
      ...working,
      ended: true,
      slots: working.slots.map((s) => ({ ...s, state: { kind: "missed" as const, message: "x" } })),
    };
    const html = render(done, false, "The agent is unavailable just now.");
    expect(html).not.toContain("<li ");
    expect(html).toContain("The agent is unavailable just now.");
    expect(html).toContain("Show details");
  });
});
