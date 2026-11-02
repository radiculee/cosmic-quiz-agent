import type { ReactNode } from "react";

import { explanationLine, finishedLine, questionBars, stillWorking, type Bar } from "../progress";
import type { Search } from "../search";
import { STAGES } from "../types";

const BUTTON =
  "rounded-sm border border-white/15 px-3 py-2.5 font-pixel text-[9px] uppercase text-ink hover:border-white/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal";
const DETAILS_ID = "search-details";

function Row({ bar }: { bar: Bar }) {
  const fill = bar.state === "left out" ? 0 : (bar.done / STAGES.length) * 100;
  return (
    <li className="grid grid-cols-[4.5rem_1fr_auto] items-center gap-3 py-2 sm:grid-cols-[5.5rem_1fr_7rem]">
      <span className="font-pixel text-[9px] uppercase text-teal">{bar.level}</span>
      <div
        aria-hidden="true"
        className={`h-2 overflow-hidden rounded-sm ${
          bar.state === "left out" ? "bg-rust/40" : "bg-white/10"
        }`}
      >
        <div
          className={`h-full bg-teal motion-safe:transition-[width] motion-safe:duration-500 ${
            bar.state === "researching" ? "motion-safe:animate-pulse" : ""
          }`}
          style={{ width: `${fill}%` }}
        />
      </div>
      <span className="text-right text-sm text-ink/90">
        {bar.word}
        {bar.step && <span className="sr-only"> ({bar.step})</span>}
      </span>
    </li>
  );
}

/**
 * The progress of a live search: a bar for the question at each level (Easy, Medium, Hard), each
 * filled by the real stage its run has reached, with one word beside it, and a line counting the
 * explanations ready. When every item has ended it shrinks to one line, the outcome text. The
 * agent's log and anything else for the curious go in `details`, behind "Show details": the page
 * owns the toggle.
 */
export function SearchProgress({
  search,
  message,
  detailsOpen,
  onToggleDetails,
  details,
}: {
  search: Search;
  /** The search's outcome text, shown as the one line once everything has ended. */
  message: string | null;
  detailsOpen: boolean;
  onToggleDetails: () => void;
  details: ReactNode;
}) {
  const finished = !stillWorking(search.slots);
  const explanations = explanationLine(search.slots);
  return (
    <section
      aria-label="Search progress"
      className="pixel-border w-full rounded-sm bg-surface px-4 py-4 sm:px-6"
    >
      {finished ? (
        <p className="text-sm text-ink/90">{message ?? finishedLine(search.slots)}</p>
      ) : (
        <>
          <ul className="divide-y divide-white/5">
            {questionBars(search.slots).map((bar) => (
              <Row key={bar.key} bar={bar} />
            ))}
          </ul>
          {explanations && <p className="mt-2 text-sm text-slate">{explanations}</p>}
        </>
      )}
      <button
        type="button"
        aria-expanded={detailsOpen}
        aria-controls={DETAILS_ID}
        onClick={onToggleDetails}
        className={`${BUTTON} mt-4`}
      >
        {detailsOpen ? "Hide details" : "Show details"}
      </button>
      <div id={DETAILS_ID} hidden={!detailsOpen} className="mt-4">
        {details}
      </div>
    </section>
  );
}
