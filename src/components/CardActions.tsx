import { type ReactNode, useId } from "react";

import { type PanelName, usePanel } from "../panels";
import { ReportButton } from "./ReportButton";

const TOGGLE =
  "rounded-lg border px-4 py-3.5 font-pixel text-[10px] uppercase text-ink transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal";

/** A button that opens or closes the panel under the row, and remembers which way it was left. */
function PanelToggle({
  name,
  label,
  open,
  onToggle,
  panelId,
}: {
  name: PanelName;
  label: string;
  open: boolean;
  onToggle: () => void;
  panelId: string;
}) {
  return (
    <button
      type="button"
      data-panel={name}
      aria-expanded={open}
      aria-controls={panelId}
      onClick={onToggle}
      className={`${TOGGLE} ${open ? "border-teal/60 bg-white/5" : "border-white/15 hover:border-white/40"}`}
    >
      {label}
    </button>
  );
}

/**
 * Under every card, a row of buttons and what they open. "Read the explanation" and "Sources (n)"
 * each open a panel under the row, both closed until the player opens them and then left as the
 * player last left them. "Next" moves on. A card with no explanation to hide, or without sources,
 * gets only the buttons it needs. Items in review are not public yet, so there is nothing to
 * report. Without `onNext` there is no next button (the web page's explanation, with its
 * questions below); `nextDisabled` shows one that is not ready.
 */
export function CardActions({
  itemId,
  nextLabel,
  onNext,
  nextDisabled = false,
  canReport = true,
  explanation,
  sources,
}: {
  itemId: number;
  nextLabel?: string | undefined;
  onNext?: (() => void) | undefined;
  nextDisabled?: boolean;
  canReport?: boolean;
  /** The explanation, behind "Read the explanation". Leave out when the card shows it already. */
  explanation?: ReactNode;
  /** The sources and the source check, behind "Sources (n)". */
  sources?: { count: number; content: ReactNode } | undefined;
}) {
  const id = useId();
  const [explanationOpen, toggleExplanation] = usePanel("explanation");
  const [sourcesOpen, toggleSources] = usePanel("sources");
  const explanationId = `${id}-explanation`;
  const sourcesId = `${id}-sources`;
  const hasRow = explanation !== undefined || sources !== undefined || (onNext && nextLabel);

  return (
    <div className="mt-8">
      {hasRow && (
        <div className="flex flex-wrap items-center gap-3">
          {explanation !== undefined && (
            <PanelToggle
              name="explanation"
              label="Read the explanation"
              open={explanationOpen}
              onToggle={toggleExplanation}
              panelId={explanationId}
            />
          )}
          {sources && (
            <PanelToggle
              name="sources"
              label={`Sources (${sources.count})`}
              open={sourcesOpen}
              onToggle={toggleSources}
              panelId={sourcesId}
            />
          )}
          {onNext && nextLabel && (
            <button
              type="button"
              onClick={onNext}
              disabled={nextDisabled}
              className="rounded-lg bg-teal px-6 py-3.5 font-pixel text-[10px] uppercase text-void hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:cursor-default disabled:opacity-40 sm:ml-auto"
            >
              {nextLabel}
            </button>
          )}
        </div>
      )}
      {explanation !== undefined && (
        <div id={explanationId} hidden={!explanationOpen}>
          {explanationOpen && explanation}
        </div>
      )}
      {sources && (
        <div id={sourcesId} hidden={!sourcesOpen}>
          {sourcesOpen && sources.content}
        </div>
      )}
      {canReport && (
        <div className="mt-8 border-t border-white/5 pt-6">
          <ReportButton key={itemId} itemId={itemId} />
        </div>
      )}
    </div>
  );
}
