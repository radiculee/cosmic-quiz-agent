import type { AnchorHTMLAttributes, MouseEvent } from "react";

import { isPlainLeftClick, navigate } from "../router";

type LinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { to: string };

/**
 * A link to a page of this app. It is a real link (so it can be opened in a new tab, copied or
 * read by a screen reader as one), and a plain left click changes the page without a reload.
 */
export function Link({ to, onClick, target, ...rest }: LinkProps) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    if (target || !isPlainLeftClick(event)) {
      return;
    }
    event.preventDefault();
    navigate(to);
  }
  return <a href={to} target={target} onClick={handleClick} {...rest} />;
}
