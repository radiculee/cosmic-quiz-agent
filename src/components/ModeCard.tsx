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
  main = false,
}: {
  to: string;
  label: string;
  title: string;
  /** "4 of 37 read", "Best streak 7"; nothing until there is something to say. */
  status: string | null;
  /** The page's one main card: solid teal with dark text, so the eye lands on it first. */
  main?: boolean;
}) {
  return (
    <Link
      to={to}
      className={`group pixel-border block rounded-sm px-4 py-3 transition-colors focus-visible:outline-2 focus-visible:outline-offset-4 ${
        main
          ? "bg-teal text-void [--pixel-dash:var(--color-void)] hover:brightness-110 focus-visible:outline-ink"
          : "bg-surface hover:[--pixel-dash:var(--color-teal)] focus-visible:outline-teal"
      }`}
    >
      <span className="flex items-center justify-between gap-3">
        <span className={`pixel-bullet font-pixel text-[9px] uppercase ${main ? "text-void before:bg-void!" : "text-slate"}`}>
          {label}
        </span>
        {status && (
          <span className={`font-pixel text-[8px] uppercase ${main ? "text-void" : "text-slate"}`}>
            {status}
          </span>
        )}
      </span>
      <span className="mt-2 flex items-center justify-between gap-3">
        <span className={`font-heading text-xl font-bold ${main ? "text-void" : "text-ink"}`}>
          {title}
        </span>
        <span
          aria-hidden="true"
          className={`font-pixel text-[10px] ${main ? "text-void" : "text-teal"} transition-transform group-hover:translate-x-1 motion-reduce:transition-none`}
        >
          &gt;
        </span>
      </span>
    </Link>
  );
}
