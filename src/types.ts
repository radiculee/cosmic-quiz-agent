export const DIFFICULTIES = ["easy", "medium", "hard"] as const;
export const MODES = ["learn", "quiz"] as const;
export const VERDICTS = ["supports", "contradicts", "says_nothing"] as const;

export type Difficulty = (typeof DIFFICULTIES)[number];
export type Mode = (typeof MODES)[number];
export type Verdict = (typeof VERDICTS)[number];

/** A topic in the bank and the difficulties with at least one published item, per mode. */
export interface BankTopic {
  name: string;
  kind: "evergreen" | "news";
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
}

export interface QuizAnswer {
  id: number;
  correct_index: number;
  explanation: string;
  sources: Source[];
  source_check: SourceCheck;
}

export interface LearnItem {
  id: number;
  mode: "learn";
  difficulty: Difficulty;
  topic: string;
  explanation: string;
  sources: Source[];
  source_check: SourceCheck;
}

export type Item = QuizQuestion | LearnItem;
