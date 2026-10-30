import { useEffect, useRef, useState } from "react";

import { stillFollowing } from "../scroll";
import { itemLabel, itemTag } from "../search";
import type { ItemKey, Tone, Verdict } from "../types";

export interface LogLine {
  /** The item of the search the line is about; null for the search as a whole. */
  key: ItemKey | null;
  label: string;
  detail: string;
  tone: Tone;
  verdict: Verdict | null;
}

export type LogOutcome =
  | { kind: "running" }
  | { kind: "done"; message: string }
  | { kind: "nothing"; message: string }
  | { kind: "rejected"; message: string }
  | { kind: "fallback"; message: string };

const TONE_COLOURS: Record<Tone, string> = {
  info: "text-ink/85",
  ok: "text-teal",
  warn: "text-rust",
};

const VERDICT_COLOURS: Record<Verdict, string> = {
  supports: "text-teal",
  contradicts: "text-rust",
  says_nothing: "text-slate",
};

const OUTCOMES: Record<Exclude<LogOutcome["kind"], "running">, [string, string]> = {
  done: ["Done", "text-teal"],
  nothing: ["Nothing made", "text-slate"],
  rejected: ["Rejected", "text-rust"],
  fallback: ["Back to the bank", "text-slate"],
};

function useElapsed(running: boolean): number {
  const started = useRef(performance.now());
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setElapsed(performance.now() - started.current), 100);
    return () => window.clearInterval(timer);
  }, [running]);
  return elapsed;
}

/** The live agent log: each step of a search's runs as it happens, in one stream, each line
 * tagged with its item ("EASY Q"), since a search's runs go at once and their lines interleave.
 * New lines scroll the log's own box, and only while the reader is at its end; they never move
 * the page, so a player answering a question further down stays where they are.
 *
 * `open` (default true) shows the lines. Closed, the log keeps only its header and outcome, for
 * a page that puts the lines behind "Show details"; it still follows the newest line, so opening
 * it shows the latest. The page owns the toggle. */
export function AgentLog({
  topic,
  lines,
  outcome,
  open = true,
}: {
  topic: string;
  lines: LogLine[];
  outcome: LogOutcome;
  open?: boolean;
}) {
  const running = outcome.kind === "running";
  const elapsed = useElapsed(running);
  const list = useRef<HTMLOListElement>(null);
  // Whether the log keeps its newest line in view: until the reader scrolls up in it.
  const following = useRef(true);
  // Where the log last put the box's scroll position.
  const pinned = useRef(0);

  useEffect(() => {
    const box = list.current;
    if (box && following.current) {
      box.scrollTop = box.scrollHeight;
      pinned.current = box.scrollTop;
    }
  }, [lines.length, open]);

  function onScroll() {
    if (list.current) {
      following.current = stillFollowing(list.current, pinned.current);
    }
  }

  return (
    <section
      aria-label={`Agent log for ${topic}`}
      className="pixel-border w-full rounded-sm bg-surface px-4 py-5 sm:px-6"
    >
      <header className="flex items-baseline justify-between gap-4 border-b border-white/5 pb-3">
        <p className="font-pixel text-[9px] uppercase text-teal">
          Agent <span className="text-slate">/ {topic}</span>
        </p>
        <p className="font-mono text-xs tabular-nums text-slate" aria-hidden="true">
          {(elapsed / 1000).toFixed(1)}s
        </p>
      </header>

      <ol
        ref={list}
        hidden={!open}
        role="log"
        aria-live="polite"
        onScroll={onScroll}
        className="mt-3 max-h-96 space-y-1 overflow-y-auto font-mono text-[13px] leading-6"
      >
        {lines.map((line, index) => (
          <li key={index} className="flex items-baseline gap-2">
            <span aria-hidden="true" className="text-slate">
              &gt;
            </span>
            {line.key !== null && (
              <span
                className="w-24 shrink-0 whitespace-nowrap font-pixel text-[8px] uppercase text-slate"
                title={itemLabel(line.key)}
              >
                <span aria-hidden="true">{itemTag(line.key)}</span>
                <span className="sr-only">{itemLabel(line.key)}:</span>
              </span>
            )}
            <span className={`shrink-0 ${TONE_COLOURS[line.tone]}`}>{line.label}</span>
            <span aria-hidden="true" className="min-w-4 flex-1 -translate-y-1 border-b border-dotted border-white/15" />
            <span
              className={`max-w-[60%] truncate text-right ${
                line.verdict ? VERDICT_COLOURS[line.verdict] : "text-slate"
              }`}
              title={line.detail}
            >
              {line.detail}
            </span>
          </li>
        ))}
        <li className="pt-1">
          {running ? (
            <span className="text-slate">
              <span className="motion-safe:animate-pulse">_</span> working
            </span>
          ) : null}
        </li>
      </ol>

      {outcome.kind !== "running" && (
        <footer className="mt-3 border-t border-white/5 pt-3">
          <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className={`font-pixel text-[9px] uppercase ${OUTCOMES[outcome.kind][1]}`}>
              {OUTCOMES[outcome.kind][0]}
            </span>
            <span className="text-sm text-ink/90">{outcome.message}</span>
          </p>
        </footer>
      )}
    </section>
  );
}
