import { formatClock, type Run, streakMultiplier } from "../game";

const NUMBER = new Intl.NumberFormat("en-IE");

/** The bar above the question during a run: progress, the speedrun clock, points and streak. */
export function RunHud({
  run,
  question,
  elapsed,
  running,
}: {
  run: Run;
  question: number;
  elapsed: number;
  running: boolean;
}) {
  const multiplier = streakMultiplier(run.streak + 1);
  const stats: [string, string, string?][] = [
    ["Question", `${question}/${run.topics.length}`],
    ["Time", formatClock(elapsed), running ? "text-ink" : "text-slate"],
    ["Points", NUMBER.format(run.points)],
    ["Streak", run.streak > 0 ? `${run.streak}${multiplier > 1 ? ` x${multiplier}` : ""}` : "0"],
  ];
  return (
    <div className="mb-4">
      <dl className="grid grid-cols-2 gap-3 rounded-lg border border-white/10 bg-surface px-4 py-3 sm:grid-cols-4">
        {stats.map(([label, value, colour]) => (
          <div key={label}>
            <dt className="font-pixel text-[8px] uppercase text-slate">{label}</dt>
            <dd className={`mt-1 font-medium tabular-nums ${colour ?? "text-ink"}`}>{value}</dd>
          </div>
        ))}
      </dl>
      {run.repeats && (
        <p className="mt-2 text-xs text-slate">
          You have played every other topic at this level, so some questions repeat.
        </p>
      )}
    </div>
  );
}
