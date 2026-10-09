/**
 * Analytics for nerds (docs/PLAN.md Session 9): the figures the panel shows, worked out from the
 * agent's statistics (/api/stats, api/stats.py) and from a live search's runs (the `stats`
 * events of /api/research). Pure functions over plain data, so they are tested without a browser.
 */
import type { Search } from "./search";
import {
  type AgentStats,
  type ClaimKind,
  DIFFICULTIES,
  type Difficulty,
  type GateStatus,
  type LayerVerdict,
  type Mode,
  MODES,
  type Outcome,
  type RunStats,
  type Verdict,
} from "./types";

// --- Filters -----------------------------------------------------------------------------------

export const MODE_FILTERS = ["all", "learn", "quiz"] as const;
export const LEVEL_FILTERS = ["all", "easy", "medium", "hard"] as const;
/** "live" is the web page's searches (the database calls them on_demand). */
export const SOURCE_FILTERS = ["all", "curator", "live"] as const;
export const RANGE_FILTERS = ["7d", "30d", "all"] as const;

export interface StatsFilters {
  mode: (typeof MODE_FILTERS)[number];
  level: (typeof LEVEL_FILTERS)[number];
  source: (typeof SOURCE_FILTERS)[number];
  range: (typeof RANGE_FILTERS)[number];
}

/** Every run, all time: what the panel opens on (decided 2026-10-08). */
export const ALL_RUNS: StatsFilters = { mode: "all", level: "all", source: "all", range: "all" };

/** The query for /api/stats, in a fixed order so each filter set is one edge-cache entry. */
export function statsQuery(filters: StatsFilters): string {
  const query = new URLSearchParams();
  if (filters.mode !== "all") {
    query.set("mode", filters.mode);
  }
  if (filters.level !== "all") {
    query.set("difficulty", filters.level);
  }
  if (filters.source !== "all") {
    query.set("source", filters.source === "live" ? "on_demand" : filters.source);
  }
  if (filters.range !== "all") {
    query.set("days", filters.range === "7d" ? "7" : "30");
  }
  return query.toString();
}

/** The Filter button's words for the current choice: "All runs, all time", or for example
 * "Quiz, hard, live runs, last 7 days". */
