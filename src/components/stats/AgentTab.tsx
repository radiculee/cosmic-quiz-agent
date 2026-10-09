import { useId, useState } from "react";

import { BarList } from "../../charts/BarList";
import { BarSplit } from "../../charts/BarSplit";
import { Histogram } from "../../charts/Histogram";
import { Meter, MeterBar } from "../../charts/Meter";
import { StatTile, Tiles } from "../../charts/StatTile";
import { Table } from "../../charts/Table";
import { LoadFailed } from "../../pages/common";
import {
  agreement,
  agreementCount,
  ALL_RUNS,
  anthropicUsd,
  bankParts,
  budgetLabel,
  CLAIM_WORDS,
  cacheHitRatio,
  callBins,
  claimRows,
  confidenceBins,
  filterSummary,
  formatCount,
  formatDate,
  formatPercent,
  formatSeconds,
  formatUsd,
  gateParts,
  gridCell,
  gridHint,
  headline,
  JEV_WORDS,
  LEVEL_FILTERS,
  MODE_FILTERS,
  monthName,
  outcomeParts,
  per,
  RANGE_FILTERS,
  reviewReasons,
  SOURCE_FILTERS,
  type StatsFilters,
  tokenTotals,
  topRows,
  VERDICT_WORDS,
  verdictParts,
} from "../../stats";
import {
  DIFFICULTIES,
  LAYER_VERDICTS,
  MODES,
  type Percentiles,
  type StatsReply,
  VERDICTS,
} from "../../types";
import { useStats } from "../../useStats";
import { SegmentedControl } from "../SegmentedControl";
import { EvalsGroup } from "./EvalsSection";
import { Group, Groups } from "./Section";

const TIME = new Intl.DateTimeFormat("en-IE", { hour: "2-digit", minute: "2-digit" });

