import { useEffect, useRef, useState } from "react";

import {
  currentStage,
  STAGE_LABELS,
  stagesDone,
  statusLine,
  stillWorking,
  timeLeft,
  timeLeftText,
} from "../progress";
import { itemLabel, type Slot } from "../search";
import { STAGES } from "../types";

/** Seconds since the search began, ticking once a second while any item is still on its way. */
function useElapsed(running: boolean): number {
  const started = useRef(performance.now());
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(
      () => setElapsed((performance.now() - started.current) / 1000),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [running]);
  return elapsed;
}

function Steps({ slot }: { slot: Slot }) {
  const done = stagesDone(slot);
  const current = currentStage(slot);
  const missed = slot.state.kind === "missed";
  return (
    <ol className="mt-2 grid grid-cols-4 gap-1.5" aria-hidden="true">
      {STAGES.map((stage, index) => {
        const finished = index < done;
        const active = stage === current;
        return (
          <li key={stage}>
            <div
              className={`h-1.5 rounded-sm ${
                missed
                  ? "bg-rust/50"
                  : finished
                    ? "bg-teal"
                    : active
                      ? "bg-teal/50 motion-safe:animate-pulse"
                      : "bg-white/10"
              }`}
            />
            <span
              className={`mt-1 block font-pixel text-[8px] uppercase ${
                finished || active ? "text-ink" : "text-slate/70"
              }`}
            >
              {STAGE_LABELS[stage]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function Row({ slot, elapsed }: { slot: Slot; elapsed: number }) {
  const stage = currentStage(slot);
  const left = timeLeftText(timeLeft(slot, elapsed));
  const status = statusLine(slot);
  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex items-baseline justify-between gap-3">
        <p className="font-pixel text-[9px] uppercase text-teal">{itemLabel(slot.key)}</p>
        {left && <p className="text-xs tabular-nums text-slate">{left}</p>}
      </div>
      <Steps slot={slot} />
      <p className="mt-2 text-sm text-ink/90">
        {status}
        {stage && <span className="sr-only"> (step {STAGES.indexOf(stage) + 1} of 4)</span>}
      </p>
    </li>
  );
}

/**
 * One row for each item of a live search, questions first and then the explanations: the four
 * stages of its work (search, read, write, verify), a status line naming what it is doing, and
 * about how long it has left. The stage and the status line come from the stream's real
 * progress events, so a row moves only when its run does. The agent's log sits behind "Show
 * details": the page owns the toggle and gives the log `detailsOpen`.
 */
export function SearchProgress({
  slots,
  detailsOpen,
  onToggleDetails,
}: {
  slots: readonly Slot[];
  detailsOpen: boolean;
  onToggleDetails: () => void;
}) {
  const elapsed = useElapsed(stillWorking(slots));
  return (
    <section
      aria-label="Search progress"
      className="pixel-border mb-4 w-full rounded-sm bg-surface px-4 py-5 sm:px-6"
    >
      <ol className="divide-y divide-white/5">
        {slots.map((slot) => (
          <Row key={slot.key} slot={slot} elapsed={elapsed} />
        ))}
      </ol>
      <button
        type="button"
        aria-expanded={detailsOpen}
        onClick={onToggleDetails}
        className="mt-4 rounded-sm border border-white/15 px-3 py-2.5 font-pixel text-[9px] uppercase text-ink hover:border-white/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
      >
        {detailsOpen ? "Hide details" : "Show details"}
      </button>
    </section>
  );
}
