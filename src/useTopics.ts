import { useCallback, useEffect, useState } from "react";

import { fetchTopics } from "./api";
import type { BankTopic } from "./types";

export type TopicsState =
  | { kind: "loading" }
  | { kind: "failed" }
  | { kind: "loaded"; topics: BankTopic[] };

/** Every bank topic, loaded once for the whole app, with a way to try again after a failure. */
export function useTopics(): [TopicsState, () => void] {
  const [state, setState] = useState<TopicsState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    fetchTopics(controller.signal)
      .then((topics) => setState({ kind: "loaded", topics }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error(error);
          setState({ kind: "failed" });
        }
      });
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return [state, retry];
}

/** The topics, or none while they load or after a failure. */
export function loadedTopics(state: TopicsState): BankTopic[] {
  return state.kind === "loaded" ? state.topics : [];
}
