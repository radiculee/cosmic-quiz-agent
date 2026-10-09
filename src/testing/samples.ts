/**
 * Sample analytics data for the unit tests: a /api/stats reply and a live run's figures, in the
 * shapes api/stats.py and agent/run_stats.py send (tests/test_stats.py has the Python twin).
 * Only tests import this.
 */
import type { RunStats, StatsReply } from "../types";

export function sampleReply(): StatsReply {
  return {
    stats: {
      filters: { mode: null, difficulty: null, source: null, days: null },
      generated_at: "2026-10-08T20:00:00+00:00",
      volume: {
        runs: 4,
        first_run_at: "2026-10-02T12:00:00+00:00",
        last_run_at: "2026-10-08T12:00:00+00:00",
        outcomes: { passed: 3, failed_checks: 1, no_answer: 0, budget_exceeded: 0, llm_error: 0 },
        gate: { published: 2, review: 1, discarded: 1 },
        cost: { agent_usd: 0.08, verifier_usd: 0.016, jev_usd: 0.0004 },
      },
      bank: { published: 3, review: 0, discarded: 1, retired: 0 },
      tokens: {
        by_model: [
          {
            model: "claude-haiku-4-5",
            runs: 4,
            input_tokens: 1000,
            output_tokens: 100,
            cache_write_tokens: 1000,
            cache_read_tokens: 8000,
            agent_usd: 0.08,
          },
        ],
        verifier_input_tokens: 12000,
        verifier_output_tokens: 800,
        jev_input_tokens: 8000,
      },
      speed: {
        run_seconds: { median: 15, p95: 30 },
        total_seconds: { median: 20, p95: 36 },
        model_call_seconds: { median: 2, p95: 6 },
        verifier_seconds: { median: 3, p95: 5 },
        jev_seconds: { median: 0.3, p95: 0.5 },
        tools: [
          { tool: "fetch_page", calls: 6, errors: 1, median: 0.4, p95: 1.2 },
          { tool: "search_wikipedia", calls: 4, errors: 0, median: 0.3, p95: 0.6 },
        ],
      },
      behaviour: {
        model_calls: [
          { calls: 3, runs: 2 },
          { calls: 5, runs: 2 },
        ],
        model_steps: 16,
        tool_steps: 12,
        parallel_steps: 3,
        pages_by_domain: [
          { domain: "en.wikipedia.org", pages: 6 },
          { domain: "arxiv.org", pages: 2 },
        ],
        nudges: 1,
        nudged_runs: 1,
        budgets: [],
        answers: 4,
        citations: { kept: 9, misquoted: 1, unfetched: 0 },
        unsupported_number_answers: 1,
      },
      verifiers: {
        haiku: { pass: 2, borderline: 1, fail: 0, error: 0 },
        jev: { pass: 3, borderline: 0, fail: 0, error: 0 },
        agreement: [
          { haiku: "borderline", jev: "pass", items: 1 },
          { haiku: "pass", jev: "pass", items: 2 },
        ],
        jev_claims: [
          { kind: "correct_answer", verdict: "supports", checks: 2 },
          { kind: "distractor", verdict: "contradicts", checks: 5 },
          { kind: "distractor", verdict: "says_nothing", checks: 1 },
          { kind: "sentence", verdict: "supports", checks: 12 },
        ],
        jev_confidence: { bins: [1, 0, 0, 0, 0, 0, 0, 1, 2, 16], exactly_one: 11 },
        review: {
          items: 1,
          haiku_doubt: 1,
          jev_doubt: 0,
          verifier_error: 0,
          explanation: 1,
          unsettled_option: 0,
          verifier_quote: 0,
        },
      },
      grid: [
        {
          mode: "learn",
          difficulty: "easy",
          runs: 2,
          published: 1,
          anthropic_usd: 0.05,
          jev_usd: 0.0002,
          median_seconds: 15,
        },
      ],
      budget: {
        month_start: "2026-10-01T00:00:00+00:00",
        anthropic_usd: 5.33,
        typesafe_usd: 0.0026,
        typesafe_all_time_usd: 0.044,
        live_usd: 0.21,
      },
    },
    caching: { uncached_usd: 0.0105, cached_usd: 0.00355, saved_usd: 0.00695, unpriced_runs: 0 },
    caps: { anthropic_month_usd: 10, live_month_usd: 4 },
  };
}

export function sampleRun(change: Partial<RunStats> = {}): RunStats {
  return {
    mode: "quiz",
    difficulty: "medium",
    model: "claude-haiku-4-5",
    outcome: "passed",
    status: "published",
    model_calls: 3,
    nudges: 0,
    tokens: {
      input: 5000,
      output: 400,
      cache_write: 0,
      cache_read: 900,
      verifier_input: 3000,
      verifier_output: 200,
      jev_input: 2000,
    },
    cost: { agent_usd: 0.021, verifier_usd: 0.004, jev_usd: 0.0001 },
    seconds: { agent: 14.2, verifier: 3.1, jev: 0.3 },
    tool_calls: { search_wikipedia: 1, fetch_page: 2 },
    tool_errors: 1,
    pages_by_domain: { "en.wikipedia.org": 1, "nasa.gov": 1 },
    citations_kept: 1,
    citations_dropped: 1,
    haiku: "pass",
    jev: "pass",
    jev_checks: { supports: 6, contradicts: 3, says_nothing: 1 },
    steps: [
      { kind: "model", tool: null, seconds: 1.5, tools_asked: 2, is_error: false },
      { kind: "tool", tool: "search_wikipedia", seconds: 0.4, tools_asked: 0, is_error: false },
      { kind: "tool", tool: "fetch_page", seconds: 0.8, tools_asked: 0, is_error: true },
    ],
    ...change,
  };
}
