import type { ReactNode } from "react";

export interface TableColumn {
  label: string;
  /** Numbers line up on the right. */
  numeric?: boolean;
}

/**
 * A small table of figures: the plain view of numbers that suit a grid better than a chart.
 * Numeric columns are right-aligned with tabular figures, so digits line up down the column.
 * The first cell of each row is its header.
 */
export function Table({
  caption,
  columns,
  rows,
  note,
}: {
  caption: string;
  columns: readonly TableColumn[];
  rows: readonly (readonly ReactNode[])[];
  note?: ReactNode;
}) {
  return (
    <figure>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[20rem] border-collapse text-sm">
          <caption className="pb-3 text-left font-pixel text-[8px] uppercase leading-relaxed text-slate">
            {caption}
          </caption>
          <thead>
            <tr className="border-b border-white/10">
              {columns.map((column) => (
                <th
                  key={column.label}
                  scope="col"
                  className={`pb-2 text-xs font-medium text-slate ${
                    column.numeric ? "pl-3 text-right" : "pr-3 text-left"
                  }`}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-white/5 last:border-0">
                {row.map((cell, index) => {
                  const column = columns[index];
                  const align = column?.numeric
                    ? "pl-3 text-right tabular-nums text-ink"
                    : "pr-3 text-left text-ink/90";
                  return index === 0 ? (
                    <th key={index} scope="row" className={`py-2 align-top font-normal ${align}`}>
                      {cell}
                    </th>
                  ) : (
                    <td key={index} className={`py-2 align-top ${align}`}>
                      {cell}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {note !== undefined && <p className="mt-2 text-xs leading-snug text-slate">{note}</p>}
    </figure>
  );
}