/** "did not run" as a table heading: "Did not run". */
function sentence(text: string): string {
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}`;
}

function usdOrDash(value: number | null): string {
  return value === null ? "-" : formatUsd(value);
}

function countOrDash(value: number | null): string {
  return value === null ? "-" : formatCount(Math.round(value));
}

// --- Filters -----------------------------------------------------------------------------------

/** One filter: a small label over a compact segmented control. */
function Filter<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <span aria-hidden="true" className="font-pixel text-[8px] uppercase text-slate">
        {label}
      </span>
      <SegmentedControl label={label} options={options} value={value} onChange={onChange} compact />
    </div>
  );
}

/** The filters sit behind one button that names the current choice; open, they scope the four
 * key figures and every group alike, so the numbers always agree. */
function FilterPanel({
  filters,
  onChange,
}: {
  filters: StatsFilters;
  onChange: (filters: StatsFilters) => void;
}) {
  const [open, setOpen] = useState(false);
  const rowsId = useId();
  return (
    <div className="space-y-4">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={rowsId}
        onClick={() => setOpen((shown) => !shown)}
        className="flex items-center gap-3 rounded-lg border border-white/10 bg-surface px-4 py-3 text-left transition-colors hover:border-white/25 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
      >
        <span className="font-pixel text-[8px] uppercase text-slate">Filter</span>
        <span className="text-sm text-ink">{filterSummary(filters)}</span>
        <span
          aria-hidden="true"
          className={`font-pixel text-[8px] text-teal transition-transform motion-reduce:transition-none ${
            open ? "rotate-90" : ""
          }`}
        >
          &gt;
        </span>
      </button>
      <div id={rowsId} hidden={!open} className="flex flex-wrap gap-x-6 gap-y-4">
        <Filter
          label="Mode"
          options={MODE_FILTERS}
          value={filters.mode}
          onChange={(mode) => onChange({ ...filters, mode })}
        />
        <Filter
          label="Level"
          options={LEVEL_FILTERS}
          value={filters.level}
          onChange={(level) => onChange({ ...filters, level })}
        />
        <Filter
          label="Source"
          options={SOURCE_FILTERS}
          value={filters.source}
          onChange={(source) => onChange({ ...filters, source })}
        />
        <Filter
          label="Range"
          options={RANGE_FILTERS}
          value={filters.range}
          onChange={(range) => onChange({ ...filters, range })}
        />
      </div>
    </div>
  );
}

// --- The four key figures ------------------------------------------------------------------------

/** Quality, cost, speed and budget (decided 2026-10-08): what the tab opens on. */
function KeyFigures({ reply }: { reply: StatsReply }) {
  const { stats, caps } = reply;
  const head = headline(stats);
  const spent = stats.budget.anthropic_usd;
  const month = monthName(stats.budget.month_start);
  return (
    <dl className="grid grid-cols-2 gap-3">
      <StatTile
        large
        label="Published"
        value={formatPercent(head.published, head.runs)}
        note={`${formatCount(head.published)} of ${formatCount(head.runs)} runs, by the gate before any review`}
      />
      <StatTile
        large
        label="Per published item"
        value={usdOrDash(head.costPerPublished)}
        note="Anthropic and TypeSafe"
      />
      <StatTile
        large
        label="Median run"
        value={formatSeconds(head.medianRun)}
        note={`Agent and verifiers; p95 ${formatSeconds(stats.speed.total_seconds.p95)}`}
      />
      <StatTile
        large
        label={`${month} spend`}
        value={formatUsd(spent)}
        chart={
          <MeterBar value={spent} cap={caps.anthropic_month_usd} label={`${month} Anthropic spend`} />
        }
        note={`of the ${formatUsd(caps.anthropic_month_usd)} Anthropic limit (${formatPercent(spent, caps.anthropic_month_usd)})`}
      />
    </dl>
  );
}

// --- The groups behind a click -----------------------------------------------------------------------

/** Every mode and level side by side, in the chosen source and range. */
function ModeGrid({ reply }: { reply: StatsReply }) {
  const { stats } = reply;
  return (
    <Table
      caption="Published by the gate, per mode and level"
      columns={[
        { label: "" },
        ...DIFFICULTIES.map((difficulty) => ({ label: difficulty.toUpperCase(), numeric: true })),
      ]}
      rows={MODES.map((mode) => [
        <span key="mode" className="font-pixel text-[8px] uppercase">
          {mode}
        </span>,
        ...DIFFICULTIES.map((difficulty) => {
          const cell = gridCell(stats, mode, difficulty);
          if (!cell) {
            return (
              <span key={difficulty} className="text-slate">
                -
              </span>
            );
          }
          return (
            <span key={difficulty} className="block">
              <span className="block font-heading text-lg font-bold">
                {formatPercent(cell.published, cell.runs)}
              </span>
              <span className="block text-xs text-slate">{formatCount(cell.runs)} runs</span>
              <span className="block text-xs text-slate">
                {usdOrDash(per(cell.anthropic_usd, cell.runs))} a run
              </span>
              <span className="block text-xs text-slate">{formatSeconds(cell.median_seconds)}</span>
            </span>
          );
        }),
      ])}
      note="Published by the gate, then runs, Anthropic cost per run and the median agent time. This grid follows the source and range filters only."
    />
  );
}

function SpendThisMonth({ reply }: { reply: StatsReply }) {
  const { budget } = reply.stats;
  return (
    <div className="space-y-5">
      <Meter
        label="Anthropic: agent and Haiku"
        value={budget.anthropic_usd}
        cap={reply.caps.anthropic_month_usd}
      />
      <Meter label="Live research" value={budget.live_usd} cap={reply.caps.live_month_usd} />
      <p className="text-xs leading-relaxed text-slate">
        TypeSafe (Jev): {formatUsd(budget.typesafe_usd)} this month,{" "}
        {formatUsd(budget.typesafe_all_time_usd)} in all. Only the agent&apos;s stored runs are
        counted: eval and development runs and the on-topic checks are not, so the Anthropic and
        TypeSafe consoles show a little more. The spend does not change with the filters.
      </p>
    </div>
  );
}

function timeRow(label: string, value: Percentiles): [string, string, string] {
  return [label, formatSeconds(value.median), formatSeconds(value.p95)];
}

function VolumeGroup({ reply }: { reply: StatsReply }) {
  const { stats } = reply;
  const { volume } = stats;
  const runs = volume.runs;
  return (
    <Group
      title="Volume, outcomes and cost"
      hint={`${formatCount(runs)} runs, ${formatPercent(volume.outcomes.passed, runs)} answered`}
    >
      <BarSplit title="How the runs ended" parts={outcomeParts(stats)} />
      <BarSplit title="What the publish gate decided" parts={gateParts(volume.gate)} />
      <BarSplit title="Where those items are now" parts={bankParts(stats)} />
      <Tiles>
        <StatTile
          label="Agent per run"
          value={usdOrDash(per(volume.cost.agent_usd, runs))}
          note="Anthropic, research and writing"
        />
        <StatTile
          label="Haiku per run"
          value={usdOrDash(per(volume.cost.verifier_usd, runs))}
          note="Anthropic, the verifier"
        />
        <StatTile
          label="Jev per run"
          value={usdOrDash(per(volume.cost.jev_usd, runs))}
          note="TypeSafe, the second opinion"
        />
        <StatTile
          label="Spent in all"
          value={formatUsd(anthropicUsd(volume.cost) + volume.cost.jev_usd)}
          note={`${formatUsd(volume.cost.jev_usd)} of it on TypeSafe`}
        />
      </Tiles>
    </Group>
  );
}

function TokensGroup({ reply }: { reply: StatsReply }) {
  const { stats, caching } = reply;
  const { speed } = stats;
  const runs = stats.volume.runs;
  const tokens = tokenTotals(stats);
  const prompt = tokens.input + tokens.cacheWrite + tokens.cacheRead;
  return (
    <Group
      title="Tokens, caching and speed"
      hint={`Caching saved ${formatUsd(caching.saved_usd)}; cache hit ${formatPercent(tokens.cacheRead, prompt)}`}
    >
      <p className="text-sm leading-relaxed text-slate">
        Tokens are averages per run. Haiku 4.5 caches only prompts of 4,096 tokens or more, so
        short runs read nothing from the cache.
      </p>
      <Tiles>
        <StatTile label="Input" value={countOrDash(per(tokens.input, runs))} note="uncached" />
        <StatTile label="Cache write" value={countOrDash(per(tokens.cacheWrite, runs))} />
        <StatTile label="Cache read" value={countOrDash(per(tokens.cacheRead, runs))} />
        <StatTile label="Output" value={countOrDash(per(tokens.output, runs))} />
      </Tiles>
      <Tiles>
        <StatTile
          label="Cache hit"
          value={formatPercent(tokens.cacheRead, prompt)}
          note={cacheHitRatio(tokens) === null ? "no prompt tokens" : "of prompt tokens"}
        />
        <StatTile
          label="Caching saved"
          value={formatUsd(caching.saved_usd)}
          note={`${formatUsd(caching.cached_usd)} paid, against ${formatUsd(caching.uncached_usd)} uncached`}
        />
        <StatTile
          label="Haiku tokens"
          value={countOrDash(per(stats.tokens.verifier_input_tokens, runs))}
          note={`in per run; ${countOrDash(per(stats.tokens.verifier_output_tokens, runs))} out`}
        />
        <StatTile
          label="Jev tokens"
          value={countOrDash(per(stats.tokens.jev_input_tokens, runs))}
          note="in per run; output is free"
        />
      </Tiles>
      <Table
        caption="Time"
        columns={[{ label: "" }, { label: "Median", numeric: true }, { label: "p95", numeric: true }]}
        rows={[
          timeRow("Agent run", speed.run_seconds),
          timeRow("Agent and verifiers", speed.total_seconds),
          timeRow("One model call", speed.model_call_seconds),
          timeRow("Haiku verifier", speed.verifier_seconds),
          timeRow("Jev, one item's checks", speed.jev_seconds),
        ]}
      />
    </Group>
  );
}

function BehaviourGroup({ reply }: { reply: StatsReply }) {
  const { stats } = reply;
  const { behaviour, speed } = stats;
  const runs = stats.volume.runs;
  const citations = behaviour.citations;
  const budgetRuns = behaviour.budgets.reduce((sum, entry) => sum + entry.runs, 0);
  const toolCalls = speed.tools.reduce((sum, tool) => sum + tool.calls, 0);
  const toolErrors = speed.tools.reduce((sum, tool) => sum + tool.errors, 0);
  const pages = behaviour.pages_by_domain.reduce((sum, entry) => sum + entry.pages, 0);
  const allCitations = citations.kept + citations.misquoted + citations.unfetched;
  const pagesPerRun = (per(pages, runs) ?? 0).toFixed(1);
  return (
    <Group
      title="Agent behaviour and evidence"
      hint={`${pagesPerRun} pages read a run; ${formatPercent(citations.kept, citations.kept + citations.misquoted)} of quotes word for word`}
    >
      <Histogram
        title="Model calls per run"
        bins={callBins(stats)}
        caption="Model calls in the run"
        note="Each bar is the number of runs that made that many model calls."
      />
      <Tiles>
        <StatTile
          label="Parallel tools"
          value={formatPercent(behaviour.parallel_steps, behaviour.tool_steps)}
          note="of model calls that used tools asked for two or more"
        />
        <StatTile
          label="Nudged"
          value={formatCount(behaviour.nudged_runs)}
          note={`runs; ${formatCount(behaviour.nudges)} nudges in all`}
        />
        <StatTile
          label="Budget ran out"
          value={formatCount(budgetRuns)}
          note={
            budgetRuns === 0
              ? "runs"
              : behaviour.budgets
                  .map((entry) => `${budgetLabel(entry.budget)}: ${entry.runs}`)
                  .join(", ")
          }
        />
        <StatTile
          label="Tool errors"
          value={formatPercent(toolErrors, toolCalls)}
          note={`${formatCount(toolErrors)} of ${formatCount(toolCalls)} calls`}
        />
      </Tiles>
      <Table
        caption="Tool calls"
        columns={[
          { label: "Tool" },
          { label: "Calls", numeric: true },
          { label: "Per run", numeric: true },
          { label: "Errors", numeric: true },
          { label: "Median", numeric: true },
          { label: "p95", numeric: true },
        ]}
        rows={speed.tools.map((tool) => [
          tool.tool,
          formatCount(tool.calls),
          (per(tool.calls, runs) ?? 0).toFixed(1),
          formatCount(tool.errors),
          formatSeconds(tool.median),
          formatSeconds(tool.p95),
        ])}
      />
      <BarList
        title="Pages read, by site"
        rows={topRows(
          behaviour.pages_by_domain.map((entry) => ({ label: entry.domain, value: entry.pages })),
          6,
        )}
        note={`${pagesPerRun} pages per run. A page read twice through a redirect counts once.`}
      />
      <Tiles>
        <StatTile
          label="Citations"
          value={(per(allCitations, behaviour.answers) ?? 0).toFixed(1)}
          note="per answer"
        />
        <StatTile
          label="Word for word"
          value={formatPercent(citations.kept, citations.kept + citations.misquoted)}
          note="of quotes found on their page"
        />
        <StatTile
          label="Dropped"
          value={formatCount(citations.misquoted + citations.unfetched)}
          note={`citations; ${formatCount(citations.unfetched)} not read in the run`}
        />
        <StatTile
          label="Numbers checked"
          value={formatPercent(
            behaviour.answers - behaviour.unsupported_number_answers,
            behaviour.answers,
          )}
          note="of answers had every number on a page read"
        />
      </Tiles>
    </Group>
  );
}

function VerifiersGroup({ reply }: { reply: StatsReply }) {
  const { stats } = reply;
  const { verifiers } = stats;
  const agree = agreement(stats);
  const jevChecks = verifiers.jev_confidence.bins.reduce((sum, count) => sum + count, 0);
  return (
    <Group
      title="Verifiers"
      hint={`Haiku and Jev agree on ${formatPercent(agree.same, agree.total)}`}
    >
      <p className="text-sm leading-relaxed text-slate">
        The verdicts the gate saw when each item was stored. Haiku 4.5 checks the item against its
        quotes; Jev gives a second opinion on each claim.
      </p>
      <BarSplit title="Haiku verifier" parts={verdictParts(verifiers.haiku)} />
      <BarSplit title="Jev" parts={verdictParts(verifiers.jev)} />
      <Table
        caption={`Haiku against Jev: ${formatPercent(agree.same, agree.total)} the same`}
        columns={[
          { label: "Haiku" },
          ...LAYER_VERDICTS.map((verdict) => ({
            label: sentence(VERDICT_WORDS[verdict]),
            numeric: true,
          })),
        ]}
        rows={LAYER_VERDICTS.map((haiku) => [
          sentence(VERDICT_WORDS[haiku]),
          ...LAYER_VERDICTS.map((jev) => {
            const count = agreementCount(stats, haiku, jev);
            return (
              <span key={jev} className={haiku === jev && count > 0 ? "font-bold text-teal" : ""}>
                {formatCount(count)}
              </span>
            );
          }),
        ])}
        note={`Rows are Haiku's verdict, columns Jev's, for the ${formatCount(agree.total)} items both judged. The diagonal is where they agree.`}
      />
      <Table
        caption="Jev's claim checks"
        columns={[
          { label: "Claim" },
          ...VERDICTS.map((verdict) => ({ label: JEV_WORDS[verdict], numeric: true })),
        ]}
        rows={claimRows(stats).map((row) => [
          CLAIM_WORDS[row.kind],
          ...VERDICTS.map((verdict) => formatCount(row.counts[verdict])),
        ])}
        note="A wrong option should be contradicted; a correct answer and the explanation's sentences should be supported."
      />
      <Histogram
        title="Jev's confidence"
        bins={confidenceBins(stats)}
        caption="Confidence, in bins of 0.1"
        note={`${formatCount(verifiers.jev_confidence.exactly_one)} of ${formatCount(jevChecks)} checks were exactly 1.00: the page states the claim outright.`}
      />
      <BarList
        title="Why items went to review"
        rows={reviewReasons(stats)}
        note={`Of ${formatCount(verifiers.review.items)} items the gate sent to review; an item can have more than one reason.`}
      />
    </Group>
  );
}

/** Everything behind a click, in order: the grid, the month's spend, the four groups, and the
 * evals (which are not live, so they show even when the figures cannot load). */
function Rows({ reply }: { reply: StatsReply | null }) {
  return (
    <Groups label="More about the agent">
      {reply && (
        <>
          <Group title="By mode and level" hint={gridHint(reply.stats)}>
            <ModeGrid reply={reply} />
          </Group>
          <Group
            title="Spend this month"
            hint={`Live research ${formatUsd(reply.stats.budget.live_usd)} of ${formatUsd(reply.caps.live_month_usd)}; Jev ${formatUsd(reply.stats.budget.typesafe_usd)}`}
          >
            <SpendThisMonth reply={reply} />
          </Group>
          {reply.stats.volume.runs === 0 ? (
            <p className="border-b border-white/10 py-4 text-sm text-slate">
              No runs match these filters.
            </p>
          ) : (
            <>
              <VolumeGroup reply={reply} />
              <TokensGroup reply={reply} />
              <BehaviourGroup reply={reply} />
              <VerifiersGroup reply={reply} />
            </>
          )}
        </>
      )}
      <EvalsGroup />
    </Groups>
  );
}

function Footnote({ reply }: { reply: StatsReply }) {
  const { stats } = reply;
  const { volume } = stats;
  const span =
    volume.first_run_at && volume.last_run_at
      ? `${formatCount(volume.runs)} runs from ${formatDate(volume.first_run_at)} to ${formatDate(volume.last_run_at)}.`
      : "No runs match these filters.";
  return (
    <p className="text-xs leading-relaxed text-slate">
      {span} Figures as of {TIME.format(new Date(stats.generated_at))}; they refresh every ten
      minutes.
    </p>
  );
}

/**
 * "The agent" tab: four key figures (quality, cost, speed and budget), then everything else in
 * closed rows the reader opens one at a time (decided 2026-10-08). One Filter button scopes it all.
 */
export function AgentTab({ active }: { active: boolean }) {
  const [filters, setFilters] = useState<StatsFilters>(ALL_RUNS);
  const [state, retry] = useStats(filters, active);
  const reply = state.kind === "loaded" ? state.reply : state.previous;
  const loading = state.kind === "loading";

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <FilterPanel filters={filters} onChange={setFilters} />
        <div aria-live="polite" className="text-sm text-slate">
          {loading && "Loading the agent's statistics..."}
          {state.kind === "failed" && <LoadFailed message={state.message} onRetry={retry} />}
        </div>
      </div>
      <div
        aria-busy={loading}
        className={`space-y-8 transition-opacity ${loading && reply ? "opacity-50" : ""}`}
      >
        {reply && <KeyFigures reply={reply} />}
        <Rows reply={reply} />
        {reply && <Footnote reply={reply} />}
      </div>
    </div>
  );
}
