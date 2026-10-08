import { useCallback, useEffect, useState } from "react";

import { fetchQuota } from "./api";
import type { Quota } from "./types";

export type QuotaState =
  | { kind: "loading" }
  | { kind: "failed" }
  | { kind: "loaded"; quota: Quota };

/**
 * The visitor's live-run quota, with a refresh for after a run. If it cannot be read the page
 * simply does not show it: the server still enforces every limit when a run starts.
 */
export function useQuota(): [QuotaState, () => void] {
  const [state, setState] = useState<QuotaState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    fetchQuota(controller.signal)
      .then((quota) => setState({ kind: "loaded", quota }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error(error);
          setState({ kind: "failed" });
        }
      });
    return () => controller.abort();
  }, [attempt]);

  const refresh = useCallback(() => setAttempt((n) => n + 1), []);
  return [state, refresh];
}
