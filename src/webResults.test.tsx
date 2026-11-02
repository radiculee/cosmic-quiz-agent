import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WebResults } from "./components/WebResults";

const score = { answered: 3, correct: 2, incorrect: 1 };
const html = (explanations: Parameters<typeof WebResults>[0]["explanations"]) =>
  renderToStaticMarkup(
    <WebResults score={score} explanations={explanations} onNewTopic={() => {}} />,
  );

describe("WebResults", () => {
  it("shows the score, the two tiles and both buttons", () => {
    const out = html({ label: "Read the explanations", disabled: false, onClick: () => {} });
    expect(out).toContain("2 of 3");
    expect(out).toMatch(/Correct/);
    expect(out).toMatch(/Incorrect/);
    expect(out).toContain("Read the explanations");
    expect(out).toContain("Another new topic");
    expect(out).not.toContain('disabled=""');
  });

  it("disables the explanations button while they are not ready", () => {
    const out = html({ label: "Explanations: researching", disabled: true, onClick: () => {} });
    expect(out).toContain('disabled=""');
  });

  it("offers only a new topic when the search made no explanation", () => {
    const out = html(null);
    expect(out).not.toContain("explanations");
    expect(out).toContain("Another new topic");
  });
});
