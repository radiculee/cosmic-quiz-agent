import type { MouseEvent } from "react";

import { ModeCard } from "../components/ModeCard";
import { ProfileStrip } from "../components/ProfileStrip";
import { quotaShort } from "../quota";
import { PATHS, usePageTitle } from "../router";
import { prefersReducedMotion } from "../useBrowserState";
import { loadedTopics } from "../useTopics";
import { useQuota } from "../useQuota";
import { type PageProps, SCENE_CHIP } from "./common";

/** The slideshow's pause control, for the hero. Null when it does not rotate (reduced motion). */
export interface SlideshowControl {
  paused: boolean;
  onToggle: () => void;
}

const PROGRESS_ID = "progress";

/**
 * The front page. The first screen is a hero over the scene slideshow: the title, the tagline and
 * the three ways in (Learn, Quiz, and a new topic from the web with the searches left today) sit in
 * the scene's empty sky, with a link down to the player's progress and the slideshow's pause
 * control at its foot. Just below the fold, one solid card holds the rank, points, trophy shelf
 * and the bank's size.
 */
export function HomePage({
  topicsState,
  profile,
  slideshow,
}: Pick<PageProps, "topicsState" | "profile"> & { slideshow: SlideshowControl | null }) {
  usePageTitle(null);
  const [quota] = useQuota();
  const topics = loadedTopics(topicsState);
  const learnTopics = topics.filter((topic) => topic.learn.length > 0);
  const learned = new Set(profile.learned);
  const read = learnTopics.filter((topic) => learned.has(topic.name)).length;
  const loaded = topicsState.kind === "loaded";

  function toProgress(event: MouseEvent<HTMLAnchorElement>) {
    const target = document.getElementById(PROGRESS_ID);
    if (!target) {
      return;
    }
    event.preventDefault();
    target.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
    target.focus({ preventScroll: true });
  }

  return (
    <div className="flex flex-col items-center">
      <section
        aria-label="Cosmic Quiz"
        className="relative flex min-h-[calc(100dvh-3.5rem)] w-full flex-col items-center pt-2 pb-24 sm:pt-4"
      >
        <h1 className="on-scene text-center font-heading text-5xl font-bold uppercase tracking-tight sm:text-6xl xl:text-7xl">
          Cosmic Quiz
        </h1>
        <p className="on-scene-muted mt-4 max-w-xl text-center text-base leading-relaxed sm:text-lg">
          An AI agent reads NASA, ESA and Wikipedia, writes the questions, and checks every answer
          against the pages it read.
        </p>

        <nav aria-label="Ways in" className="mt-7 grid w-full grid-cols-1 gap-3 sm:grid-cols-3">
          <ModeCard
            to={PATHS.learn}
            label="Learn"
            title="Read a topic"
            status={loaded ? `${read} of ${learnTopics.length} read` : null}
          />
          <ModeCard
            to={PATHS.quiz}
            label="Quiz"
            title="Play a run"
            status={profile.bestStreak > 0 ? `Best streak ${profile.bestStreak}` : "Not played yet"}
          />
          <ModeCard
            to={PATHS.explore}
            label="Web"
            title="Try a new topic"
            status={quota.kind === "loaded" ? quotaShort(quota.quota) : null}
            accent
          />
        </nav>

        <div className="absolute inset-x-0 bottom-5 flex items-center justify-between gap-4">
          <a href={`#${PROGRESS_ID}`} onClick={toProgress} className={SCENE_CHIP}>
            <svg viewBox="0 0 10 6" width="10" height="6" fill="currentColor" aria-hidden="true">
              <path d="M0 0h2v2H0zM2 2h2v2H2zM4 4h2v2H4zM6 2h2v2H6zM8 0h2v2H8z" />
            </svg>
            Your progress
          </a>
          {slideshow && (
            <button
              type="button"
              onClick={slideshow.onToggle}
              aria-label={slideshow.paused ? "Play the background slideshow" : "Pause the background slideshow"}
              className={SCENE_CHIP}
            >
              <svg viewBox="0 0 8 8" width="8" height="8" fill="currentColor" aria-hidden="true">
                <path d={slideshow.paused ? "M1 0h2v8H1zM3 1h2v6H3zM5 2h2v4H5zM7 3h1v2H7z" : "M1 0h2v8H1zM5 0h2v8H5z"} />
              </svg>
              {slideshow.paused ? "Play" : "Pause"}
            </button>
          )}
        </div>
      </section>

      <div
        id={PROGRESS_ID}
        tabIndex={-1}
        className="pixel-border w-full scroll-mt-6 rounded-sm bg-surface px-5 py-5 focus:outline-none sm:px-6 sm:py-6"
      >
        <ProfileStrip profile={profile} shelf />
        {loaded && (
          <p className="mt-6 border-t border-white/10 pt-4 text-center text-xs text-slate">
            {topics.length} topics in the bank. Every answer is checked against the pages the agent
            read.
          </p>
        )}
      </div>
    </div>
  );
}
