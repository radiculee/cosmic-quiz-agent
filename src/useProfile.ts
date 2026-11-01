import { useEffect, useSyncExternalStore } from "react";

import {
  accountRemote,
  browserStorage,
  createProfileStore,
  type Profile,
  type ProfileStore,
  type ProfileUpdate,
} from "./profile";
import { ACCOUNTS_ENABLED, session, supabaseProject } from "./session";
import type { Award } from "./trophies";
import { useSession } from "./useSession";

export type { ProfileUpdate };
export type UpdateProfile = (update: ProfileUpdate) => Award[];

function browserStore(): ProfileStore {
  const project = supabaseProject();
  return createProfileStore({
    storage: browserStorage(),
    // With accounts off there is no remote, so nothing is ever sent.
    remote:
      ACCOUNTS_ENABLED && project
        ? accountRemote({
            ...project,
            token: () => session.accessToken(),
            fetch: (input, init) => fetch(input, init),
          })
        : null,
    newId: () => crypto.randomUUID(),
    schedule: (task, ms) => {
      setTimeout(task, ms);
    },
    warn: (message) => console.warn(message),
  });
}

/** The one profile of this page. */
const store = browserStore();

/**
 * The profile shown, with an updater that saves each change and returns what it earned. Updates
 * apply to the latest profile, so several in a row (a live LEARN result counts as a live run and
 * a topic read) never lose one another. A guest's profile is kept in this browser; when a player
 * signs in, it is added to their account and the account's profile is shown instead.
 */
export function useProfile(): [Profile, UpdateProfile] {
  const state = useSession();
  const profile = useSyncExternalStore(store.subscribe, store.profile, store.profile);
  const userId = state.status === "signed-in" ? state.account.id : null;
  const signedOut = state.status === "guest" || state.status === "off";

  useEffect(() => {
    if (userId) {
      void store.signIn(userId);
    } else if (signedOut) {
      store.signOut();
    }
  }, [userId, signedOut]);

  // Coming back online sends what is waiting.
  useEffect(() => {
    if (!userId) {
      return undefined;
    }
    const send = () => void store.flush();
    window.addEventListener("online", send);
    return () => window.removeEventListener("online", send);
  }, [userId]);

  return [profile, store.update];
}
