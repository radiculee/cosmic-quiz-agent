import { formatCount, formatPercent, type Part } from "../stats";
import { block, horizontalBar, splitLayout } from "./geometry";
import { TONE_FILL } from "./palette";
import { useWidth } from "./useWidth";

const HEIGHT = 14;

/**
 * A whole split into its parts: one bar, each part coloured by what it means, with a 2px gap
 * between parts. The legend under it names every part with its count and share, so the numbers
 * never depend on colour or on hovering; hovering a part shows the same.
 */
export function BarSplit({ title, parts }: { title: string; parts: readonly Part[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const total = parts.reduce((sum, part) => sum + part.value, 0);
  const segments = splitLayout(
    parts.map((part) => part.value),
    width,
  );
  const last = segments.length - 1;
  const summary = parts.map((part) => `${part.label} ${part.value}`).join(", ");

  return (
    <figure>
      <figcaption className="font-pixel text-[8px] uppercase leading-relaxed text-slate">
        {title}
        <span className="ml-2 normal-case text-slate/80">({formatCount(total)})</span>
      </figcaption>
      <div ref={ref} className="mt-3 h-3.5">
        {total > 0 && width > 0 && (
          <svg width={width} height={HEIGHT} role="img" aria-label={`${title}: ${summary}`}>
            {segments.map((segment, position) => {
              const part = parts[segment.index];
              if (!part) {
                return null;
              }
              // The last part carries the bar's rounded data end; the rest are square.
              const d =
                position === last
                  ? horizontalBar(segment.x, 0, segment.width, HEIGHT)
                  : block(segment.x, 0, segment.width, HEIGHT);
              return (
                <path
                  key={part.label}
                  d={d}
                  style={{ fill: TONE_FILL[part.tone] }}
                  className="transition-opacity hover:opacity-80"
                >
                  <title>{`${part.label}: ${formatCount(part.value)} (${formatPercent(part.value, total)})`}</title>
                </path>
              );
            })}
          </svg>
        )}
        {total === 0 && <p className="text-xs text-slate">None in these runs.</p>}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
        {parts.map((part) => (
          <li key={part.label} className="flex items-baseline gap-2">
            <span
              aria-hidden="true"
              className="inline-block h-2.5 w-2.5 shrink-0 self-center rounded-[2px]"
              style={{ backgroundColor: TONE_FILL[part.tone] }}
            />
            <span className={part.value > 0 ? "text-ink/90" : "text-slate"}>{part.label}</span>
            <span className="font-medium text-ink">{formatCount(part.value)}</span>
            <span className="text-xs text-slate">{formatPercent(part.value, total)}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
