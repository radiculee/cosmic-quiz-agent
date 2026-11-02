import { type WebScore, scoreText } from "../webResults";
import { PRIMARY_BUTTON, SECONDARY_BUTTON } from "../pages/common";

/** What the player can do about the explanations once the questions are done. */
export interface ExplanationsAction {
  label: string;
  disabled: boolean;
  onClick: () => void;
}

function Tile({ label, count, mark }: { label: string; count: number; mark: string }) {
  return (
    <div className={`flex-1 rounded-sm border-t-4 bg-void px-4 py-3 text-center ${mark}`}>
      <p className="font-heading text-3xl font-bold tabular-nums">{count}</p>
      <p className="mt-1 font-pixel text-[8px] uppercase text-ink">{label}</p>
    </div>
  );
}

/**
 * After the last question of a web search: the score, the questions answered right and wrong,
 * and what to do next. It makes no model call; every figure comes from the player's answers.
 */
export function WebResults({
  score,
  explanations,
  onNewTopic,
}: {
  score: WebScore;
  explanations: ExplanationsAction | null;
  onNewTopic: () => void;
}) {
  return (
    <section
      aria-label="Your result"
      className="pixel-border mb-4 w-full rounded-sm bg-surface px-5 py-6 text-center sm:px-8"
    >
      <p className="font-pixel text-[9px] uppercase text-slate">Your result</p>
      <p className="mt-3 font-heading text-5xl font-bold text-teal">{scoreText(score)}</p>
      <div className="mx-auto mt-5 flex max-w-sm gap-3">
        <Tile label="Correct" count={score.correct} mark="border-teal" />
        <Tile label="Incorrect" count={score.incorrect} mark="border-rust" />
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        {explanations && (
          <button
            type="button"
            onClick={explanations.onClick}
            disabled={explanations.disabled}
            className={`${PRIMARY_BUTTON} px-5 py-3.5 text-[10px]`}
          >
            {explanations.label}
          </button>
        )}
        <button
          type="button"
          onClick={onNewTopic}
          className={`${explanations ? SECONDARY_BUTTON : PRIMARY_BUTTON} px-5 py-3.5 text-[10px]`}
        >
          Another new topic
        </button>
      </div>
    </section>
  );
}
