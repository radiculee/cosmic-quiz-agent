/**
 * What the Quiz setup screen says about the quiz. Plain strings with no React import, because the
 * prerender reads this file too, so the visible page and the prerendered page say the same.
 */
export const QUIZ_HOW_HEADING = "How the quiz works";

export const QUIZ_HOW_STEPS: readonly string[] = [
  "Pick a difficulty: easy, medium or hard.",
  "Pick a run of 10, 30 or 60 questions. A length is offered once the question bank has that many topics at your difficulty.",
  "Every question has four options and is on a different topic, played against the clock.",
  "After each answer you see the explanation and the sources it was checked against.",
];

export const QUIZ_SOURCES_HEADING = "Where the questions come from";

export const QUIZ_SOURCES_TEXT =
  "An AI agent reads pages from sources such as NASA, ESA and Wikipedia and writes each question. A separate check must find a passage in those pages that supports the correct answer before the question is published.";
