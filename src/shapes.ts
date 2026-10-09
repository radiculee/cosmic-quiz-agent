/**
 * The checks for the analytics panel's data: a live run's figures (the `stats` event of
 * /api/research), the agent's statistics (/api/stats) and the bundled eval history. Built from
 * the guards in guards.ts, so each check follows its type in types.ts field by field.
 */
import {
  type Guard,
  isBoolean,
  isNumber,
  isString,
  isTime,
  keyedBy,
  listOf,
  nullable,
  oneOf,
  recordOf,
  shape,
  someKeyedBy,
} from "./guards";
import {
  type AgentStats,
  BANK_STATUSES,
  CLAIM_KINDS,
  DIFFICULTIES,
  type EvalHistory,
  GATE_STATUSES,
  LAYER_VERDICTS,
  MODES,
  OUTCOMES,
  type Percentiles,
  type RunStats,
  SOURCES,
  type StatsReply,
  type StepTiming,
  VERDICTS,
} from "./types";

const isMode = oneOf(MODES);
const isDifficulty = oneOf(DIFFICULTIES);
const isLayerVerdict = oneOf(LAYER_VERDICTS);
const isCount = (value: unknown): value is number => isNumber(value) && value >= 0;

// --- A live run --------------------------------------------------------------------------------

const isStepTiming = shape<StepTiming>({
  kind: oneOf(["model", "tool"] as const),
  tool: nullable(isString),
  seconds: isNumber,
  tools_asked: isCount,
  is_error: isBoolean,
});

export const isRunStats: Guard<RunStats> = shape<RunStats>({
  mode: isMode,
  difficulty: isDifficulty,
  model: isString,
  outcome: oneOf(OUTCOMES),
  status: nullable(oneOf(GATE_STATUSES)),
  model_calls: isCount,
  nudges: isCount,
  tokens: shape<RunStats["tokens"]>({
    input: isCount,
    output: isCount,
    cache_write: isCount,
    cache_read: isCount,
    verifier_input: isCount,
    verifier_output: isCount,
    jev_input: isCount,
  }),
  cost: shape<RunStats["cost"]>({ agent_usd: isCount, verifier_usd: isCount, jev_usd: isCount }),
  seconds: shape<RunStats["seconds"]>({ agent: isCount, verifier: isCount, jev: isCount }),
  tool_calls: recordOf(isCount),
  tool_errors: isCount,
  pages_by_domain: recordOf(isCount),
  citations_kept: isCount,
  citations_dropped: isCount,
  haiku: nullable(isLayerVerdict),
  jev: nullable(isLayerVerdict),
  jev_checks: shape<RunStats["jev_checks"]>({
    supports: isCount,
    contradicts: isCount,
    says_nothing: isCount,
  }),
  steps: listOf(isStepTiming),
});

// --- The agent ---------------------------------------------------------------------------------

/** Jev's confidence comes in ten bins of 0.1 (agent_stats()). */
export const CONFIDENCE_BIN_COUNT = 10;

type Stats = AgentStats;

const isPercentiles = shape<Percentiles>({
  median: nullable(isNumber),
  p95: nullable(isNumber),
});

