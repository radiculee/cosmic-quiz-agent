import { BarList } from "../../charts/BarList";
import { StatTile, Tiles } from "../../charts/StatTile";
import { itemLabel, type Search, type SearchRun } from "../../search";
import {
  addCounts,
  cacheHitRatio,
  formatCount,
  formatPercent,
  formatSeconds,
  formatUsd,
  JEV_WORDS,
  madeCounts,
  runPages,
  runSeconds,
  runUsd,
  searchTotals,
  VERDICT_WORDS,
} from "../../stats";
import { type GateStatus, type StepTiming, VERDICTS } from "../../types";
import { Group, Groups } from "./Section";

const STATUS_WORDS: Record<GateStatus, string> = {
  published: "Published",
  review: "In review",
  discarded: "Discarded",
};

function stepLabel(step: StepTiming, index: number): string {
  const number = `${index + 1}.`;
  if (step.kind === "tool") {
    return `${number} ${step.tool ?? "tool"}${step.is_error ? " (failed)" : ""}`;
  }
  if (step.tools_asked === 0) {
    return `${number} model call`;
  }
  return `${number} model call, ${step.tools_asked} tool${step.tools_asked > 1 ? "s" : ""}`;
}

function plural(count: number, word: string): string {
  return `${formatCount(count)} ${word}${count === 1 ? "" : "s"}`;
}

/** One run: a summary line that opens to its steps and figures. */
function RunDetails({ run }: { run: SearchRun }) {
  const { stats } = run;
  const status = stats.status ? STATUS_WORDS[stats.status] : "No answer";
  const tools = Object.entries(stats.tool_calls)
    .sort((a, b) => b[1] - a[1])
    .map(([tool, calls]) => `${tool} ${calls}`)
    .join(", ");
  const checks = VERDICTS.map(
    (verdict) => `${stats.jev_checks[verdict]} ${JEV_WORDS[verdict].toLowerCase()}`,
  ).join(", ");
  return (
    <li>
      <details className="group/run rounded-sm border border-white/10 bg-surface/60">
        <summary className="flex cursor-pointer list-none flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal [&::-webkit-details-marker]:hidden">
          <span
            aria-hidden="true"
            className="inline-block font-pixel text-[8px] text-teal group-open/run:rotate-90"
          >
            &gt;
          </span>
          <span className="font-heading font-bold">{itemLabel(run.key)}</span>
          <span className="font-pixel text-[8px] uppercase text-slate">{status}</span>
          <span className="ml-auto text-sm tabular-nums text-ink/90">
            {plural(stats.model_calls, "call")}, {plural(runPages(stats), "page")},{" "}
            {formatSeconds(runSeconds(stats))}, {formatUsd(runUsd(stats))}
          </span>
        </summary>
        <div className="space-y-6 border-t border-white/10 px-4 py-5">
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="inline text-slate">Tokens: </dt>
              <dd className="inline">
                {formatCount(stats.tokens.input)} in, {formatCount(stats.tokens.cache_read)} from the
                cache, {formatCount(stats.tokens.cache_write)} cached,{" "}
                {formatCount(stats.tokens.output)} out
              </dd>
            </div>
            <div>
              <dt className="inline text-slate">Verifiers: </dt>
              <dd className="inline">
                Haiku {stats.haiku ? VERDICT_WORDS[stats.haiku] : "not run"}, Jev{" "}
                {stats.jev ? VERDICT_WORDS[stats.jev] : "not run"}
              </dd>
            </div>
            <div>
              <dt className="inline text-slate">Tools: </dt>
              <dd className="inline">
                {tools || "none"}
                {stats.tool_errors > 0 ? ` (${stats.tool_errors} failed)` : ""}
              </dd>
            </div>
            <div>
              <dt className="inline text-slate">Citations: </dt>
              <dd className="inline">
                {stats.citations_kept} kept, {stats.citations_dropped} dropped
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="inline text-slate">Jev&apos;s checks: </dt>
              <dd className="inline">{checks}</dd>
            </div>
          </dl>
          <BarList
            title="Steps, in order"
            rows={stats.steps.map((step, index) => ({
              label: stepLabel(step, index),
              value: step.seconds,
            }))}
            format={formatSeconds}
            note={`Then the Haiku verifier (${formatSeconds(stats.seconds.verifier)}) and Jev (${formatSeconds(stats.seconds.jev)}).`}
          />
        </div>
      </details>
    </li>
  );
}

/**
 * "This search": what the agent did for the search just made on the web page. It opens on four
 * key figures (cost, what was made, time and pages read; decided 2026-10-08), and the rest waits
 * in closed rows. Built from the figures each run sends with its result, so it fills in as the
 * runs end.
 */
