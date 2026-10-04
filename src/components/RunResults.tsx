import { type BadgeId, formatClock, rankFor, type Run, runCorrect } from "../game";
import { BadgeChip } from "./BadgeChip";

const NUMBER = new Intl.NumberFormat("en-IE");

interface RunResultsProps {
  run: Run;
  elapsed: number;
  pointsBefore: number;
  pointsAfter: number;
  newBadges: BadgeId[];
  onPlayAgain: () => void;
  onChangeSettings: () => void;
}

/** The end of a run: score, time, points, rank progress, new badges and a recap. */
export function RunResults({
  run,
  elapsed,
  pointsBefore,
  pointsAfter,
  newBadges,
  onPlayAgain,
  onChangeSettings,
}: RunResultsProps) {
  const correct = runCorrect(run);
  const total = run.topics.length;
  const before = rankFor(pointsBefore);
  const after = rankFor(pointsAfter);
  const stats: [string, string][] = [
    ["Points", `+${NUMBER.format(run.points)}`],
    ["Accuracy", `${Math.round((correct / Math.max(total, 1)) * 100)}%`],
    ["Best streak", String(run.bestStreak)],
    ["Time", formatClock(elapsed)],
  ];

  return (
    <article className="pixel-border w-full rounded-sm bg-surface/70 px-5 py-8 text-center sm:px-8">
      <p className="font-pixel text-[9px] uppercase text-slate">
        Run complete / {run.difficulty}
      </p>
      <p className="mt-4 font-heading text-6xl font-bold">
        <span className={correct === total ? "text-gold" : "text-teal"}>{correct}</span>
        <span className="text-slate">/{total}</span>
      </p>

      <dl className="mx-auto mt-8 grid max-w-md grid-cols-2 gap-4 sm:grid-cols-4">
        {stats.map(([label, value]) => (
          <div key={label}>
            <dt className="font-pixel text-[8px] uppercase text-slate">{label}</dt>
            <dd className="mt-1 text-lg font-medium tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>

      <p className="mt-8 text-sm text-ink/90">
        {after.name !== before.name ? (
          <>
            Rank up: <span className="font-bold text-gold">{after.name}</span>
          </>
        ) : (
          <>
            {after.name}
            {after.next &&
              `: ${NUMBER.format(after.next.points - pointsAfter)} points to ${after.next.name}`}
          </>
        )}
      </p>

      {newBadges.length > 0 && (
        <div className="mt-6">
          <p className="font-pixel text-[8px] uppercase text-slate">New badges</p>
          <ul className="mt-3 flex flex-wrap justify-center gap-2">
            {newBadges.map((id) => (
              <BadgeChip key={id} id={id} earned />
            ))}
          </ul>
        </div>
      )}

      <ol className="mx-auto mt-8 max-w-md space-y-1.5 text-left text-sm">
        {run.results.map((result, index) => (
          <li key={`${result.itemId}-${index}`} className="flex items-center gap-3">
            <span
              aria-hidden="true"
              className={`inline-block size-2 ${result.correct ? "bg-teal" : "bg-rust"}`}
            />
            <span className="flex-1 truncate text-ink/90">{result.topic}</span>
            <span className="sr-only">{result.correct ? "correct" : "wrong"}</span>
            <span className="tabular-nums text-slate">+{result.score.total}</span>
          </li>
        ))}
      </ol>

      <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
        <button
          type="button"
          onClick={onChangeSettings}
          className="rounded-lg border border-white/10 bg-surface px-5 py-3.5 font-pixel text-[9px] uppercase text-ink hover:border-white/25 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
        >
          Change settings
        </button>
        <button
          type="button"
          onClick={onPlayAgain}
          className="rounded-lg bg-teal px-8 py-3.5 font-pixel text-[10px] uppercase text-void hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
        >
          Play again
        </button>
      </div>
    </article>
  );
}