const isAgentStats = shape<Stats>({
  filters: shape<Stats["filters"]>({
    mode: nullable(isMode),
    difficulty: nullable(isDifficulty),
    source: nullable(oneOf(SOURCES)),
    days: nullable(isCount),
  }),
  generated_at: isTime,
  volume: shape<Stats["volume"]>({
    runs: isCount,
    first_run_at: nullable(isTime),
    last_run_at: nullable(isTime),
    outcomes: keyedBy(OUTCOMES, isCount),
    gate: keyedBy(GATE_STATUSES, isCount),
    cost: shape<Stats["volume"]["cost"]>({
      agent_usd: isCount,
      verifier_usd: isCount,
      jev_usd: isCount,
    }),
  }),
  bank: keyedBy(BANK_STATUSES, isCount),
  tokens: shape<Stats["tokens"]>({
    by_model: listOf(
      shape<Stats["tokens"]["by_model"][number]>({
        model: isString,
        runs: isCount,
        input_tokens: isCount,
        output_tokens: isCount,
        cache_write_tokens: isCount,
        cache_read_tokens: isCount,
        agent_usd: isCount,
      }),
    ),
    verifier_input_tokens: isCount,
    verifier_output_tokens: isCount,
    jev_input_tokens: isCount,
  }),
  speed: shape<Stats["speed"]>({
    run_seconds: isPercentiles,
    total_seconds: isPercentiles,
    model_call_seconds: isPercentiles,
    verifier_seconds: isPercentiles,
    jev_seconds: isPercentiles,
    tools: listOf(
      shape<Stats["speed"]["tools"][number]>({
        tool: isString,
        calls: isCount,
        errors: isCount,
        median: nullable(isNumber),
        p95: nullable(isNumber),
      }),
    ),
  }),
  behaviour: shape<Stats["behaviour"]>({
    model_calls: listOf(shape<{ calls: number; runs: number }>({ calls: isCount, runs: isCount })),
    model_steps: isCount,
    tool_steps: isCount,
    parallel_steps: isCount,
    pages_by_domain: listOf(
      shape<{ domain: string; pages: number }>({ domain: isString, pages: isCount }),
    ),
    nudges: isCount,
    nudged_runs: isCount,
    budgets: listOf(shape<{ budget: string; runs: number }>({ budget: isString, runs: isCount })),
    answers: isCount,
    citations: shape<Stats["behaviour"]["citations"]>({
      kept: isCount,
      misquoted: isCount,
      unfetched: isCount,
    }),
    unsupported_number_answers: isCount,
  }),
  verifiers: shape<Stats["verifiers"]>({
    haiku: keyedBy(LAYER_VERDICTS, isCount),
    jev: keyedBy(LAYER_VERDICTS, isCount),
    agreement: listOf(
      shape<Stats["verifiers"]["agreement"][number]>({
        haiku: isLayerVerdict,
        jev: isLayerVerdict,
        items: isCount,
      }),
    ),
    jev_claims: listOf(
      shape<Stats["verifiers"]["jev_claims"][number]>({
        kind: oneOf(CLAIM_KINDS),
        verdict: oneOf(VERDICTS),
        checks: isCount,
      }),
    ),
    jev_confidence: shape<Stats["verifiers"]["jev_confidence"]>({
      bins: (value): value is number[] =>
        listOf(isCount)(value) && value.length === CONFIDENCE_BIN_COUNT,
      exactly_one: isCount,
    }),
    review: shape<Stats["verifiers"]["review"]>({
      items: isCount,
      haiku_doubt: isCount,
      jev_doubt: isCount,
      verifier_error: isCount,
      explanation: isCount,
      unsettled_option: isCount,
      verifier_quote: isCount,
    }),
  }),
  grid: listOf(
    shape<Stats["grid"][number]>({
      mode: isMode,
      difficulty: isDifficulty,
      runs: isCount,
      published: isCount,
      anthropic_usd: isCount,
      jev_usd: isCount,
      median_seconds: nullable(isNumber),
    }),
  ),
  budget: shape<Stats["budget"]>({
    month_start: isTime,
    anthropic_usd: isCount,
    typesafe_usd: isCount,
    typesafe_all_time_usd: isCount,
    live_usd: isCount,
  }),
});

export const isStatsReply: Guard<StatsReply> = shape<StatsReply>({
  stats: isAgentStats,
  caching: shape<StatsReply["caching"]>({
    uncached_usd: isCount,
    cached_usd: isCount,
    // Negative when cache writes cost more than the reads saved.
    saved_usd: isNumber,
    unpriced_runs: isCount,
  }),
  caps: shape<StatsReply["caps"]>({ anthropic_month_usd: isCount, live_month_usd: isCount }),
});

// --- The eval history ----------------------------------------------------------------------------

type Generation = EvalHistory["generation"][number];
type Ontopic = EvalHistory["ontopic"][number];

export const isEvalHistory: Guard<EvalHistory> = shape<EvalHistory>({
  generation: listOf(
    shape<Generation>({
      run: isString,
      at: isTime,
      size: oneOf(["full", "quick"] as const),
      model: isString,
      jev_model: nullable(isString),
      jev_criteria: nullable(isString),
      gate_rule: isString,
      items: isCount,
      layer1_pass: isCount,
      by_difficulty: listOf(
        shape<Generation["by_difficulty"][number]>({
          difficulty: isDifficulty,
          items: isCount,
          layer1_pass: isCount,
        }),
      ),
      unfetched_urls: isCount,
      verified: isCount,
      haiku: someKeyedBy(LAYER_VERDICTS, isCount),
      jev: someKeyedBy(LAYER_VERDICTS, isCount),
      agreement: isCount,
      gate: someKeyedBy(GATE_STATUSES, isCount),
      seeded: listOf(
        shape<Generation["seeded"][number]>({
          fault: isString,
          items: isCount,
          layer1: isCount,
          haiku: isCount,
          jev: isCount,
          handled: isCount,
        }),
      ),
      calibration: listOf(
        shape<Generation["calibration"][number]>({
          band: isString,
          claims: isCount,
          right: isCount,
        }),
      ),
      anthropic_usd: isCount,
      typesafe_usd: isCount,
    }),
  ),
  ontopic: listOf(
    shape<Ontopic>({
      run: isString,
      at: isTime,
      inputs: isCount,
      on_topic: isCount,
      judges: listOf(
        shape<Ontopic["judges"][number]>({ judge: isString, right: isCount }),
      ),
    }),
  ),
});
