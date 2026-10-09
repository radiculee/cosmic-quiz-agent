/**
 * The eval history, built into the page: eval results stay on Vedant's machine, and
 * `python -m evals export` writes a summary of each run to src/data/evals.json (decided
 * 2026-10-08). Checked like any other outside data; if it is not in the expected shape the
 * panel leaves the evals out.
 */
import data from "./data/evals.json";
import { isEvalHistory } from "./shapes";
import type { EvalHistory } from "./types";

export const EVAL_HISTORY: EvalHistory | null = isEvalHistory(data) ? data : null;

/** What each kind of planted fault is, in words. */
export const FAULT_WORDS: Record<string, string> = {
  wrong_number: "A wrong number",
  fake_quote: "A quote not on the page",
  unsupported_claim: "A claim the sources do not make",
  true_distractor: "A wrong option that is true",
};