export function SearchTab({
  search,
  running,
}: {
  search: Search | null;
  running: boolean;
}) {
  const live = search ? search.slots.filter((slot) => slot.source === "live").length : 0;
  if (!search || (search.runs.length === 0 && !running)) {
    return (
      <div className="space-y-4 text-sm leading-relaxed text-ink/90">
        <p>
          {search && live === 0
            ? `The bank already had all of ${search.topic}, so no agent ran for it.`
            : "No live search on this visit yet."}
        </p>
        <p className="text-slate">
          Search for a new topic on the web page, then open this tab to see what each run of the
          agent did: its model calls, tools, pages, tokens, time and cost.
        </p>
      </div>
    );
  }

  const runs = search.runs;
  const totals = searchTotals(runs.map((run) => run.stats));
  const made = madeCounts(search);
  const prompt = totals.tokens.input + totals.tokens.cacheWrite + totals.tokens.cacheRead;
  const madeNote = [
    made.review > 0 ? `${made.review} in review` : null,
    made.leftOut > 0 ? `${made.leftOut} left out` : null,
    running ? "still running" : null,
  ]
    .filter((part) => part !== null)
    .join(", ");
  const sites = totals.pagesByDomain;
  const toolRows = addCounts(runs.map((run) => run.stats.tool_calls));

  return (
    <div className="space-y-8">
      <div>
        <h3 className="font-heading text-2xl font-bold">{search.topic}</h3>
        <p className="mt-2 font-pixel text-[8px] uppercase text-slate">
          {running ? "still running" : `${runs.length} of ${live} runs reported`}
        </p>
      </div>
      {runs.length === 0 ? (
        <p className="text-sm text-slate">The first run is still going.</p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-3">
            <StatTile
              large
              label="Cost"
              value={formatUsd(totals.anthropicUsd + totals.typesafeUsd)}
              note={`${formatUsd(totals.typesafeUsd)} of it on Jev`}
            />
            <StatTile
              large
              label="Made"
              value={`${made.made} of ${made.planned}`}
              note={madeNote || "every item it set out to make"}
            />
            <StatTile
              large
              label="Time"
              value={formatSeconds(totals.seconds)}
              note="the runs' own time, agent and verifiers"
            />
            <StatTile
              large
              label="Pages read"
              value={formatCount(totals.pages)}
              note={`from ${plural(sites.length, "site")}`}
            />
          </dl>
          <Groups label="More about this search">
            <Group
              title="Run by run"
              hint={`${plural(runs.length, "run")}, ${plural(totals.modelCalls, "model call")}`}
            >
              <ul className="space-y-2">
                {runs.map((run) => (
                  <RunDetails key={run.key} run={run} />
                ))}
              </ul>
            </Group>
            <Group
              title="Tokens"
              hint={`${formatCount(totals.tokens.input)} in, ${formatCount(totals.tokens.output)} out; cache hit ${formatPercent(totals.tokens.cacheRead, prompt)}`}
            >
              <Tiles>
                <StatTile
                  label="Input"
                  value={formatCount(totals.tokens.input)}
                  note="tokens, uncached"
                />
                <StatTile label="Cache read" value={formatCount(totals.tokens.cacheRead)} />
                <StatTile label="Cache write" value={formatCount(totals.tokens.cacheWrite)} />
                <StatTile
                  label="Output"
                  value={formatCount(totals.tokens.output)}
                  note={
                    cacheHitRatio(totals.tokens) === null
                      ? undefined
                      : `cache hit ${formatPercent(totals.tokens.cacheRead, prompt)}`
                  }
                />
              </Tiles>
            </Group>
            <Group
              title="Pages by site"
              hint={sites[0] ? `Most from ${sites[0].label}` : "No pages read"}
            >
              <BarList title="Pages read, by site" rows={sites} />
            </Group>
            <Group
              title="Tool calls"
              hint={`${plural(totals.toolCalls, "call")}${totals.toolErrors > 0 ? `, ${totals.toolErrors} failed` : ""}`}
            >
              <BarList title="Tool calls" rows={toolRows} />
            </Group>
            <Group
              title="Jev's checks"
              hint={`${plural(totals.jevChecks, "claim")}, ${formatCount(totals.jev.supports)} supported`}
            >
              <p className="text-sm leading-relaxed text-ink/90">
                Jev checked {formatCount(totals.jevChecks)} claims:{" "}
                {VERDICTS.map(
                  (verdict) => `${totals.jev[verdict]} ${JEV_WORDS[verdict].toLowerCase()}`,
                ).join(", ")}
                . A wrong option is meant to be contradicted, so contradictions are expected for
                every question.
              </p>
            </Group>
          </Groups>
        </>
      )}
      <p className="text-xs leading-relaxed text-slate">
        Items the bank already had cost nothing and have no run. The on-topic check before the
        first run (one Jev request, about $0.00002) is not counted here. Nothing on this tab names
        a question&apos;s answer.
      </p>
    </div>
  );
}
