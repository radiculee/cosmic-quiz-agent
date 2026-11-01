import { createContext, type ReactNode, useContext } from "react";
import { createPortal } from "react-dom";

/** The second row of the site header (SiteHeader.tsx), once it has mounted. */
export const HeaderSlotContext = createContext<HTMLElement | null>(null);

/**
 * A page's settings, drawn in the sticky header instead of in the page. The state stays in the
 * page that renders this, so a control here behaves exactly as it did in the page's own bar.
 * Nothing is drawn until the header's row exists, and when no page renders this the row is empty
 * and hidden.
 */
export function HeaderSettings({ children }: { children: ReactNode }) {
  const slot = useContext(HeaderSlotContext);
  return slot ? createPortal(children, slot) : null;
}
