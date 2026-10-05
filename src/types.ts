export const DIFFICULTIES = ["easy", "medium", "hard"] as const;
export const MODES = ["learn", "quiz"] as const;
export const VERDICTS = ["supports", "contradicts", "says_nothing"] as const;

export type Difficulty = (typeof DIFFICULTIES)[number];
export type Mode = (typeof MODES)[number];
export type Verdict = (typeof VERDICTS)[number];
/** "review" items come only from the player's own live run and are labelled as not verified. */
export type ShownStatus = "published" | "review";

/** A topic in the bank and the difficulties with at least one published item, per mode. */
export interface BankTopic {
  name: string;
  kind: "evergreen" | "news" | "custom";
  learn: Difficulty[];
  quiz: Difficulty[];
}

/** A page the agent read in its run, with the passage it quoted. */
export interface Source {
  url: string;
  site: string;
  quote: string;
}

/** What Jev found the cited pages say about one answer option. */
export interface OptionCheck {
  option: number;
  verdict: Verdict;
  confidence: number;
}

/** Jev's second opinion. It reports what the sources support, not whether a claim is true. */
export interface SourceCheck {
  options: OptionCheck[];
  sentences: number;
  sentences_supported: number;
}

export interface QuizQuestion {
  id: number;
  mode: "quiz";
  difficulty: Difficulty;
  topic: string;
  question: string;
  options: string[];
  status: ShownStatus;
}

export interface QuizAnswer {
  id: number;
  correct_index: number;
  explanation: string;
  sources: Source[];
  source_check: SourceCheck;
  /** Why the checks held a live item back; sent with the answer so it cannot spoil it. */
  doubts: string[];
}

export interface LearnItem {
  id: number;
  mode: "learn";
  difficulty: Difficulty;
  topic: string;
  explanation: string;
  sources: Source[];
  source_check: SourceCheck;
  status: ShownStatus;
  doubts: string[];
}

export type Item = QuizQuestion | LearnItem;

/** A quiz question from a live run, with the token that unlocks its answer. */
export interface LiveQuestion {
  question: QuizQuestion;
  revealToken: string;
}

export type Tone = "info" | "ok" | "warn";

/** Events streamed by /api/research (agent/ondemand.py). */
export type ResearchEvent =
  | {
      type: "log";
      label: string;
      detail: string;
      tone: Tone;
      verdict: Verdict | null;
      confidence: number | null;
      seconds: number;
    }
  | { type: "rejected"; message: string }
  | {
      type: "fallback";
      reason: "in_bank" | "limit" | "unavailable" | "discarded";
      message: string;
      topic: string | null;
    }
  | { type: "result"; item: Item; reveal_token: string | null }
  | { type: "error"; message: string };
