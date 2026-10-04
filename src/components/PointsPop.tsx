import type { AnswerScore } from "../game";

/** The points an answer earned, with what made them up. */
export function PointsPop({ score }: { score: AnswerScore }) {
  if (score.total === 0) {
    return <p className="mt-2 font-pixel text-[9px] uppercase text-slate">+0 points. Streak reset.</p>;
  }
  const parts = [`${score.base} base`];
  if (score.multiplier > 1) parts.push(`x${score.multiplier} streak`);
  if (score.speedBonus > 0) parts.push(`+${score.speedBonus} speed`);
  return (
    <p className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 motion-safe:animate-[pop_400ms_ease-out]">
      <span className="font-heading text-3xl font-bold text-gold">+{score.total}</span>
      <span className="font-pixel text-[8px] uppercase text-slate">{parts.join(" / ")}</span>
    </p>
  );
}
