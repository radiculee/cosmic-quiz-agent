import type { ReactNode } from "react";

import { formatCount, type Row } from "../stats";
import { columnLayout, verticalBar } from "./geometry";
import { LABEL_FILL, RULE, SERIES_FILL, VALUE_FILL } from "./palette";
import { useWidth } from "./useWidth";

const PLOT = 96;
const TOP = 16; // room for the value on the tallest column
const AXIS = 18; // room for the bin labels under the baseline

/**
 * How many fall in each bin, as columns from one baseline. Each non-empty column carries its
 * count on its cap and every bin is labelled under the baseline, so nothing needs a hover to be
 * read; hovering a column shows its bin and count too. Empty bins are left blank, not drawn.
 */
export function Histogram({
  title,
  bins,
  caption,
  note,
}: {
  title: string;
  /** In order along the axis; each label names its bin. */
  bins: readonly Row[];
  /** What the axis measures, under the bin labels. */
  caption: string;
  note?: ReactNode;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const max = Math.max(0, ...bins.map((bin) => bin.value));
  const columns = columnLayout(bins.length, width);
  const baseline = TOP + PLOT;
  const summary = bins.map((bin) => `${bin.label}: ${bin.value}`).join(", ");
  return (
    <figure>
      <figcaption className="font-pixel text-[8px] uppercase leading-relaxed text-slate">
        {title}
      </figcaption>
      <div ref={ref} className="mt-2" style={{ height: TOP + PLOT + AXIS }}>
        {width > 0 && max > 0 && (
          <svg
            width={width}
            height={TOP + PLOT + AXIS}
            role="img"
            aria-label={`${title}. ${caption}. ${summary}`}
          >
            <line
              x1={0}
              x2={width}
              y1={baseline + 0.5}
              y2={baseline + 0.5}
              style={{ stroke: RULE }}
            />
            {bins.map((bin, index) => {
              const column = columns[index];
              if (!column) {
                return null;
              }
              const height = bin.value > 0 ? Math.max(2, (PLOT * bin.value) / max) : 0;
              const middle = column.x + column.width / 2;
              return (
                <g key={bin.label}>
                  {height > 0 && (
                    <>
                      <path
                        d={verticalBar(column.x, baseline, column.width, height)}
                        style={{ fill: SERIES_FILL }}
                        className="transition-opacity hover:opacity-80"
                      >
                        <title>{`${bin.label}: ${formatCount(bin.value)}`}</title>
                      </path>
                      <text
                        x={middle}
                        y={baseline - height - 5}
                        textAnchor="middle"
                        fontSize={10}
                        style={{ fill: VALUE_FILL }}
                        className="tabular-nums"
                      >
                        {formatCount(bin.value)}
                      </text>
                    </>
                  )}
                  <text
                    x={middle}
                    y={baseline + 13}
                    textAnchor="middle"
                    fontSize={10}
                    style={{ fill: LABEL_FILL }}
                    className="tabular-nums"
                  >
                    {bin.label}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
        {max === 0 && <p className="text-xs text-slate">None in these runs.</p>}
      </div>
      <p className="mt-1 text-center text-xs text-slate">{caption}</p>
      {note !== undefined && <p className="mt-2 text-xs leading-snug text-slate">{note}</p>}
    </figure>
  );
}
