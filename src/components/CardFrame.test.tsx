import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { LearnItem, QuizQuestion } from "../types";
import { LearnCard } from "./LearnCard";
import { QuizCard } from "./QuizCard";

const LABEL = "Being checked";
const SPOKEN = "A person has not finished checking this item.";

const LEARN: LearnItem = {
  id: 1,
  mode: "learn",
  difficulty: "easy",
  topic: "Magnetars",
  explanation: "A magnetar is a neutron star with a very strong magnetic field.",
  sources: [],
  source_check: { options: [], sentences: 0, sentences_supported: 0 },
  status: "published",
  doubts: [],
};

const QUIZ: QuizQuestion = {
  id: 2,
  mode: "quiz",
  difficulty: "easy",
  topic: "Magnetars",
  question: "What is a magnetar?",
  options: ["A", "B", "C", "D"],
  status: "published",
};

function learn(item: LearnItem): string {
  return renderToStaticMarkup(<LearnCard item={item} />);
}

function quiz(question: QuizQuestion): string {
  return renderToStaticMarkup(<QuizCard question={question} onAnswered={() => null} />);
}

describe("the Being checked label", () => {
  it("shows on a Learn card whose item is flagged, with the spoken text", () => {
    const html = learn({ ...LEARN, being_checked: true });

    expect(html).toContain(LABEL);
    expect(html).toContain(SPOKEN);
  });

  it("shows on a quiz card whose item is flagged, ahead of the question", () => {
    const html = quiz({ ...QUIZ, being_checked: true });

    expect(html).toContain(LABEL);
    expect(html).toContain(SPOKEN);
    expect(html.indexOf(LABEL)).toBeLessThan(html.indexOf("What is a magnetar?"));
  });

  it("does not show without the field, or with it false", () => {
    for (const html of [
      learn(LEARN),
      learn({ ...LEARN, being_checked: false }),
      quiz(QUIZ),
      quiz({ ...QUIZ, being_checked: false }),
    ]) {
      expect(html).not.toContain(LABEL);
      expect(html).not.toContain(SPOKEN);
    }
  });

  it("does not depend on hover: no title attribute carries the meaning", () => {
    expect(learn({ ...LEARN, being_checked: true })).not.toContain("title=");
  });
});
