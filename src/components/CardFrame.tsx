import type { ReactNode } from "react";

import type { Difficulty, Mode } from "../types";

/** The panel a round is shown in: pixel-dashed edge, mode and difficulty tag, topic heading. */
export function CardFrame({
  mode,
  difficulty,
  topic,
  children,
}: {
  mode: Mode;
  difficulty: Difficulty;
  topic: string;
  children: ReactNode;
}) {
  return (
    <article className="pixel-border w-full rounded-sm bg-surface/70 px-5 py-7 sm:px-8">
      <p className="pixel-bullet font-pixel text-[8px] uppercase text-slate">
        {mode} / {difficulty}
      </p>
      <h2 className="mt-3 font-heading text-2xl font-bold sm:text-3xl">{topic}</h2>
      {children}
    </article>
  );
}
