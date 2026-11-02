/**
 * What a live search's progress panel shows. One bar for each level of question (Easy, Medium,
 * Hard) and one line for the explanations, all from the stream's real events: a bar fills as its
 * run reports the stage it has reached, and never on a timer. Pure functions over slots, so they
 * are tested without a browser.
 */
import type { Slot } from "./search";
import { STAGES } from "./types";

/** How many of the four stages are finished: the run is working on the one after them. */
export function stagesDone(slot: Slot): number {
  switch (slot.state.kind) {
    case "ready":
      return STAGES.length;
    case "researching":
      return slot.state.progress ? STAGES.indexOf(slot.state.progress.stage) : 0;
    default:
      return 0;
  }
}

export type BarState = "waiting" | "researching" | "ready" | "left out";

/** The one word on a row. */
export const BAR_WORDS: Record<BarState, string> = {
  waiting: "Waiting",
  researching: "Researching",
  ready: "Ready",
  "left out": "Left out",
};

/** A bank item is ready, even while it loads: it is free and has no run to wait for. */
export function barState(slot: Slot): BarState {
  switch (slot.state.kind) {
    case "missed":
      return "left out";
    case "ready":
    case "loading":
      return "ready";
    case "researching":
      return "researching";
    case "waiting":
      return "waiting";
  }
}

export interface Bar {
  key: Slot["key"];
  /** "Easy", "Medium" or "Hard". */
  level: string;
  state: BarState;
  word: string;
  /** Stages finished, 0 to 4: how far the bar is filled. */
  done: number;
  /** For a screen reader, where a running item is ("step 2 of 4"); null before its first report. */
  step: string | null;
}

function readyCount(slots: readonly Slot[]): number {
  return slots.filter((slot) => barState(slot) === "ready").length;
}

function capitalised(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function bar(slot: Slot): Bar {
  const state = barState(slot);
  const reported = slot.state.kind === "researching" && slot.state.progress !== undefined;
  return {
    key: slot.key,
    level: capitalised(slot.difficulty),
    state,
    word: BAR_WORDS[state],
    done: slot.state.kind === "loading" ? STAGES.length : stagesDone(slot),
    step: reported ? `step ${stagesDone(slot) + 1} of ${STAGES.length}` : null,
  };
}

/** The bars: only the question at each level, easiest first. */
export function questionBars(slots: readonly Slot[]): Bar[] {
  return slots.filter((slot) => slot.mode === "quiz").map(bar);
}

/** "Explanations: 1 of 3 ready", or null if this search has no explanation. */
export function explanationLine(slots: readonly Slot[]): string | null {
  const explanations = slots.filter((slot) => slot.mode === "learn");
  if (explanations.length === 0) {
    return null;
  }
  return `Explanations: ${readyCount(explanations)} of ${explanations.length} ready`;
}

/** Whether any item is still on its way. */
export function stillWorking(slots: readonly Slot[]): boolean {
  return slots.some(
    (slot) =>
      slot.state.kind === "waiting" ||
      slot.state.kind === "researching" ||
      slot.state.kind === "loading",
  );
}

/** The panel's one line once every item has ended, when the page has no outcome text for it. */
export function finishedLine(slots: readonly Slot[]): string {
  const questions = slots.filter((slot) => slot.mode === "quiz");
  const explanations = slots.filter((slot) => slot.mode === "learn");
  const parts = [`${readyCount(questions)} of ${questions.length} questions`];
  if (explanations.length > 0) {
    parts.push(`${readyCount(explanations)} of ${explanations.length} explanations`);
  }
  return `Search finished: ${parts.join(" and ")} ready.`;
}
