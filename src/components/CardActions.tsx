import { ReportButton } from "./ReportButton";

/** Under every card: report the item, or move on to the next one. Items in review are not
 * public yet, so there is nothing to report. */
export function CardActions({
  itemId,
  nextLabel,
  onNext,
  canReport = true,
}: {
  itemId: number;
  nextLabel: string;
  onNext: () => void;
  canReport?: boolean;
}) {
  return (
    <div className="mt-10 flex flex-col-reverse items-start gap-6 border-t border-white/5 pt-6 sm:flex-row sm:items-center sm:justify-between">
      {canReport ? <ReportButton key={itemId} itemId={itemId} /> : <span />}
      <button
        type="button"
        onClick={onNext}
        className="rounded-lg bg-teal px-6 py-3.5 font-pixel text-[10px] uppercase text-void hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
      >
        {nextLabel}
      </button>
    </div>
  );
}
