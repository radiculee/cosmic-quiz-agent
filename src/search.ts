/**
 * A live search as the web page holds it (agent/ondemand.py streams it): one slot per planned
 * item, the explanation first and then the questions, each made live or loaded from the bank.
 * Pure functions over plain data, so the page's rules are tested without a browser.
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

export function explanationSlot(search: Search): Slot | undefined {
  return search.slots.find((slot) => slot.mode === "learn");
}

/** The questions in the order they are played: the chosen level first. */
export function questionSlots(search: Search): Slot[] {
  return search.slots.filter((slot) => slot.mode === "quiz");
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
