import type { OptionCheck, SourceCheck, Verdict } from "../types";

const LABELS: Record<Verdict, string> = {
  supports: "Supported",
  contradicts: "Contradicted",
  says_nothing: "Not addressed",
};

const COLOURS: Record<Verdict, string> = {
  supports: "text-teal",
  contradicts: "text-rust",
  says_nothing: "text-slate",
};

const BARS: Record<Verdict, string> = {
  supports: "bg-teal",
  contradicts: "bg-rust",
  says_nothing: "bg-slate",
};

function Meter({ check }: { check: OptionCheck }) {
  const percent = Math.round(check.confidence * 100);
  return (
    <div className="flex items-center gap-3">
      <div
        className="h-1.5 w-20 overflow-hidden rounded-full bg-white/10"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label={`Confidence ${percent} percent`}
      >
        <div className={`h-full ${BARS[check.verdict]}`} style={{ width: `${percent}%` }} />
      </div>
      <span className="w-9 text-right text-xs tabular-nums text-slate">
        {check.confidence.toFixed(2)}
      </span>
    </div>
  );
}

const CAPTION =
  "What the cited sources say, as judged by Jev, a second AI model. It checks the sources, not the truth.";

/** Per answer option for a quiz item: what the cited sources say about each one. */
export function QuizSourceCheck({ check, options }: { check: SourceCheck; options: string[] }) {
  const byOption = new Map(check.options.map((entry) => [entry.option, entry]));
  return (
    <section aria-labelledby="source-check-heading" className="mt-8">
      <h3 id="source-check-heading" className="font-pixel text-[9px] uppercase text-slate">
        Source check
      </h3>
      <p className="mt-2 text-xs text-slate">{CAPTION}</p>
      <ul className="mt-4 space-y-3">
        {options.map((option, index) => {
          const entry = byOption.get(index);
          return (
            <li key={option} className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1 sm:grid-cols-[auto_1fr_auto_auto]">
              <span className="font-pixel text-[9px] text-slate">{"ABCD"[index]}</span>
              <span className="text-sm text-ink/90">{option}</span>
              {entry ? (
                <>
                  <span
                    className={`col-start-2 font-pixel text-[8px] uppercase sm:col-start-auto ${COLOURS[entry.verdict]}`}
                  >
                    {LABELS[entry.verdict]}
                  </span>
                  <div className="col-start-2 sm:col-start-auto">
                    <Meter check={entry} />
                  </div>
                </>
              ) : (
                <span className="col-start-2 font-pixel text-[8px] uppercase text-slate sm:col-span-2 sm:col-start-auto">
                  Not checked
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** One line for a LEARN item: how many sentences of the explanation the sources back. */
export function LearnSourceCheck({ check }: { check: SourceCheck }) {
  if (check.sentences === 0) {
    return null;
  }
  return (
    <section aria-labelledby="source-check-heading" className="mt-8">
      <h3 id="source-check-heading" className="font-pixel text-[9px] uppercase text-slate">
        Source check
      </h3>
      <p className="mt-3 text-sm text-ink/90">
        <span className="font-medium text-teal">
          {check.sentences_supported} of {check.sentences}
        </span>{" "}
        sentences are backed by the cited sources.
      </p>
      <p className="mt-2 text-xs text-slate">{CAPTION}</p>
    </section>
  );
}
