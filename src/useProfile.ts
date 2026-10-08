import { useCallback, useRef, useState } from "react";

import { browserStorage, loadProfile, type Profile, saveProfile } from "./profile";
import type { Award } from "./trophies";

/** One of profile.ts's pure updates: the new profile and what it earned. */
export type ProfileUpdate = (profile: Profile) => [Profile, Award[]];
export type UpdateProfile = (update: ProfileUpdate) => Award[];

/**
 * The saved profile, with an updater that saves each change and returns what it earned. Updates
 * apply to the latest profile, so several in a row (a live LEARN result counts as a live run and
 * a topic read) never lose one another.
 */
export function useProfile(): [Profile, UpdateProfile] {
  const [profile, setProfile] = useState<Profile>(() => loadProfile(browserStorage()));
  const latest = useRef(profile);
  const update = useCallback((change: ProfileUpdate) => {
    const [next, earned] = change(latest.current);
    latest.current = next;
    setProfile(next);
    saveProfile(browserStorage(), next);
    return earned;
  }, []);
  return [profile, update];
}
