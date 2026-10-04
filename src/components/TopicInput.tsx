import { type KeyboardEvent, useId, useState } from "react";

import type { BankTopic } from "../types";

interface TopicInputProps {
  value: string;
  suggestions: BankTopic[];
  disabled: boolean;
  onChange: (value: string) => void;
  /** Enter with no suggestion highlighted: start the round. */
  onSubmit: () => void;
}

/**
 * The topic box: a combobox that suggests bank topics as the player types. Arrow keys move
 * through the suggestions, Enter picks the highlighted one (or starts the round), Escape closes.
 */
export function TopicInput({ value, suggestions, disabled, onChange, onSubmit }: TopicInputProps) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const showList = open && suggestions.length > 0;

  function pick(topic: BankTopic) {
    onChange(topic.name);
    setOpen(false);
    setActive(-1);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      if (suggestions.length === 0) {
        return;
      }
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => (current + step + suggestions.length) % suggestions.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const highlighted = showList ? suggestions[active] : undefined;
      if (highlighted) {
        pick(highlighted);
      } else {
        setOpen(false);
        onSubmit();
      }
    } else if (event.key === "Escape") {
      setOpen(false);
      setActive(-1);
    }
  }

  return (
    <div className="relative w-full">
      <label htmlFor={`${listId}-input`} className="sr-only">
        Topic
      </label>
      <input
        id={`${listId}-input`}
        type="text"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
        autoComplete="off"
        spellCheck={false}
        placeholder="Pick a topic, e.g. Black holes"
        value={value}
        disabled={disabled}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
          setActive(-1);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
        className="w-full rounded-lg border border-white/10 bg-surface px-5 py-4 text-base text-ink placeholder:text-slate/70 focus:border-teal focus:outline-none disabled:opacity-50"
      />
      {showList && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Topics in the bank"
          className="absolute z-10 mt-2 max-h-80 w-full overflow-y-auto rounded-lg border border-white/10 bg-surface py-2 shadow-xl shadow-black/40"
        >
          {suggestions.map((topic, index) => (
            <li
              key={topic.name}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              // Pick on mouse down, before the input's blur closes the list.
              onMouseDown={(event) => {
                event.preventDefault();
                pick(topic);
              }}
              onMouseEnter={() => setActive(index)}
              className={`flex cursor-pointer items-center justify-between px-5 py-2.5 text-sm ${
                index === active ? "bg-white/5 text-ink" : "text-ink/85"
              }`}
            >
              <span>{topic.name}</span>
              {topic.kind === "news" && (
                <span className="font-pixel text-[8px] uppercase text-gold">News</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
