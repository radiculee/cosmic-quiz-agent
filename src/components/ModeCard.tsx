import type { ReactNode } from "react";

import { Link } from "./Link";

/** A large card on the home page that opens one of the modes. */
export function ModeCard({
  to,
  label,
  title,
  text,
  footer,
}: {
  to: string;
  label: string;
  title: string;
  text: string;
  footer: ReactNode;
}) {
  return (
    <Link
      to={to}
      className="group pixel-border block rounded-sm bg-surface/70 px-6 py-7 transition-colors hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal"
    >
      <span className="pixel-bullet block font-pixel text-[9px] uppercase text-slate">{label}</span>
      <h2 className="mt-4 font-heading text-3xl font-bold">{title}</h2>
      <span className="mt-3 block text-sm leading-relaxed text-ink/80">{text}</span>
      <span className="mt-6 flex items-center justify-between gap-4 text-xs text-slate">
        <span>{footer}</span>
        <span
          aria-hidden="true"
          className="font-pixel text-[10px] text-teal transition-transform group-hover:translate-x-1 motion-reduce:transition-none"
        >
          &gt;
        </span>
      </span>
    </Link>
  );
}
