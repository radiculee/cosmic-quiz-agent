/**
 * The score of a web search's questions, shown after the last one. Only questions that were
 * answered count: one left out, or never reached, is neither correct nor incorrect. Pure
 * functions, so the rules are tested without a browser.
 */
import type { Slot } from "./search";

export interface WebScore {
  answered: number;
  correct: number;
  incorrect: number;
}

/** `answered` holds the ids of the questions answered, `right` those of them answered correctly. */
export function webScore(answered: ReadonlySet<number>, right: ReadonlySet<number>): WebScore {
  const correct = [...answered].filter((id) => right.has(id)).length;
  return { answered: answered.size, correct, incorrect: answered.size - correct };
}

/** "2 of 3". */
export function scoreText({ correct, answered }: WebScore): string {
  return `${correct} of ${answered}`;
}

/**
 * Whether the results card is due: at least one question was answered and none is still to
 * answer (one left out does not count; one still on its way does). A search that made no
 * question, or whose questions were never answered, keeps the page's usual flow.
 */
export function resultsDue(questions: readonly Slot[], answered: ReadonlySet<number>): boolean {
  const open = questions.filter((slot) => slot.state.kind !== "missed");
  return (
    open.length > 0 &&
    open.every((slot) => slot.state.kind === "ready" && answered.has(slot.state.item.id))
  );
}
