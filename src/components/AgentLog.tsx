import { useEffect, useRef, useState } from "react";

import type { Difficulty, Mode, Tone, Verdict } from "../types";

export interface LogLine {
  label: string;
  detail: string;
  tone: Tone;
  verdict: Verdict | null;
}

export type LogOutcome =
  | { kind: "running" }
  | { kind: "published" }
  | { kind: "review" }
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
  published: ["Published", "text-teal"],
  review: ["In review", "text-gold"],
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

/** The live agent log: each step of a custom-topic run as it happens. */
export function AgentLog({
  topic,
  mode,
  difficulty,
  lines,
  outcome,
}: {
  topic: string;
  mode: Mode;
  difficulty: Difficulty;
  lines: LogLine[];
  outcome: LogOutcome;
}) {
  const running = outcome.kind === "running";
  const elapsed = useElapsed(running);
  const end = useRef<HTMLLIElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [lines.length]);

  return (
    <section
      aria-label={`Agent log for ${topic}`}
      className="pixel-border w-full rounded-sm bg-surface/80 px-4 py-5 sm:px-6"
    >
      <header className="flex items-baseline justify-between gap-4 border-b border-white/5 pb-3">
        <p className="font-pixel text-[9px] uppercase text-teal">
          Agent <span className="text-slate">/ {topic} / {mode} / {difficulty}</span>
        </p>
        <p className="font-mono text-xs tabular-nums text-slate" aria-hidden="true">
          {(elapsed / 1000).toFixed(1)}s
        </p>
      </header>

      <ol role="log" aria-live="polite" className="mt-3 max-h-96 space-y-1 overflow-y-auto font-mono text-[13px] leading-6">
        {lines.map((line, index) => (
          <li key={index} className="flex items-baseline gap-2">
            <span aria-hidden="true" className="text-slate">
              &gt;
            </span>
            <span className={`shrink-0 ${TONE_COLOURS[line.tone]}`}>{line.label}</span>
            <span aria-hidden="true" className="min-w-4 flex-1 translate-y-[-4px] border-b border-dotted border-white/15" />
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
        <li ref={end} className="pt-1">
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
            <span className="text-sm text-ink/90">
              {outcome.kind === "published" && "Added to the bank for everyone."}
              {outcome.kind === "review" &&
                "Shown to you now, marked not fully verified. It joins the bank once it is reviewed."}
              {(outcome.kind === "rejected" || outcome.kind === "fallback") && outcome.message}
            </span>
          </p>
        </footer>
      )}
    </section>
  );
}
