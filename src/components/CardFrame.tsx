import type { ReactNode } from "react";

import type { Difficulty, Mode, ShownStatus } from "../types";

/**
 * The panel a round is shown in: pixel-dashed edge, mode and difficulty tag, topic heading. An
 * item in review (only ever the player's own live result) is tagged as not fully verified.
 */
export function CardFrame({
  mode,
  difficulty,
  topic,
  status = "published",
  children,
}: {
  mode: Mode;
  difficulty: Difficulty;
  topic: string;
  status?: ShownStatus;
  children: ReactNode;
}) {
  return (
    <article className="pixel-border w-full rounded-sm bg-surface px-5 py-7 sm:px-8">
      <p className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="pixel-bullet font-pixel text-[8px] uppercase text-slate">
          {mode} / {difficulty}
        </span>
        {status === "review" && (
          <span className="rounded-sm border border-gold/50 px-2 py-1 font-pixel text-[8px] uppercase text-gold">
            Not fully verified
          </span>
        )}
      </p>
      <h2 className="mt-3 font-heading text-2xl font-bold sm:text-3xl">{topic}</h2>
      {children}
    </article>
  );
}
