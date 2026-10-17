interface DropdownProps<T extends string> {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
  /** Choices listed but not available (greyed in the list, and not selectable). */
  disabled?: readonly T[];
  /** The id of a line explaining why some choices are not available. */
  describedBy?: string | undefined;
  /** Grow to the height of its row (in a bar beside other controls) instead of a fixed one. */
  stretch?: boolean;
}

/**
 * One choice from a short list, built on a native select so a phone shows its own picker and the
 * keyboard and screen readers work as they do everywhere. The select lies invisibly over a face
 * drawn in the site's style (the choice as a pixel label, and a chevron); its text is 16px, so
 * iOS never zooms the page into it (tests/test_packaging.py holds that).
 */
export function Dropdown<T extends string>({
  label,
  options,
  value,
  onChange,
  disabled = [],
  describedBy,
  stretch = false,
}: DropdownProps<T>) {
  return (
    <div
      className={`relative inline-flex w-28 shrink-0 items-center justify-between gap-2 rounded-lg border border-white/10 bg-surface px-3 text-teal transition-colors hover:border-white/25 has-[select:focus-visible]:outline-2 has-[select:focus-visible]:outline-offset-2 has-[select:focus-visible]:outline-teal ${
        stretch ? "min-h-12 self-stretch" : "h-12"
      }`}
    >
      <span aria-hidden="true" className="font-pixel text-[10px] uppercase leading-none">
        {value}
      </span>
      <Chevron />
      <select
        aria-label={label}
        aria-describedby={describedBy}
        value={value}
        onChange={(event) => {
          const next = options.find((option) => option === event.target.value);
          if (next !== undefined) {
            onChange(next);
          }
        }}
        className="absolute inset-0 h-full w-full cursor-pointer appearance-none bg-surface text-base text-ink opacity-0 scheme-dark"
      >
        {options.map((option) => (
          <option key={option} value={option} disabled={disabled.includes(option)}>
            {option.charAt(0).toUpperCase() + option.slice(1)}
          </option>
        ))}
      </select>
    </div>
  );
}

/** A small down chevron drawn from squares, matching the pixel accents. Decorative only. */
function Chevron() {
  return (
    <svg
      viewBox="0 0 10 6"
      width="10"
      height="6"
      aria-hidden="true"
      className="shrink-0"
      shapeRendering="crispEdges"
    >
      <path d="M0 0h2v2H0zM8 0h2v2H8zM2 2h2v2H2zM6 2h2v2H6zM4 4h2v2H4z" fill="currentColor" />
    </svg>
  );
}
