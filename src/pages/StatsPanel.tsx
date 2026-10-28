import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";

import { AgentTab } from "../components/stats/AgentTab";
import { SearchTab } from "../components/stats/SearchTab";
import type { Search } from "../search";
import { SECONDARY_BUTTON } from "./common";

type Tab = "search" | "agent";

const TABS: { id: Tab; label: string }[] = [
  { id: "search", label: "This search" },
  { id: "agent", label: "The agent" },
];

/**
 * Mission Control (docs/PLAN.md Session 9): a full-screen panel over the web page at
 * /explore/stats, with two tabs. "This search" shows what the agent did for the search just made;
 * "The agent" shows everything it has measured, with filters. It is a modal <dialog>, so the page
 * behind is inert and keeps its search going; Esc, Close and Back all close it, and focus goes
 * back where it was.
 */
export function StatsPanel({
  open,
  onClose,
  search,
  running,
}: {
  open: boolean;
  /** Leave /explore/stats; the panel closes when the address does. */
  onClose: () => void;
  search: Search | null;
  running: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const [tab, setTab] = useState<Tab>("agent");
  const titleId = useId();
  const panelId = useId();
  const hasSearch = search !== null && (running || search.runs.length > 0);
  // Whether this panel has asked to leave /explore/stats and the address has not changed yet.
  const leaving = useRef(false);

  /** Leave /explore/stats once per close. Going Back takes effect a moment later, so `open` is
   * still true in between, and Esc can bring both a cancel and a close event: when the browser
   * does not let the cancel be prevented, it closes the dialog straight after. */
  function requestClose() {
    if (!leaving.current) {
      leaving.current = true;
      onClose();
    }
  }

  useEffect(() => {
    leaving.current = false;
    const element = dialog.current;
    if (!element) {
      return;
    }
    if (open && !element.open) {
      const active = document.activeElement;
      returnFocus.current = active instanceof HTMLElement ? active : null;
      // Open on the search just made, if there is one; otherwise on the agent as a whole.
      setTab(hasSearch ? "search" : "agent");
      element.showModal();
      element.scrollTop = 0;
    } else if (!open) {
      // The browser may have closed the dialog already (see onClose below).
      if (element.open) {
        element.close();
      }
      const back = returnFocus.current;
      returnFocus.current = null;
      if (back?.isConnected) {
        back.focus({ preventScroll: true });
      }
    }
    // Only opening and closing run this; the tab is chosen from the search as the panel opens.
  }, [open]);

  function moveTab(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (step === 0) {
      return;
    }
    event.preventDefault();
    const next = (index + step + TABS.length) % TABS.length;
    const target = TABS[next];
    if (target) {
      setTab(target.id);
      tabs.current[next]?.focus();
    }
  }

  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      // Esc goes back through the address, like Close and Back, so all three agree.
      onCancel={(event) => {
        event.preventDefault();
        requestClose();
      }}
      // A browser can also close a modal dialog without a cancel event (its rules for repeated
      // close requests), which would leave the address on /explore/stats with the panel shut. A
      // close the panel did not make goes through the address too; its own comes once `open` is
      // false.
      onClose={() => {
        if (open) {
          requestClose();
        }
      }}
      className="m-0 h-dvh max-h-none w-full max-w-none overscroll-contain bg-void p-0 text-ink backdrop:bg-void"
    >
      {open && (
        <div className="mx-auto w-full max-w-3xl px-4 pb-20">
          <div className="flex h-14 items-center justify-between">
            <span className="font-heading text-base font-bold uppercase tracking-tight">
              Cosmic Quiz
            </span>
            <button
              type="button"
              onClick={requestClose}
              className={`${SECONDARY_BUTTON} px-4 py-2.5 text-[9px]`}
            >
              Close
            </button>
          </div>

          <div className="pt-6">
            <h2 id={titleId} className="font-heading text-4xl font-bold uppercase tracking-tight">
              Mission Control
            </h2>
            <p className="mt-3 max-w-xl leading-relaxed text-ink/90">
              Everything the agent measures: what it costs, how long it takes, what it reads and
              how its checks judge it. Only totals leave the database.
            </p>
          </div>

          <div
            role="tablist"
            aria-label="What to show"
            className="mt-8 inline-flex gap-1 rounded-lg border border-white/10 bg-surface p-1"
          >
            {TABS.map((entry, index) => {
              const selected = entry.id === tab;
              return (
                <button
                  key={entry.id}
                  ref={(element) => {
                    tabs.current[index] = element;
                  }}
                  type="button"
                  role="tab"
                  id={`${panelId}-${entry.id}`}
                  aria-selected={selected}
                  aria-controls={`${panelId}-${entry.id}-panel`}
                  tabIndex={selected ? 0 : -1}
                  onClick={() => setTab(entry.id)}
                  onKeyDown={(event) => moveTab(event, index)}
                  className={`rounded-md px-5 py-3 font-pixel text-[10px] uppercase leading-none transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal ${
                    selected ? "bg-teal text-void" : "text-slate hover:text-ink"
                  }`}
                >
                  {entry.label}
                </button>
              );
            })}
          </div>

          {/* Both tabs stay mounted, so the agent tab keeps its filters while the other shows. */}
          <div
            role="tabpanel"
            id={`${panelId}-search-panel`}
            aria-labelledby={`${panelId}-search`}
            hidden={tab !== "search"}
            className="mt-10"
          >
            <SearchTab search={search} running={running} />
          </div>
          <div
            role="tabpanel"
            id={`${panelId}-agent-panel`}
            aria-labelledby={`${panelId}-agent`}
            hidden={tab !== "agent"}
            className="mt-10"
          >
            <AgentTab active={open && tab === "agent"} />
          </div>
        </div>
      )}
    </dialog>
  );
}
