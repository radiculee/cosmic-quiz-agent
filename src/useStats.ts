import { useCallback, useEffect, useState } from "react";

import { ApiError, fetchStats } from "./api";
import { type StatsFilters, statsQuery } from "./stats";
import type { StatsReply } from "./types";

/** While new figures load, or after they failed to, the last ones stay on screen (faded), so
 * changing a filter never empties the panel. */
export type StatsState =
  | { kind: "loading"; previous: StatsReply | null }
  | { kind: "loaded"; reply: StatsReply }
  | { kind: "failed"; message: string; previous: StatsReply | null };

// The edge caches each filter set for ten minutes (api/stats.py); the page keeps them as long.
const KEEP_MS = 10 * 60 * 1000;
const kept = new Map<string, { reply: StatsReply; at: number }>();

function fresh(query: string): StatsReply | null {
  const entry = kept.get(query);
  return entry && Date.now() - entry.at < KEEP_MS ? entry.reply : null;
}

function shown(state: StatsState): StatsReply | null {
  return state.kind === "loaded" ? state.reply : state.previous;
}

/** The agent's statistics for `filters`, fetched only while `active` (the tab is open). */
export function useStats(filters: StatsFilters, active: boolean): [StatsState, () => void] {
  const query = statsQuery(filters);
  const [state, setState] = useState<StatsState>(() => {
    const reply = fresh(query);
    return reply ? { kind: "loaded", reply } : { kind: "loading", previous: null };
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!active) {
      return;
    }
    const reply = fresh(query);
    if (reply) {
      setState({ kind: "loaded", reply });
      return;
    }
    const controller = new AbortController();
    setState((current) => ({ kind: "loading", previous: shown(current) }));
    fetchStats(query, controller.signal)
      .then((loaded) => {
        kept.set(query, { reply: loaded, at: Date.now() });
        setState({ kind: "loaded", reply: loaded });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        const message =
          error instanceof ApiError && error.status === 429
            ? error.message
            : "The statistics could not be loaded.";
        setState((current) => ({ kind: "failed", message, previous: shown(current) }));
      });
    return () => controller.abort();
  }, [query, attempt, active]);

  const retry = useCallback(() => setAttempt((count) => count + 1), []);
  return [state, retry];
}
