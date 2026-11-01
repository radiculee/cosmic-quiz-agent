import { useCallback, useState } from "react";

import { browserStorage } from "./profile";

/** The panels under a card's button row. Each remembers whether the player left it open. */
export type PanelName = "explanation" | "sources";

export const PANEL_KEY_PREFIX = "curiosity.panel.";

const OPEN = "open";
const CLOSED = "closed";

/** Whether the player last left this panel open. A panel nobody has touched starts closed. */
export function loadPanel(storage: Pick<Storage, "getItem"> | undefined, name: PanelName): boolean {
  try {
    return storage?.getItem(PANEL_KEY_PREFIX + name) === OPEN;
  } catch {
    return false;
  }
}

/** Remember the panel's state. A browser that refuses to store it is not an error. */
export function savePanel(
  storage: Pick<Storage, "setItem"> | undefined,
  name: PanelName,
  open: boolean,
) {
  try {
    storage?.setItem(PANEL_KEY_PREFIX + name, open ? OPEN : CLOSED);
  } catch {
    // Private windows and full storage throw; the panel still works for this visit.
  }
}

/** A panel's open state, starting from what the player chose last time. */
export function usePanel(name: PanelName): [boolean, () => void] {
  const [open, setOpen] = useState(() => loadPanel(browserStorage(), name));
  const toggle = useCallback(() => {
    savePanel(browserStorage(), name, !open);
    setOpen(!open);
  }, [name, open]);
  return [open, toggle];
}
