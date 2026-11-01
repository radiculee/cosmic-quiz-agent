import { formatClock, type Run, streakMultiplier } from "../game";

const NUMBER = new Intl.NumberFormat("en-IE");

/** The run's figures and End run, drawn in the site header's settings row during a run:
 * progress, the speedrun clock, points and streak. */
export function RunHud({
  run,
  question,
  elapsed,
  running,
  onEnd,
}: {
  run: Run;
  question: number;
  elapsed: number;
  running: boolean;
  onEnd: () => void;
}) {
  const multiplier = streakMultiplier(run.streak + 1);
  const stats: [string, string, string?][] = [
    ["Question", `${question}/${run.topics.length}`],
    ["Time", formatClock(elapsed), running ? "text-ink" : "text-slate"],
    ["Points", NUMBER.format(run.points)],
    ["Streak", run.streak > 0 ? `${run.streak}${multiplier > 1 ? ` x${multiplier}` : ""}` : "0"],
  ];
  return (
    <div className="flex items-center gap-3">
      <dl className="grid flex-1 grid-cols-4 gap-2">
        {stats.map(([label, value, colour]) => (
          <div key={label}>
            <dt className="font-pixel text-[8px] uppercase text-slate">
              <span className="sm:hidden" aria-hidden="true">
                {label === "Question" ? "Q" : label}
              </span>
              <span className={label === "Question" ? "sr-only sm:not-sr-only" : "sr-only"}>
                {label}
              </span>
            </dt>
            <dd className={`mt-1 text-sm font-medium tabular-nums ${colour ?? "text-ink"}`}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <button
        type="button"
        onClick={onEnd}
        className="shrink-0 rounded-sm border border-white/15 px-3 py-2.5 font-pixel text-[8px] uppercase text-slate hover:border-white/40 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
      >
        End run
      </button>
    </div>
  );
}
