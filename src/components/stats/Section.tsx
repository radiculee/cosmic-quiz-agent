import { type ReactNode, useState } from "react";

/**
 * One group of figures behind a click (decided 2026-10-08: each tab opens on its four key
 * figures, and the rest waits in closed rows). The row names the group with a one-line hint of
 * what is inside; its figures are drawn only once it is opened, and every row starts closed.
 * Rows stack in a `Groups` list.
 */
export function Group({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <details
      onToggle={(event) => setOpen(event.currentTarget.open)}
      className="group border-b border-white/10"
    >
      <summary className="flex cursor-pointer list-none items-baseline gap-3 py-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal [&::-webkit-details-marker]:hidden">
        <span
          aria-hidden="true"
          className="inline-block font-pixel text-[8px] text-teal transition-transform group-open:rotate-90 motion-reduce:transition-none"
        >
          &gt;
        </span>
        <span className="flex min-w-0 flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-4">
          <h3 className="font-heading text-lg font-bold">{title}</h3>
          {hint !== undefined && <span className="text-sm text-slate">{hint}</span>}
        </span>
      </summary>
      {open && <div className="space-y-9 pb-10 pt-3">{children}</div>}
    </details>
  );
}

/** The closed rows of a tab, under its four key figures. */
export function Groups({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={label} className="border-t border-white/10">
      {children}
    </div>
  );
}

/** A small heading inside a group, in the pixel face. */
export function Label({ children }: { children: ReactNode }) {
  return (
    <h4 className="font-pixel text-[8px] uppercase leading-relaxed text-slate">{children}</h4>
  );
}
