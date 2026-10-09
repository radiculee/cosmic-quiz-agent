import type { ReactNode } from "react";

import { formatPercent, formatUsd } from "../stats";
import { fillRatio, horizontalBar } from "./geometry";
import { TONE_FILL } from "./palette";
import { useWidth } from "./useWidth";

const HEIGHT = 10;

/**
 * The bar of a meter: spend against a cap. The fill says how close it is: teal while there is
 * room, gold from 80% and rust at the cap. The track is a faint step of the same colour.
 */
export function MeterBar({ value, cap, label }: { value: number; cap: number; label: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const ratio = fillRatio(value, cap);
  const tone = ratio >= 1 ? "bad" : ratio >= 0.8 ? "doubt" : "good";
  const fill = TONE_FILL[tone];
  const length = ratio > 0 ? Math.max(2, width * ratio) : 0;
  return (
    <div ref={ref} className="h-2.5">
      {width > 0 && (
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label={`${label}: ${formatUsd(value)} of ${formatUsd(cap)}`}
        >
          <rect width={width} height={HEIGHT} rx={HEIGHT / 2} style={{ fill, opacity: 0.18 }} />
          {length > 0 && (
            <path d={horizontalBar(0, 0, length, HEIGHT, HEIGHT / 2)} style={{ fill }} />
          )}
        </svg>
      )}
    </div>
  );
}

/** Spend against a cap, with its label and the amounts written out beside the bar. */
export function Meter({
  label,
  value,
  cap,
  note,
}: {
  label: string;
  value: number;
  cap: number;
  note?: ReactNode;
}) {
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="font-pixel text-[8px] uppercase leading-relaxed text-slate">{label}</span>
        <span className="text-sm text-ink">
          <span className="font-medium">{formatUsd(value)}</span>
          <span className="text-slate"> of {formatUsd(cap)}</span>
          <span className="ml-2 text-xs text-slate">{formatPercent(value, cap)}</span>
        </span>
      </div>
      <div className="mt-2">
        <MeterBar value={value} cap={cap} label={label} />
      </div>
      {note !== undefined && <p className="mt-2 text-xs leading-snug text-slate">{note}</p>}
    </div>
  );
}
