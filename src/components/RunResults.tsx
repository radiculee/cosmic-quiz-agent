import { formatClock, isRunFinished, rankFor, type Run, runAccuracy, runCorrect } from "../game";
import { type Award, trophy } from "../trophies";
import { TrophyIcon } from "./TrophyIcon";

const NUMBER = new Intl.NumberFormat("en-IE");

interface RunResultsProps {
  run: Run;
  elapsed: number;
  pointsBefore: number;
  pointsAfter: number;
  /** Everything earned during the run, already shown in the pop-up; listed again as a recap. */
  awards: readonly Award[];
  onPlayAgain: () => void;
  onChangeSettings: () => void;
}

/**
 * The end of a run: score, time, points, rank progress, new trophies and a recap. A run ended
 * early shows the questions answered so far; it earns no full-run trophies.
 */
export function RunResults({
  run,
  elapsed,
  pointsBefore,
  pointsAfter,
  awards,
  onPlayAgain,
  onChangeSettings,
}: RunResultsProps) {
  const finished = isRunFinished(run);
  const correct = runCorrect(run);
  const answered = run.results.length;
  const before = rankFor(pointsBefore);
  const after = rankFor(pointsAfter);
  const trophies = awards.flatMap((award) => (award.kind === "trophy" ? [award] : []));
  const stats: [string, string][] = [
    ["Points", `+${NUMBER.format(run.points)}`],
    ["Accuracy", `${Math.round(runAccuracy(run) * 100)}%`],
    ["Best streak", String(run.bestStreak)],
    ["Time", formatClock(elapsed)],
  ];

  return (
    <article className="pixel-border w-full rounded-sm bg-surface px-5 py-8 text-center sm:px-8">
      <p className="font-pixel text-[9px] uppercase text-slate">
        {finished ? "Run complete" : "Run ended"} / {run.difficulty}
      </p>
      <p className="mt-4 font-heading text-6xl font-bold">
        <span className={finished && correct === answered ? "text-gold" : "text-teal"}>{correct}</span>
        <span className="text-slate">/{answered}</span>
      </p>
      {!finished && (
        <p className="mt-3 text-sm text-slate">
          {answered} of {run.topics.length} questions answered. Points count; full-run trophies
          need every question.
        </p>
      )}

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

      {trophies.length > 0 && (
        <div className="mt-6">
          <p className="font-pixel text-[8px] uppercase text-slate">New trophies</p>
          <ul className="mt-3 flex flex-wrap justify-center gap-3">
            {trophies.map((award) => {
              const label = `${trophy(award.id).name}: ${award.tier}`;
              return (
                <li key={`${award.id}-${award.tier}`} title={label}>
                  <TrophyIcon glyph={award.id} tone={award.tier} />
                  <span className="sr-only">{label}</span>
                </li>
              );
            })}
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
