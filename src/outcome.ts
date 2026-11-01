import { madeAnything, summarize, summaryLine, type Search } from "./search";
import type { LogOutcome } from "./components/AgentLog";

/** Shown instead of the usual "could not back it" line when the agent could not be reached. */
export const UNAVAILABLE_MESSAGE =
  "The agent is unavailable just now. This search was not counted. Topics in the bank are still free to play.";

/**
 * How an ended search is reported. `unavailable` is the stream's end event: every run failed
 * before the model answered, so the topic is not to blame. Only a search that made nothing says so.
 */
export function searchOutcome(search: Search, unavailable: boolean): Extract<LogOutcome, { message: string }> {
  if (madeAnything(search)) {
    return { kind: "done", message: summaryLine(summarize(search)) };
  }
  const message = unavailable ? UNAVAILABLE_MESSAGE : summaryLine(summarize(search));
  return { kind: "nothing", message };
}
