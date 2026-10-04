import { useCallback, useEffect, useRef, useState } from "react";

export interface RunClock {
  /** Milliseconds counted so far. */
  elapsed: number;
  running: boolean;
  start: () => void;
  pause: () => void;
  reset: () => void;
}

/**
 * The speedrun clock. It runs only while a question is waiting for an answer, so reading the
 * explanation and sources afterwards never costs time.
 */
export function useRunClock(): RunClock {
  const [counted, setCounted] = useState(0);
  const [since, setSince] = useState<number | null>(null);
  const [now, setNow] = useState(() => performance.now());
  const sinceRef = useRef<number | null>(null);

  useEffect(() => {
    if (since === null) return;
    const timer = window.setInterval(() => setNow(performance.now()), 100);
    return () => window.clearInterval(timer);
  }, [since]);

  const start = useCallback(() => {
    if (sinceRef.current === null) {
      const started = performance.now();
      sinceRef.current = started;
      setSince(started);
      setNow(started);
    }
  }, []);

  const pause = useCallback(() => {
    const started = sinceRef.current;
    if (started !== null) {
      setCounted((total) => total + performance.now() - started);
      sinceRef.current = null;
      setSince(null);
    }
  }, []);

  const reset = useCallback(() => {
    sinceRef.current = null;
    setSince(null);
    setCounted(0);
  }, []);

  const elapsed = counted + (since === null ? 0 : Math.max(0, now - since));
  return { elapsed, running: since !== null, start, pause, reset };
}
