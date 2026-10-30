import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AgentLog, type LogLine } from "./AgentLog";

const LINES: LogLine[] = [
  { key: null, label: "On-topic check (Jev)", detail: "astronomy 0.99", tone: "ok", verdict: null },
  { key: "quiz-easy", label: "fetch_page", detail: "nasa.gov/x", tone: "info", verdict: null },
  {
    key: "learn-hard",
    label: "search_wikipedia",
    detail: '"magnetar"',
    tone: "info",
    verdict: null,
  },
  { key: "quiz-easy", label: "Publish gate", detail: "passed", tone: "ok", verdict: null },
];

function render(open?: boolean): string {
  return renderToStaticMarkup(
    <AgentLog
      topic="Magnetars"
      lines={LINES}
      outcome={{ kind: "done", message: "Made 2 of 2." }}
      {...(open === undefined ? {} : { open })}
    />,
  );
}

describe("the agent log", () => {
  it("tags every item's line, even when the items' lines interleave", () => {
    const html = render();

    expect(html.match(/EASY Q</g)).toHaveLength(2);
    expect(html.match(/HARD EXPL</g)).toHaveLength(1);
    // Screen readers hear the full name instead of the tag.
    expect(html).toContain("EASY question:");
    // No headings between items any more: one line per step.
    expect(html.match(/<li/g)).toHaveLength(LINES.length + 1);
  });

  it("shows its lines by default and hides them when closed, keeping the outcome", () => {
    const hiddenList = /<ol[^>]* hidden=""/;
    expect(render()).not.toMatch(hiddenList);
    expect(render(true)).not.toMatch(hiddenList);

    const closed = render(false);
    expect(closed).toMatch(hiddenList);
    expect(closed).toContain("Made 2 of 2.");
  });
});
