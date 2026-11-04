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

  it("keeps the facts: the sources step and the scoring as the last step", () => {
    expect(QUIZ_HOW_STEPS).toHaveLength(7);
    expect(QUIZ_HOW_STEPS[5]).toBe(
      "After each answer you see the explanation and the sources it was checked against.",
    );
    expect(QUIZ_HOW_STEPS[6]).toBe(
      "EASY 100, MEDIUM 200, HARD 300 points a correct answer. x1.5 from 3 in a row, x2 from 5, and +25% for answering within 15 seconds.",
    );
    expect(QUIZ_HOW_STEPS.join(" ")).toContain("have not played come first");
    expect(QUIZ_HOW_STEPS.join(" ")).toContain("only while a question waits");
  });
});
