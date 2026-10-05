import { useEffect, useRef, useState } from "react";

import { fetchAnswer } from "../api";
import type { AnswerScore } from "../game";
import type { QuizAnswer, QuizQuestion } from "../types";
import { CardActions } from "./CardActions";
import { CardFrame } from "./CardFrame";
import { Doubts } from "./Doubts";
import { PointsPop } from "./PointsPop";
import { QuizSourceCheck } from "./SourceCheckPanel";
import { SourcesList } from "./SourcesList";

type AnswerState =
  | { kind: "unanswered" }
  | { kind: "checking"; picked: number }
  | { kind: "answered"; picked: number; answer: QuizAnswer; score: AnswerScore | null }
  | { kind: "failed"; picked: number };

interface QuizCardProps {
  question: QuizQuestion;
  /** Unlocks the answer to a question from the player's own live run. */
  revealToken?: string | undefined;
  /** Called once per answer with the seconds taken; returns the points it earned, if scored. */
  onAnswered: (correct: boolean, seconds: number) => AnswerScore | null;
  nextLabel: string;
  onNext: () => void;
}

/** One question: pick an option, then see the answer, the explanation and its sources. */
export function QuizCard({ question, revealToken, onAnswered, nextLabel, onNext }: QuizCardProps) {
  const [state, setState] = useState<AnswerState>({ kind: "unanswered" });
  const shownAt = useRef(performance.now());

  // A new question starts unanswered, and its answer time counts from now.
  useEffect(() => {
    setState({ kind: "unanswered" });
    shownAt.current = performance.now();
  }, [question.id]);

  async function pick(index: number) {
    if (state.kind !== "unanswered" && state.kind !== "failed") {
      return;
    }
    const seconds = (performance.now() - shownAt.current) / 1000;
    setState({ kind: "checking", picked: index });
    try {
      const answer = await fetchAnswer(question.id, revealToken);
      const score = onAnswered(index === answer.correct_index, seconds);
      setState({ kind: "answered", picked: index, answer, score });
    } catch {
      setState({ kind: "failed", picked: index });
    }
  }

  const answer = state.kind === "answered" ? state.answer : undefined;
  const score = state.kind === "answered" ? state.score : null;
  const picked = state.kind === "unanswered" ? undefined : state.picked;

  function optionStyle(index: number): string {
    if (!answer) {
      return index === picked
        ? "border-teal/60 bg-white/5"
        : "border-white/10 hover:border-white/30 hover:bg-white/[0.03]";
    }
    if (index === answer.correct_index) {
      return "border-teal bg-teal/10";
    }
    if (index === picked) {
      return "border-rust bg-rust/10";
    }
    return "border-white/5 opacity-60";
  }

  return (
    <CardFrame
      mode="quiz"
      difficulty={question.difficulty}
      topic={question.topic}
      status={question.status}
    >
      <p className="mt-4 text-xl leading-relaxed font-medium">{question.question}</p>

      <ol className="mt-6 space-y-3">
        {question.options.map((option, index) => (
          <li key={option}>
            <button
              type="button"
              onClick={() => void pick(index)}
              disabled={state.kind === "checking" || state.kind === "answered"}
              aria-pressed={index === picked}
              className={`flex w-full items-start gap-4 rounded-lg border px-4 py-3.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:cursor-default ${optionStyle(index)}`}
            >
              <span className="mt-1 font-pixel text-[9px] text-slate">{"ABCD"[index]}</span>
              <span className="flex-1 text-base text-ink">{option}</span>
              {answer && index === answer.correct_index && (
                <span className="mt-1 font-pixel text-[8px] uppercase text-teal">Answer</span>
              )}
            </button>
          </li>
        ))}
      </ol>

      <div aria-live="polite">
        {state.kind === "checking" && <p className="mt-6 text-sm text-slate">Checking...</p>}
        {state.kind === "failed" && (
          <p role="alert" className="mt-6 text-sm text-rust">
            The answer could not be loaded. Pick again to retry.
          </p>
        )}
        {answer && picked !== undefined && (
          <>
            <p className="mt-6 font-heading text-2xl font-bold">
              {picked === answer.correct_index ? (
                <span className="text-teal">Correct.</span>
              ) : (
                <span>
                  Not quite. The answer is{" "}
                  <span className="text-teal">{"ABCD"[answer.correct_index]}</span>.
                </span>
              )}
            </p>
            {score && <PointsPop score={score} />}
            <p className="mt-4 leading-relaxed text-ink/90">{answer.explanation}</p>
            <Doubts doubts={answer.doubts} />
            <QuizSourceCheck check={answer.source_check} options={question.options} />
            <SourcesList sources={answer.sources} />
            <CardActions
              itemId={question.id}
              nextLabel={nextLabel}
              onNext={onNext}
              canReport={question.status === "published"}
            />
          </>
        )}
      </div>
    </CardFrame>
  );
}
