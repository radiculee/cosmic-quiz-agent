import type { ReactNode } from "react";

import { formatCount, type Row } from "../stats";
import { horizontalBar } from "./geometry";
import { SERIES_FILL } from "./palette";
import { useWidth } from "./useWidth";

const HEIGHT = 12;

function Bar({ value, max, label }: { value: number; max: number; label: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const length = max > 0 ? Math.max(value > 0 ? 2 : 0, (width * value) / max) : 0;
  return (
    <div ref={ref} className="h-3">
      {width > 0 && length > 0 && (
        <svg width={width} height={HEIGHT} aria-hidden="true">
          <path
            d={horizontalBar(0, 0, length, HEIGHT)}
            style={{ fill: SERIES_FILL }}
            className="transition-opacity hover:opacity-80"
          >
            <title>{label}</title>
          </path>
        </svg>
      )}
    </div>
  );
}

/**
 * Rows ranked by size, one series: each row's label, its bar from a shared baseline, and its
 * value at the bar's tip. A short list, so every row carries its value; it reads as a table
 * with a bar in it, and a screen reader gets it as a list of label and value.
 */
export function BarList({
  title,
  rows,
  format = formatCount,
  note,
}: {
  title: string;
  rows: readonly Row[];
  format?: (value: number) => string;
  note?: ReactNode;
}) {
  const max = Math.max(0, ...rows.map((row) => row.value));
  return (
    <figure>
      <figcaption className="font-pixel text-[8px] uppercase leading-relaxed text-slate">
        {title}
      </figcaption>
      {rows.length === 0 ? (
        <p className="mt-3 text-xs text-slate">None in these runs.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {rows.map((row) => (
            <li
              key={row.label}
              className="grid grid-cols-[minmax(0,9rem)_1fr_3.5rem] items-center gap-3 text-sm sm:grid-cols-[minmax(0,16rem)_1fr_4.5rem]"
            >
              {/* Labels wrap rather than being cut off. */}
              <span className="leading-snug break-words text-ink/90">{row.label}</span>
              <Bar value={row.value} max={max} label={`${row.label}: ${format(row.value)}`} />
              <span className="text-right font-medium tabular-nums text-ink">
                {format(row.value)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {note !== undefined && <p className="mt-3 text-xs leading-snug text-slate">{note}</p>}
    </figure>
  );
}
