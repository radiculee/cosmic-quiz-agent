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

/** Names an item of a live search: "learn-medium", "quiz-easy" and so on. */
export type ItemKey = `${Mode}-${Difficulty}`;

/** One item a live search shows: made live, or already in the bank (free). */
export interface PlannedItem {
  key: ItemKey;
  mode: Mode;
  difficulty: Difficulty;
  source: "live" | "bank";
}

export type Tone = "info" | "ok" | "warn";

// --- Mission Control (Session 9) ----------------------------------------------------------

export const OUTCOMES = [
  "passed",
  "failed_checks",
  "no_answer",
  "budget_exceeded",
  "llm_error",
] as const;
export const GATE_STATUSES = ["published", "review", "discarded"] as const;
export const BANK_STATUSES = ["published", "review", "discarded", "retired"] as const;
export const LAYER_VERDICTS = ["pass", "borderline", "fail", "error"] as const;
export const CLAIM_KINDS = ["correct_answer", "distractor", "sentence"] as const;
export const SOURCES = ["curator", "on_demand"] as const;

/** How an agent run ended (agent/schemas.py). */
export type Outcome = (typeof OUTCOMES)[number];
/** What the publish gate decided for a run's item. */
export type GateStatus = (typeof GATE_STATUSES)[number];
export type BankStatus = (typeof BANK_STATUSES)[number];
/** One verifier layer's verdict on an item. */
export type LayerVerdict = (typeof LAYER_VERDICTS)[number];
export type ClaimKind = (typeof CLAIM_KINDS)[number];
/** Who started a run: the daily Curator, or a player's live search. */
export type RunSource = (typeof SOURCES)[number];

/** One step of a live run: a model call (with how many tools it asked for) or a tool call. */
export interface StepTiming {
  kind: "model" | "tool";
  tool: string | null;
  seconds: number;
  tools_asked: number;
  is_error: boolean;
}

/** What one live run measured (agent/run_stats.py). Numbers only: nothing in it can give a
 * quiz answer away. */
export interface RunStats {
  mode: Mode;
  difficulty: Difficulty;
  model: string;
  outcome: Outcome;
  status: GateStatus | null;
  model_calls: number;
  nudges: number;
  tokens: {
    input: number;
    output: number;
    cache_write: number;
    cache_read: number;
    verifier_input: number;
    verifier_output: number;
    jev_input: number;
  };
  cost: { agent_usd: number; verifier_usd: number; jev_usd: number };
  seconds: { agent: number; verifier: number; jev: number };
  tool_calls: Record<string, number>;
  tool_errors: number;
  pages_by_domain: Record<string, number>;
  citations_kept: number;
  citations_dropped: number;
  haiku: LayerVerdict | null;
  jev: LayerVerdict | null;
  jev_checks: { supports: number; contradicts: number; says_nothing: number };
  steps: StepTiming[];
}

/** A median and 95th percentile; null when there was nothing to measure. */
export interface Percentiles {
  median: number | null;
  p95: number | null;
}

