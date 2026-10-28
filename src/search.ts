/**
 * A live search as the web page holds it (agent/ondemand.py streams it): one slot per planned
 * item, the questions first and the explanations last, each level easiest first, each made live
 * or loaded from the bank (every level since 2026-10-28). The explanations open only once every
 * question has been answered (decided 2026-10-10), so they can never give an answer away. Pure
 * functions over plain data, so the page's rules are tested without a browser.
 */
import type { Item, ItemKey, PlannedItem, RunStats } from "./types";

export type SlotState =
  /** Made live; its run has not started yet. */
  | { kind: "waiting" }
  /** Made live; its run is going. */
  | { kind: "researching" }
  /** Already in the bank; being loaded, free. */
  | { kind: "loading" }
  | { kind: "ready"; item: Item; revealToken?: string | undefined }
  /** Discarded by the checks, failed, not started, or not loaded. */
  | { kind: "missed"; message: string };

export interface Slot extends PlannedItem {
  state: SlotState;
}

export interface Search {
  /** A new id per search, so the page's panels start afresh. */
  id: number;
  /** The bank's spelling when it has the topic. */
  topic: string;
  slots: Slot[];
  /** What each finished run measured, in the order the runs ended (the analytics panel). */
  runs: SearchRun[];
  /** The stream has closed: nothing still waiting will come. */
  ended: boolean;
}

export interface SearchRun {
  key: ItemKey;
  stats: RunStats;
}

/** "EASY question" or "MEDIUM explanation", for headings and buttons. */
export function itemLabel(key: ItemKey): string {
  const [mode, difficulty] = key.split("-");
  return `${(difficulty ?? "").toUpperCase()} ${mode === "learn" ? "explanation" : "question"}`;
}

export function fromPlan(id: number, topic: string, items: readonly PlannedItem[]): Search {
  return {
    id,
    topic,
    slots: items.map((item) => ({
      ...item,
      state: item.source === "live" ? { kind: "waiting" } : { kind: "loading" },
    })),
    runs: [],
    ended: false,
  };
}

/** A run's figures arrived. Each item has one run, so a repeat replaces the earlier figures. */
export function measured(search: Search, key: ItemKey, stats: RunStats): Search {
  return { ...search, runs: [...search.runs.filter((run) => run.key !== key), { key, stats }] };
}

function update(search: Search, key: ItemKey, next: (slot: Slot) => SlotState): Search {
  return {
    ...search,
    slots: search.slots.map((slot) => (slot.key === key ? { ...slot, state: next(slot) } : slot)),
  };
}

/** A log line about the item: its run has started. */
export function started(search: Search, key: ItemKey): Search {
  return update(search, key, (slot) =>
    slot.state.kind === "waiting" ? { kind: "researching" } : slot.state,
  );
}

/** The item arrived: a live result, or a bank item loaded. */
export function resolved(search: Search, key: ItemKey, item: Item, revealToken?: string): Search {
  return update(search, key, () => ({ kind: "ready", item, revealToken }));
}

export function missed(search: Search, key: ItemKey, message: string): Search {
  return update(search, key, (slot) =>
    slot.state.kind === "ready" ? slot.state : { kind: "missed", message },
  );
}

/** The stream closed. Live items still waiting or researching will not come: `message` says
 * why. Items loading from the bank are not affected. */
export function ended(search: Search, message: string): Search {
  return {
    ...search,
    ended: true,
    slots: search.slots.map((slot) =>
      slot.state.kind === "waiting" || slot.state.kind === "researching"
        ? { ...slot, state: { kind: "missed", message } }
        : slot,
    ),
  };
}

/** The explanations, easiest first. */
export function explanationSlots(search: Search): Slot[] {
  return search.slots.filter((slot) => slot.mode === "learn");
}

/** The questions in the order they are played, easiest first. */
export function questionSlots(search: Search): Slot[] {
  return search.slots.filter((slot) => slot.mode === "quiz");
}

/** The first explanation that is ready, easiest first: the one the reader starts on. */
export function firstReady(slots: readonly Slot[]): Slot | undefined {
  return slots.find((slot) => slot.state.kind === "ready");
}

/** Where the explanations stand for the player. */
export type ExplanationLock =
  /** Questions still to answer, ready or still coming, before they open. */
  | { kind: "locked"; left: number }
  /** Every question is done; no explanation is ready yet, but one is being made or loaded. */
  | { kind: "coming" }
  /** At least one explanation is ready, and every question is answered or left out. */
  | { kind: "open" }
  /** Every explanation was left out: discarded, failed or not started. */
  | { kind: "missed"; message: string };

/**
 * The explanations open once every question the search shows has been answered or left out,
 * and at least one of them is ready; the others open as they arrive. A search that made no
 * question opens them as soon as one is ready. `answered` holds the ids of the questions
 * answered on the page. Undefined when the search has no explanation in its plan.
 */
export function explanationLock(
  search: Search,
  answered: ReadonlySet<number>,
): ExplanationLock | undefined {
  const slots = explanationSlots(search);
  const [first] = slots;
  if (!first) {
    return undefined;
  }
  if (slots.every((slot) => slot.state.kind === "missed")) {
    return { kind: "missed", message: first.state.kind === "missed" ? first.state.message : "" };
  }
  const left = questionSlots(search).filter(
    (question) =>
      question.state.kind !== "missed" &&
      !(question.state.kind === "ready" && answered.has(question.state.item.id)),
  ).length;
  if (left > 0) {
    return { kind: "locked", left };
  }
  return firstReady(slots) ? { kind: "open" } : { kind: "coming" };
}

/** The first question at or after `from` that is not left out, or null if there is none. */
export function nextOpen(slots: readonly Slot[], from: number): number | null {
  for (let index = Math.max(0, from); index < slots.length; index += 1) {
    if (slots[index]?.state.kind !== "missed") {
      return index;
    }
  }
  return null;
}

/** Whether the search has made at least one live item (Web researcher counts such searches). */
export function madeAnything(search: Search): boolean {
  return search.slots.some((slot) => slot.source === "live" && slot.state.kind === "ready");
}

export interface SearchSummary {
  /** Live items made: published or in review. */
  made: number;
  review: number;
  /** Live items the search planned. */
  live: number;
}

export function summarize(search: Search): SearchSummary {
  const live = search.slots.filter((slot) => slot.source === "live");
  const made = live.filter((slot) => slot.state.kind === "ready");
  return {
    made: made.length,
    review: made.filter((slot) => slot.state.kind === "ready" && slot.state.item.status === "review")
      .length,
    live: live.length,
  };
}

/** The line under the agent log once the search has ended. */
export function summaryLine({ made, review, live }: SearchSummary): string {
  if (made === 0) {
    return "The agent could not back any of it with its sources this time. Topics in the bank are still free to play.";
  }
  const parts = [`Made ${made} of ${live}, saved to the bank.`];
  if (review > 0) {
    parts.push(
      `${review === 1 ? "One is" : `${review} are`} marked not fully verified and shown only to you until reviewed.`,
    );
  }
  return parts.join(" ");
}
