import type { ReactNode } from "react";

import { ApiError } from "../api";
import type { Profile } from "../profile";
import type { Award } from "../trophies";
import type { Difficulty } from "../types";
import type { UpdateProfile } from "../useProfile";
import type { TopicsState } from "../useTopics";

/** What the app shell gives every page (App.tsx). */
export interface PageProps {
  topicsState: TopicsState;
  retryTopics: () => void;
  profile: Profile;
  updateProfile: UpdateProfile;
  /** Show new trophies and rank-ups in the pop-up. */
  celebrate: (awards: readonly Award[]) => void;
  /** Shared by every page, so a level picked on one carries over to the next. */
  difficulty: Difficulty;
  setDifficulty: (difficulty: Difficulty) => void;
}

// The server cleans topics the same way (agent/topic_check.py); this only avoids a wasted call.
export const MIN_TOPIC_CHARS = 2;
export const MAX_TOPIC_CHARS = 80;

/** A page's title and the sentence under it, straight on the scene. */
export function PageHeading({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center pt-8 text-center sm:pt-10">
      <h1 className="on-scene font-heading text-5xl font-bold uppercase tracking-tight">{title}</h1>
      <p className="on-scene-muted mt-4 max-w-lg leading-relaxed">{children}</p>
    </div>
  );
}

/** While the topics load, or after they failed to. Nothing once they are loaded. */
export function TopicsNotice({ state, onRetry }: { state: TopicsState; onRetry: () => void }) {
  if (state.kind === "loading") {
    return <p className="scene-note mx-auto text-center text-sm">Loading topics...</p>;
  }
  if (state.kind === "failed") {
    return (
      <p role="alert" className="scene-note mx-auto text-center text-sm">
        Could not load the topics.{" "}
        <button type="button" onClick={onRetry} className="text-teal underline underline-offset-4">
          Try again
        </button>
      </p>
    );
  }
  return null;
}

/** A failed load, with a retry. */
export function LoadFailed({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <p role="alert" className="scene-note mx-auto text-center text-sm">
      {message}{" "}
      <button type="button" onClick={onRetry} className="text-teal underline underline-offset-4">
        Try again
      </button>
    </p>
  );
}

/** What to tell the player when a question or explanation could not be loaded. */
export function loadError(error: unknown): string {
  if (error instanceof ApiError && error.status === 429) {
    return error.message;
  }
  return error instanceof ApiError && error.status === 404
    ? "There is no item for this topic at these settings yet."
    : "It could not be loaded. Try again in a moment.";
}

/** A small solid chip on the scene: the hero's Your progress and Pause, the footer's Privacy. */
export const SCENE_CHIP =
  "flex items-center gap-2 rounded-sm border border-white/15 bg-surface px-3 py-2 font-pixel text-[8px] uppercase text-ink transition-colors hover:border-white/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal";

// Solid in every state, including disabled and hover: a button on the scene must never let the
// scene show through.
export const PRIMARY_BUTTON =
  "rounded-lg bg-teal font-pixel uppercase text-void transition enabled:hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:bg-[color-mix(in_oklab,var(--color-teal)_35%,var(--color-surface))] disabled:text-void/70";
export const SECONDARY_BUTTON =
  "flex items-center gap-3 rounded-lg border border-white/10 bg-surface font-pixel uppercase text-ink transition-colors hover:border-white/25 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal disabled:text-slate/60";