/** The agent's statistics (agent_stats(), supabase/migrations/007_agent_stats.sql). */
export interface AgentStats {
  filters: {
    mode: Mode | null;
    difficulty: Difficulty | null;
    source: RunSource | null;
    days: number | null;
  };
  generated_at: string;
  volume: {
    runs: number;
    first_run_at: string | null;
    last_run_at: string | null;
    outcomes: Record<Outcome, number>;
    /** What the publish gate decided when each run was stored, before any review. */
    gate: Record<GateStatus, number>;
    cost: { agent_usd: number; verifier_usd: number; jev_usd: number };
  };
  /** Where those items are now. */
  bank: Record<BankStatus, number>;
  tokens: {
    by_model: {
      model: string;
      runs: number;
      input_tokens: number;
      output_tokens: number;
      cache_write_tokens: number;
      cache_read_tokens: number;
      agent_usd: number;
    }[];
    verifier_input_tokens: number;
    verifier_output_tokens: number;
    jev_input_tokens: number;
  };
  speed: {
    run_seconds: Percentiles;
    total_seconds: Percentiles;
    model_call_seconds: Percentiles;
    verifier_seconds: Percentiles;
    jev_seconds: Percentiles;
    tools: { tool: string; calls: number; errors: number; median: number | null; p95: number | null }[];
  };
  behaviour: {
    model_calls: { calls: number; runs: number }[];
    model_steps: number;
    tool_steps: number;
    parallel_steps: number;
    pages_by_domain: { domain: string; pages: number }[];
    nudges: number;
    nudged_runs: number;
    budgets: { budget: string; runs: number }[];
    answers: number;
    citations: { kept: number; misquoted: number; unfetched: number };
    unsupported_number_answers: number;
  };
  verifiers: {
    haiku: Record<LayerVerdict, number>;
    jev: Record<LayerVerdict, number>;
    agreement: { haiku: LayerVerdict; jev: LayerVerdict; items: number }[];
    jev_claims: { kind: ClaimKind; verdict: Verdict; checks: number }[];
    jev_confidence: { bins: number[]; exactly_one: number };
    review: {
      items: number;
      haiku_doubt: number;
      jev_doubt: number;
      verifier_error: number;
      explanation: number;
      unsettled_option: number;
      verifier_quote: number;
    };
  };
  grid: {
    mode: Mode;
    difficulty: Difficulty;
    runs: number;
    published: number;
    anthropic_usd: number;
    jev_usd: number;
    median_seconds: number | null;
  }[];
  budget: {
    month_start: string;
    anthropic_usd: number;
    typesafe_usd: number;
    typesafe_all_time_usd: number;
    live_usd: number;
  };
}

/** GET /api/stats (api/stats.py). */
export interface StatsReply {
  stats: AgentStats;
  caching: { uncached_usd: number; cached_usd: number; saved_usd: number; unpriced_runs: number };
  caps: { anthropic_month_usd: number; live_month_usd: number };
}

/** The eval history built into the page (src/data/evals.json, `python -m evals export`). */
export interface EvalHistory {
  generation: {
    run: string;
    at: string;
    size: "full" | "quick";
    model: string;
    jev_model: string | null;
    jev_criteria: string | null;
    gate_rule: string;
    items: number;
    layer1_pass: number;
    by_difficulty: { difficulty: Difficulty; items: number; layer1_pass: number }[];
    unfetched_urls: number;
    verified: number;
    haiku: Partial<Record<LayerVerdict, number>>;
    jev: Partial<Record<LayerVerdict, number>>;
    agreement: number;
    gate: Partial<Record<GateStatus, number>>;
    seeded: {
      fault: string;
      items: number;
      layer1: number;
      haiku: number;
      jev: number;
      handled: number;
    }[];
    calibration: { band: string; claims: number; right: number }[];
    anthropic_usd: number;
    typesafe_usd: number;
  }[];
  ontopic: {
    run: string;
    at: string;
    inputs: number;
    on_topic: number;
    judges: { judge: string; right: number }[];
  }[];
}

/** Events streamed by /api/research (agent/ondemand.py). */
export type ResearchEvent =
  | { type: "plan"; topic: string; items: PlannedItem[] }
  | {
      type: "log";
      /** The item the line is about; null for the search as a whole. */
      key: ItemKey | null;
      label: string;
      detail: string;
      tone: Tone;
      verdict: Verdict | null;
      confidence: number | null;
      seconds: number;
    }
  | { type: "rejected"; message: string }
  | { type: "fallback"; reason: "limit" | "unavailable"; message: string }
  | { type: "result"; key: ItemKey; item: Item; reveal_token: string | null }
  | {
      type: "missed";
      key: ItemKey;
      reason: "discarded" | "failed" | "skipped";
      message: string;
    }
  /** What one run measured, for the analytics panel; sent for discarded runs too. */
  | { type: "stats"; key: ItemKey; stats: RunStats }
  | { type: "error"; message: string };

/** The visitor's live searches left today (GET /api/quota, api/quota.py). */
export interface Quota {
  remaining: number;
  limit: number;
  /** ISO time in UTC when the visitor's daily count starts again. */
  resets_at: string;
  /** Whether the global caps would let a live search start now. */
  global_open: boolean;
}
