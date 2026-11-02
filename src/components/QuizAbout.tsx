import {
  QUIZ_HOW_HEADING,
  QUIZ_HOW_STEPS,
  QUIZ_SOURCES_HEADING,
  QUIZ_SOURCES_TEXT,
} from "../quizAbout";

/** The setup screen's explanation of the quiz, on a solid card. The words live in quizAbout.ts. */
export function QuizAbout() {
  return (
    <section
      aria-label="About the quiz"
      className="pixel-border mt-10 w-full max-w-xl rounded-sm bg-surface px-5 py-6 sm:px-8"
    >
      <h2 className="font-heading text-xl font-bold text-ink">{QUIZ_HOW_HEADING}</h2>
      <ul className="mt-3 space-y-2">
        {QUIZ_HOW_STEPS.map((step) => (
          <li key={step} className="pixel-bullet text-sm leading-relaxed text-ink/90">
            {step}
          </li>
        ))}
      </ul>
      <h2 className="mt-6 font-heading text-xl font-bold text-ink">{QUIZ_SOURCES_HEADING}</h2>
      <p className="mt-3 text-sm leading-relaxed text-ink/90">{QUIZ_SOURCES_TEXT}</p>
    </section>
  );
}
