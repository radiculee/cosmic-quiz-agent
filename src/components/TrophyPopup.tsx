import { useEffect, useId, useRef } from "react";

import { type Award, tierIndex, trophy } from "../trophies";
import { TIER_TEXT, TrophyIcon } from "./TrophyIcon";

const NUMBER = new Intl.NumberFormat("en-IE");

function AwardRow({ award }: { award: Award }) {
  if (award.kind === "rank") {
    return (
      <li className="flex items-center gap-4">
        <TrophyIcon glyph="rank-up" tone="rank" size="lg" />
        <span>
          <span className="block font-heading text-xl font-bold">Rank up: {award.name}</span>
          <span className="mt-1.5 block font-pixel text-[8px] uppercase text-teal">
            {NUMBER.format(award.points)} points
          </span>
        </span>
      </li>
    );
  }
  const entry = trophy(award.id);
  const goal = entry.goals[tierIndex(award.tier)] ?? 0;
  return (
    <li className="flex items-center gap-4">
      <TrophyIcon glyph={award.id} tone={award.tier} size="lg" />
      <span>
        <span className="block font-heading text-xl font-bold">{entry.name}</span>
        <span className={`mt-1.5 block font-pixel text-[8px] uppercase ${TIER_TEXT[award.tier]}`}>
          {award.tier}
        </span>
        <span className="mt-1 block text-sm leading-snug text-slate">{entry.how(goal)}</span>
      </span>
    </li>
  );
}

/**
 * New trophies and rank-ups: a centred card over a dimmed page. It is a modal <dialog>, so the
 * page behind is inert and focus stays in the card; Esc or Continue closes it, and focus goes
 * back where it was. Awards that arrive together share one card; a later batch is the next card.
 * The pop-in is skipped for people who prefer reduced motion.
 */
export function TrophyPopup({
  awards,
  onClose,
}: {
  awards: readonly Award[] | undefined;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    const element = dialog.current;
    if (!element) {
      return;
    }
    if (awards && !element.open) {
      const active = document.activeElement;
      returnFocus.current = active instanceof HTMLElement ? active : null;
      element.showModal();
    } else if (!awards && element.open) {
      element.close();
    }
  }, [awards]);

  // Esc and Continue both end here, through the dialog's own close event.
  function handleClose() {
    const back = returnFocus.current;
    if (back?.isConnected) {
      back.focus({ preventScroll: true });
    }
    onClose();
  }

  const count = awards?.length ?? 0;
  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      onClose={handleClose}
      className="m-auto w-[min(26rem,calc(100%-2rem))] rounded-sm border border-gold/40 bg-surface p-0 text-ink shadow-2xl shadow-black/60 backdrop:bg-void/75"
    >
      {awards && (
        <div className="px-7 py-7 motion-safe:animate-[pop_250ms_ease-out]">
          <h2 id={titleId} className="font-pixel text-[9px] uppercase text-gold">
            {count === 1 ? (awards[0]?.kind === "rank" ? "Rank up" : "New trophy") : `${count} new`}
          </h2>
          <ul className="mt-5 space-y-5">
            {awards.map((award) => (
              <AwardRow
                key={award.kind === "rank" ? `rank-${award.name}` : `${award.id}-${award.tier}`}
                award={award}
              />
            ))}
          </ul>
          <button
            type="button"
            autoFocus
            onClick={() => dialog.current?.close()}
            className="mt-8 w-full rounded-lg bg-teal py-3.5 font-pixel text-[10px] uppercase text-void hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
          >
            Continue
          </button>
        </div>
      )}
    </dialog>
  );
}
