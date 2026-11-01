import { useEffect, useSyncExternalStore } from "react";

import { OFF, session, type SessionState } from "./session";

/**
 * The page's sign-in state, kept in step with session.ts. The first use checks a saved session
 * or a return from a sign-in, if there is one; with accounts off it stays "off" and does nothing.
 * A prerendered page has no session, so the server's snapshot is "off" too.
 */
export function useSession(): SessionState {
  const state = useSyncExternalStore(session.subscribe, session.state, () => OFF);
  useEffect(() => {
    session.start();
  }, []);
  return state;
}
