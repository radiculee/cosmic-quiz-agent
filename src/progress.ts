/**
 * What a live search's progress rows show for each item. Everything here comes from the stream's
 * real events: the stage a run has reached, its status line and, for the time left, the median
 * of recent runs at that mode and level (`estimate_seconds`). Nothing is timer-driven except the
 * clock the time left counts down on. Pure functions over a slot, so they are tested without a
 * browser.
 */
import type { Slot } from "./search";
import { STAGES, type Stage } from "./types";

export const STAGE_LABELS: Record<Stage, string> = {
  search: "Search",
  read: "Read",
  write: "Write",
  verify: "Verify",
};

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

/** The stage a run is working on, if it is running and has reported one. */
export function currentStage(slot: Slot): Stage | null {
  return slot.state.kind === "researching" && slot.state.progress
    ? slot.state.progress.stage
    : null;
}

/** The row's status line: the real work the run reported, or where the item stands. */
export function statusLine(slot: Slot): string {
  switch (slot.state.kind) {
    case "waiting":
      return "Starting";
    case "researching":
      return slot.state.progress?.status ?? "Starting";
    case "loading":
      return "Loading from the bank";
    case "ready":
      return slot.source === "bank" ? "Ready, from the bank" : "Ready";
    case "missed":
      return "Left out";
  }
}

export type TimeLeft = { kind: "left"; seconds: number } | { kind: "over" } | null;

/**
 * How long a live run usually has left. `elapsed` is seconds since the search began. The run's
 * own clock starts at its first progress; before that it has its whole estimate. Null for an item
 * that is not running or has no estimate (a bank item, or a level with too few recent runs).
 */
export function timeLeft(slot: Slot, elapsed: number): TimeLeft {
  const estimate = slot.estimate_seconds;
  if (slot.source !== "live" || estimate === null || estimate === undefined) {
    return null;
  }
  if (slot.state.kind === "waiting") {
    return { kind: "left", seconds: Math.ceil(estimate) };
  }
  if (slot.state.kind !== "researching") {
    return null;
  }
  const startedAt = slot.state.progress?.startedAt ?? elapsed;
  const left = estimate - (elapsed - startedAt);
  return left > 0 ? { kind: "left", seconds: Math.ceil(left) } : { kind: "over" };
}

export function timeLeftText(left: TimeLeft): string {
  if (left === null) {
    return "";
  }
  return left.kind === "over" ? "Taking longer than usual" : `About ${left.seconds} s left`;
}

/** Whether any run is still going, so the clock needs to tick. */
export function stillWorking(slots: readonly Slot[]): boolean {
  return slots.some(
    (slot) =>
      slot.state.kind === "waiting" ||
      slot.state.kind === "researching" ||
      slot.state.kind === "loading",
  );
}
