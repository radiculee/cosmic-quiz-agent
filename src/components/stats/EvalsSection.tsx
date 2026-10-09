import { StatTile, Tiles } from "../../charts/StatTile";
import { Table } from "../../charts/Table";
import { EVAL_HISTORY, FAULT_WORDS } from "../../evals";
import { formatCount, formatDate, formatPercent, formatUsd } from "../../stats";
import { Group } from "./Section";

/**
 * The evals: how the agent and its checks scored on a fixed test set, run by hand on Vedant's
 * machine and built into the page (`python -m evals export`). One closed row: the latest run in
 * full, and every run in a short history as more are made. They are not live, so the filters do
 * not apply.
 */
export function EvalsGroup() {
  const history = EVAL_HISTORY;
  const latest = history?.generation.at(-1);
  if (!history || !latest) {
    return null;
  }
  const faults = latest.seeded.reduce((sum, fault) => sum + fault.items, 0);
  const handled = latest.seeded.reduce((sum, fault) => sum + fault.handled, 0);
  const ontopic = history.ontopic.at(-1);
  const jevVersion = latest.jev_model
    ? `${latest.jev_model}${latest.jev_criteria ? ` (${latest.jev_criteria} criteria)` : ""}`
    : "not run";

  return (
    <Group
      title="Evals"
      hint={
        faults > 0
          ? `${handled} of ${faults} planted faults kept out (${formatDate(latest.at)})`
          : `${latest.layer1_pass} of ${latest.items} items passed the code checks`
      }
    >
      <p className="text-sm leading-relaxed text-slate">
        The latest eval, {formatDate(latest.at)}: {formatCount(latest.items)} items on fixed topics
        with {latest.model}, Jev {jevVersion}, and the {latest.gate_rule.replaceAll("_", " ")} rule.
        Run by hand, not live, so the filters do not apply.
      </p>
      <Tiles>
        <StatTile
          label="Code checks"
          value={formatPercent(latest.layer1_pass, latest.items)}
          note={`${latest.layer1_pass} of ${latest.items} items passed`}
        />
        <StatTile
          label="Unread URLs"
          value={formatCount(latest.unfetched_urls)}
          note="cited in a passing item"
        />
        <StatTile
          label="Faults kept out"
          value={`${handled} of ${faults}`}
          note="planted faults that could not reach a player"
        />
        <StatTile
          label="Published"
          value={formatCount(latest.gate.published ?? 0)}
          note={`of ${latest.verified} that passed the code checks`}
        />
      </Tiles>
      <Table
        caption="Planted faults: which check caught them"
        columns={[
          { label: "Fault" },
          { label: "Items", numeric: true },
          { label: "Code", numeric: true },
          { label: "Haiku", numeric: true },
          { label: "Jev", numeric: true },
          { label: "Kept out", numeric: true },
        ]}
        rows={latest.seeded.map((fault) => [
          FAULT_WORDS[fault.fault] ?? fault.fault,
          fault.items,
          fault.layer1,
          fault.haiku,
          fault.jev,
          fault.handled,
        ])}
        note="Each check runs on every planted item, so each is measured on its own. Kept out means the item was not published, or the bad quote was dropped."
      />
      <Table
        caption="Jev's calibration: answers and wrong options"
        columns={[
          { label: "Confidence" },
          { label: "Claims", numeric: true },
          { label: "Verdict right", numeric: true },
        ]}
        rows={latest.calibration.map((band) => [
          band.band,
          band.claims,
          formatPercent(band.right, band.claims),
        ])}
        note="Well calibrated means each band is right about as often as its confidence says."
      />
      {ontopic && (
        <Table
          caption={`The on-topic check, ${formatDate(ontopic.at)}`}
          columns={[{ label: "Judge" }, { label: "Right", numeric: true }]}
          rows={ontopic.judges.map((judge) => [
            judge.judge === "jev"
              ? "Jev (in use)"
              : judge.judge === "keywords"
                ? "Keyword list"
                : judge.judge,
            `${judge.right} of ${ontopic.inputs}`,
          ])}
          note={`${ontopic.inputs} labelled inputs: ${ontopic.on_topic} topics to research, the rest off topic or instructions in disguise.`}
        />
      )}
      {history.generation.length > 1 && (
        <Table
          caption="Every eval"
          columns={[
            { label: "Date" },
            { label: "Items", numeric: true },
            { label: "Code checks", numeric: true },
            { label: "Faults kept out", numeric: true },
            { label: "Cost", numeric: true },
          ]}
          rows={history.generation.map((run) => {
            const kept = run.seeded.reduce((sum, fault) => sum + fault.handled, 0);
            const planted = run.seeded.reduce((sum, fault) => sum + fault.items, 0);
            return [
              formatDate(run.at),
              run.items,
              formatPercent(run.layer1_pass, run.items),
              planted > 0 ? `${kept} of ${planted}` : "-",
              formatUsd(run.anthropic_usd + run.typesafe_usd),
            ];
          })}
        />
      )}
    </Group>
  );
}