export function filterSummary(filters: StatsFilters): string {
  const subject = [filters.mode, filters.level, filters.source].filter((word) => word !== "all");
  const runs = subject.length > 0 ? `${subject.join(", ")} runs` : "all runs";
  const period = { "7d": "last 7 days", "30d": "last 30 days", all: "all time" }[filters.range];
  const text = `${runs}, ${period}`;
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}`;
}

// --- Formatting --------------------------------------------------------------------------------

const WHOLE = new Intl.NumberFormat("en-IE", { maximumFractionDigits: 0 });
const ONE_DECIMAL = new Intl.NumberFormat("en-IE", { maximumFractionDigits: 1 });

/** 1,284, then 12.9K and 1.2M for big counts. */
export function formatCount(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return `${ONE_DECIMAL.format(value / 1_000_000)}M`;
  }
  if (Math.abs(value) >= 10_000) {
    return `${ONE_DECIMAL.format(value / 1_000)}K`;
  }
  return WHOLE.format(value);
}

/** Dollars with enough digits to mean something: $5.33, $0.054, $0.0026. */
export function formatUsd(value: number): string {
  const sign = value < 0 ? "-" : "";
  const amount = Math.abs(value);
  if (amount === 0) {
    return "$0";
  }
  if (amount >= 1) {
    return `${sign}$${amount.toFixed(2)}`;
  }
  if (amount >= 0.01) {
    return `${sign}$${amount.toFixed(3)}`;
  }
  return `${sign}$${amount.toPrecision(2)}`;
}

/** "2.1 s", "15.4 s", "123 s"; a dash when there was nothing to measure. */
export function formatSeconds(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return value >= 100 ? `${WHOLE.format(value)} s` : `${value.toFixed(1)} s`;
}

/** part / whole, or null when there is nothing to divide by. */
export function share(part: number, whole: number): number | null {
  return whole > 0 ? part / whole : null;
}

/** "51%", "<1%" for a small non-zero share, and a dash when there is no whole. */
export function formatPercent(part: number, whole: number): string {
  const value = share(part, whole);
  if (value === null) {
    return "-";
  }
  const rounded = Math.round(value * 100);
  return rounded === 0 && part > 0 ? "<1%" : `${rounded}%`;
}

/** A month in words, from the month's first instant in UTC ("October"). */
export function monthName(iso: string): string {
  return new Date(iso).toLocaleString("en-IE", { month: "long", timeZone: "UTC" });
}

/** A date in words ("1 Oct 2026"). */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IE", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

// --- Words for the values ------------------------------------------------------------------------

/** How a split's parts are coloured: by what they mean, never by their rank. */
export type PartTone = "good" | "doubt" | "bad" | "neutral";

export interface Part {
  label: string;
  value: number;
  tone: PartTone;
}

const OUTCOME_PARTS: [Outcome, string, PartTone][] = [
  ["passed", "Answered", "good"],
  ["budget_exceeded", "Budget ran out", "doubt"],
  ["failed_checks", "Failed the code checks", "bad"],
  ["no_answer", "No answer", "neutral"],
  ["llm_error", "Model error", "neutral"],
];

const GATE_PARTS: [GateStatus, string, PartTone][] = [
  ["published", "Published", "good"],
  ["review", "Review", "doubt"],
  ["discarded", "Discarded", "bad"],
];

const VERDICT_PARTS: [LayerVerdict, string, PartTone][] = [
  ["pass", "Pass", "good"],
  ["borderline", "Doubt", "doubt"],
  ["fail", "Fail", "bad"],
  ["error", "Did not run", "neutral"],
];

export const VERDICT_WORDS: Record<LayerVerdict, string> = {
  pass: "pass",
  borderline: "doubt",
  fail: "fail",
  error: "did not run",
};

export const CLAIM_WORDS: Record<ClaimKind, string> = {
  correct_answer: "Correct answers",
  distractor: "Wrong options",
  sentence: "Explanation sentences",
};

export const JEV_WORDS: Record<Verdict, string> = {
  supports: "Supported",
  contradicts: "Contradicted",
  says_nothing: "Not addressed",
};

function parts<K extends string>(counts: Record<K, number>, order: [K, string, PartTone][]): Part[] {
  return order.map(([key, label, tone]) => ({ label, value: counts[key], tone }));
}

export function outcomeParts(stats: AgentStats): Part[] {
  return parts(stats.volume.outcomes, OUTCOME_PARTS);
}

export function gateParts(counts: Record<GateStatus, number>): Part[] {
  return parts(counts, GATE_PARTS);
}

export function bankParts(stats: AgentStats): Part[] {
  return [
    ...gateParts(stats.bank),
    { label: "Retired", value: stats.bank.retired, tone: "neutral" },
  ];
}

export function verdictParts(counts: Record<LayerVerdict, number>): Part[] {
  return parts(counts, VERDICT_PARTS);
}

// --- The agent tab -------------------------------------------------------------------------------

export function anthropicUsd(cost: { agent_usd: number; verifier_usd: number }): number {
  return cost.agent_usd + cost.verifier_usd;
}

/** A total spread over a count, or null when the count is zero. */
export function per(total: number, count: number): number | null {
  return count > 0 ? total / count : null;
}

export interface Headline {
  runs: number;
  published: number;
  /** Anthropic and TypeSafe together, over the items the gate published. */
  costPerPublished: number | null;
  medianRun: number | null;
}

export function headline(stats: AgentStats): Headline {
  const { volume } = stats;
  const total = anthropicUsd(volume.cost) + volume.cost.jev_usd;
  return {
    runs: volume.runs,
    published: volume.gate.published,
    costPerPublished: per(total, volume.gate.published),
    medianRun: stats.speed.total_seconds.median,
  };
}

export interface TokenTotals {
  input: number;
  output: number;
  cacheWrite: number;
  cacheRead: number;
}

/** The agent loop's tokens, every model together. */
export function tokenTotals(stats: AgentStats): TokenTotals {
  return stats.tokens.by_model.reduce(
    (sum, entry) => ({
      input: sum.input + entry.input_tokens,
      output: sum.output + entry.output_tokens,
      cacheWrite: sum.cacheWrite + entry.cache_write_tokens,
      cacheRead: sum.cacheRead + entry.cache_read_tokens,
    }),
    { input: 0, output: 0, cacheWrite: 0, cacheRead: 0 },
  );
}

/** The share of prompt tokens read from the cache. */
export function cacheHitRatio(tokens: TokenTotals): number | null {
  return share(tokens.cacheRead, tokens.input + tokens.cacheWrite + tokens.cacheRead);
}

export type GridCell = AgentStats["grid"][number];

/** The mode and level the gate published most of, and the one it published least of (null
 * when no cell has runs). The first of equal cells, in grid order, is kept. */
export function gridRange(stats: AgentStats): { high: GridCell; low: GridCell } | null {
  const cells = stats.grid.filter((cell) => cell.runs > 0);
  const first = cells[0];
  if (!first) {
    return null;
  }
  const rate = (cell: GridCell) => cell.published / cell.runs;
  let high = first;
  let low = first;
  for (const cell of cells) {
    if (rate(cell) > rate(high)) {
      high = cell;
    }
    if (rate(cell) < rate(low)) {
      low = cell;
    }
  }
  return { high, low };
}

export function gridCell(
  stats: AgentStats,
  mode: Mode,
  difficulty: Difficulty,
): GridCell | undefined {
  return stats.grid.find((cell) => cell.mode === mode && cell.difficulty === difficulty);
}

/** The grid row's one-line hint: the lowest and highest share published, as the cells show it. */
export function gridHint(stats: AgentStats): string {
  const range = gridRange(stats);
  if (!range) {
    return "No runs yet";
  }
  const name = (cell: GridCell) => `${cell.mode} ${cell.difficulty}`;
  const high = formatPercent(range.high.published, range.high.runs);
  const low = formatPercent(range.low.published, range.low.runs);
  const withRuns = stats.grid.filter((cell) => cell.runs > 0).length;
  if (withRuns === 1) {
    return `Only ${name(range.high)} has runs: ${high} published`;
  }
  if (high === low) {
    const all = withRuns === MODES.length * DIFFICULTIES.length;
    return `${high} published in every cell${all ? "" : " with runs"}`;
  }
  return `From ${low} published (${name(range.low)}) to ${high} (${name(range.high)})`;
}

export interface Row {
  label: string;
  value: number;
}

/** The first `keep` rows, and the rest added up as "Other". */
export function topRows(rows: readonly Row[], keep: number): Row[] {
  if (rows.length <= keep + 1) {
    return [...rows];
  }
  const other = rows.slice(keep).reduce((sum, row) => sum + row.value, 0);
  return [...rows.slice(0, keep), { label: "Other", value: other }];
}

/** Items Haiku and Jev gave the same verdict, out of those both judged. */
export function agreement(stats: AgentStats): { same: number; total: number } {
  return stats.verifiers.agreement.reduce(
    (sum, cell) => ({
      same: sum.same + (cell.haiku === cell.jev ? cell.items : 0),
      total: sum.total + cell.items,
    }),
    { same: 0, total: 0 },
  );
}

export function agreementCount(stats: AgentStats, haiku: LayerVerdict, jev: LayerVerdict): number {
  return (
    stats.verifiers.agreement.find((cell) => cell.haiku === haiku && cell.jev === jev)?.items ?? 0
  );
}

/** Jev's claim checks per kind of claim, with a count per verdict. */
export function claimRows(
  stats: AgentStats,
): { kind: ClaimKind; counts: Record<Verdict, number> }[] {
  const kinds: ClaimKind[] = ["correct_answer", "distractor", "sentence"];
  return kinds.map((kind) => {
    const counts: Record<Verdict, number> = { supports: 0, contradicts: 0, says_nothing: 0 };
    for (const entry of stats.verifiers.jev_claims) {
      if (entry.kind === kind) {
        counts[entry.verdict] += entry.checks;
      }
    }
    return { kind, counts };
  });
}

/** Why the gate sent items to review, most common first; an item can have several reasons. */
export function reviewReasons(stats: AgentStats): Row[] {
  const review = stats.verifiers.review;
  const rows: Row[] = [
    { label: "Haiku doubted the explanation", value: review.explanation },
    { label: "Haiku could not settle a wrong option", value: review.unsettled_option },
    { label: "Haiku's own quote was not on a page", value: review.verifier_quote },
    { label: "Jev's support was below the threshold", value: review.jev_doubt },
    { label: "A verifier did not run", value: review.verifier_error },
  ];
  return rows.filter((row) => row.value > 0).sort((a, b) => b.value - a.value);
}

/** Jev's checks by confidence, labelled by where each bin starts: "0.0" to "0.9" (each 0.1
 * wide; the last also holds 1.0). */
export function confidenceBins(stats: AgentStats): Row[] {
  const bins = stats.verifiers.jev_confidence.bins;
  return bins.map((value, index) => ({ label: (index / bins.length).toFixed(1), value }));
}

/** Runs by how many model calls they made, from the fewest to the most. A count no run made is
 * an empty bin, so the axis has no gaps. */
export function callBins(stats: AgentStats): Row[] {
  const counts = stats.behaviour.model_calls;
  if (counts.length === 0) {
    return [];
  }
  const calls = counts.map((entry) => entry.calls);
  const low = Math.min(...calls);
  const high = Math.max(...calls);
  return Array.from({ length: high - low + 1 }, (_, index) => {
    const n = low + index;
    return { label: String(n), value: counts.find((entry) => entry.calls === n)?.runs ?? 0 };
  });
}

/** "step budget" or "time budget", from agent_stats()'s first word of the budget reason. */
export function budgetLabel(budget: string): string {
  return `${budget.charAt(0).toUpperCase()}${budget.slice(1)} budget`;
}

// --- A live search -------------------------------------------------------------------------------

export interface MadeCounts {
  /** Live items made: published or in review. */
  made: number;
  /** Live items the search planned (the bank's are free and not counted). */
  planned: number;
  review: number;
  /** Discarded, failed or not started. */
  leftOut: number;
}

/** What a search has made so far, out of what it set out to make. */
export function madeCounts(search: Search): MadeCounts {
  const live = search.slots.filter((slot) => slot.source === "live");
  const made = live.filter((slot) => slot.state.kind === "ready");
  return {
    made: made.length,
    planned: live.length,
    review: made.filter((slot) => slot.state.kind === "ready" && slot.state.item.status === "review")
      .length,
    leftOut: live.filter((slot) => slot.state.kind === "missed").length,
  };
}

export interface SearchTotals {
  runs: number;
  modelCalls: number;
  toolCalls: number;
  toolErrors: number;
  pages: number;
  nudges: number;
  jevChecks: number;
  tokens: TokenTotals & { verifierInput: number; verifierOutput: number; jevInput: number };
  anthropicUsd: number;
  typesafeUsd: number;
  /** The runs' own time (agent, Haiku and Jev), not the search's wall-clock time. */
  seconds: number;
  pagesByDomain: Row[];
  jev: Record<Verdict, number>;
}

function sum(values: readonly number[]): number {
  return values.reduce((total, value) => total + value, 0);
}

export function runSeconds(stats: RunStats): number {
  return stats.seconds.agent + stats.seconds.verifier + stats.seconds.jev;
}

export function runPages(stats: RunStats): number {
  return sum(Object.values(stats.pages_by_domain));
}

export function runToolCalls(stats: RunStats): number {
  return sum(Object.values(stats.tool_calls));
}

export function runUsd(stats: RunStats): number {
  return anthropicUsd(stats.cost) + stats.cost.jev_usd;
}

/** Rows from name-to-count maps added together, biggest first (then by name). */
export function addCounts(maps: readonly Record<string, number>[]): Row[] {
  const totals = new Map<string, number>();
  for (const map of maps) {
    for (const [label, value] of Object.entries(map)) {
      totals.set(label, (totals.get(label) ?? 0) + value);
    }
  }
  return [...totals.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
}

export function searchTotals(runs: readonly RunStats[]): SearchTotals {
  return {
    runs: runs.length,
    modelCalls: sum(runs.map((run) => run.model_calls)),
    toolCalls: sum(runs.map(runToolCalls)),
    toolErrors: sum(runs.map((run) => run.tool_errors)),
    pages: sum(runs.map(runPages)),
    nudges: sum(runs.map((run) => run.nudges)),
    jevChecks: sum(
      runs.map((run) => run.jev_checks.supports + run.jev_checks.contradicts + run.jev_checks.says_nothing),
    ),
    tokens: {
      input: sum(runs.map((run) => run.tokens.input)),
      output: sum(runs.map((run) => run.tokens.output)),
      cacheWrite: sum(runs.map((run) => run.tokens.cache_write)),
      cacheRead: sum(runs.map((run) => run.tokens.cache_read)),
      verifierInput: sum(runs.map((run) => run.tokens.verifier_input)),
      verifierOutput: sum(runs.map((run) => run.tokens.verifier_output)),
      jevInput: sum(runs.map((run) => run.tokens.jev_input)),
    },
    anthropicUsd: sum(runs.map((run) => anthropicUsd(run.cost))),
    typesafeUsd: sum(runs.map((run) => run.cost.jev_usd)),
    seconds: sum(runs.map(runSeconds)),
    pagesByDomain: addCounts(runs.map((run) => run.pages_by_domain)),
    jev: {
      supports: sum(runs.map((run) => run.jev_checks.supports)),
      contradicts: sum(runs.map((run) => run.jev_checks.contradicts)),
      says_nothing: sum(runs.map((run) => run.jev_checks.says_nothing)),
    },
  };
}
