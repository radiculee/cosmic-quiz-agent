import type { ReactNode } from "react";

/**
 * One figure with its label: the number is the chart. Use inside a <dl> (see `Tiles`). The value
 * keeps proportional figures; a note under it says what the number is out of, or how it was
 * measured. `chart` adds one small graphic under the value (a meter, for example), and `large`
 * is for a tab's four key figures.
 */
export function StatTile({
  label,
  value,
  note,
  chart,
  large = false,
}: {
  label: string;
  value: string;
  note?: ReactNode;
  chart?: ReactNode;
  large?: boolean;
}) {
  return (
    <div
      className={`rounded-sm border border-white/10 bg-surface/60 ${large ? "px-5 py-5" : "px-4 py-3.5"}`}
    >
      <dt className="font-pixel text-[8px] uppercase leading-relaxed text-slate">{label}</dt>
      <dd
        className={`font-heading font-bold leading-none text-ink ${
          large ? "mt-3 text-4xl" : "mt-2 text-2xl"
        }`}
      >
        {value}
      </dd>
      {chart !== undefined && <dd className="mt-3">{chart}</dd>}
      {note !== undefined && <dd className="mt-2 text-xs leading-snug text-slate">{note}</dd>}
    </div>
  );
}

/** A row of tiles: two across on a phone, up to four on a wide screen. */
export function Tiles({ children, columns = 4 }: { children: ReactNode; columns?: 2 | 3 | 4 }) {
  const wide = { 2: "sm:grid-cols-2", 3: "sm:grid-cols-3", 4: "sm:grid-cols-4" }[columns];
  return <dl className={`grid grid-cols-2 gap-3 ${wide}`}>{children}</dl>;
}
