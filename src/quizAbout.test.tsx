import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { QuizAbout } from "./components/QuizAbout";
import { QUIZ_HOW_STEPS, QUIZ_SOURCES_TEXT } from "./quizAbout";

describe("QuizAbout", () => {
  it("shows both headings, every step and the sources text", () => {
    const html = renderToStaticMarkup(<QuizAbout />);
    expect(html).toContain("How the quiz works");
    expect(html).toContain("Where the questions come from");
    expect(html.match(/<li /g)).toHaveLength(QUIZ_HOW_STEPS.length);
    for (const step of QUIZ_HOW_STEPS) {
      expect(html).toContain(step);
    }
    expect(html).toContain(QUIZ_SOURCES_TEXT);
  });

  it("has four steps, the third and fourth as decided", () => {
    expect(QUIZ_HOW_STEPS).toHaveLength(4);
    expect(QUIZ_HOW_STEPS[3]).toBe(
      "After each answer you see the explanation and the sources it was checked against.",
    );
  });
});
