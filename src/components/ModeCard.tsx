import { Link } from "./Link";

/**
 * One of the three ways in on the home page, compact enough to sit in the scene's empty sky: a
 * pixel label and a short status over the mode's title. Solid, like every card on a scene.
 */
export function ModeCard({
  to,
  label,
  title,
  status,
  accent = false,
}: {
  to: string;
  label: string;
  title: string;
  /** "4 of 37 read", "Best streak 7", "2 of 2 left today"; nothing while it is unknown. */
  status: string | null;
  /** Show the status in teal (the live searches left today). */
  accent?: boolean;
}) {
  return (
    <Link
      to={to}
      className="group pixel-border block rounded-sm bg-surface px-4 py-3 transition-colors hover:[--pixel-dash:var(--color-teal)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal"
    >
      <span className="flex items-center justify-between gap-3">
        <span className="pixel-bullet font-pixel text-[9px] uppercase text-slate">{label}</span>
        {status && (
          <span className={`font-pixel text-[8px] uppercase ${accent ? "text-teal" : "text-slate"}`}>
            {status}
          </span>
        )}
      </span>
      <span className="mt-2 flex items-center justify-between gap-3">
        <span className="font-heading text-xl font-bold text-ink">{title}</span>
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
