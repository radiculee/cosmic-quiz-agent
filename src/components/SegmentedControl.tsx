import { type KeyboardEvent, useRef } from "react";

interface SegmentedControlProps<T extends string | number> {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
  /** Choices shown but not available (greyed and skipped by the keyboard). */
  disabled?: readonly T[];
  /** The id of a line explaining why some choices are not available. */
  describedBy?: string | undefined;
  /** Smaller buttons, for a row of filters. */
  compact?: boolean;
}

/**
 * A row of mutually exclusive choices, built as a radio group: Tab reaches the selected choice,
 * and the arrow keys move between the available choices, as screen-reader users expect.
 */
export function SegmentedControl<T extends string | number>({
  label,
  options,
  value,
  onChange,
  disabled = [],
  describedBy,
  compact = false,
}: SegmentedControlProps<T>) {
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  function move(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const step =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? 1
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? -1
          : 0;
    if (step === 0) {
      return;
    }
    event.preventDefault();
    const count = options.length;
    for (let offset = 1; offset < count; offset += 1) {
      const next = (((index + step * offset) % count) + count) % count;
      const option = options[next];
      if (option !== undefined && !disabled.includes(option)) {
        onChange(option);
        buttons.current[next]?.focus();
        return;
      }
    }
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      aria-describedby={describedBy}
      className="inline-flex gap-1 rounded-lg border border-white/10 bg-surface p-1"
    >
      {options.map((option, index) => {
        const selected = option === value;
        const off = disabled.includes(option);
        return (
          <button
            key={String(option)}
            ref={(element) => {
              buttons.current[index] = element;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={off}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(option)}
            onKeyDown={(event) => move(event, index)}
            className={`rounded-md font-pixel uppercase leading-none ${
              compact ? "px-3 py-2.5 text-[8px]" : "px-5 py-3 text-[10px]"
            } transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:cursor-not-allowed disabled:text-slate/30 disabled:line-through disabled:decoration-slate/30 ${
              selected ? "bg-teal text-void" : "text-slate hover:text-ink"
            }`}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}
