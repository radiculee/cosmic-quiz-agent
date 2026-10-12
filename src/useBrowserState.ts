/**
 * Two things the browser knows that the scenes follow (src/slideshow.ts): whether the visitor
 * prefers reduced motion, and whether the tab is hidden. Both update live.
 */
import { useSyncExternalStore } from "react";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

/** Read once, for a one-off choice such as how to scroll. */
export function prefersReducedMotion(): boolean {
  return window.matchMedia(REDUCED_MOTION).matches;
}

/** How to scroll something into view: smoothly, unless the visitor prefers reduced motion. */
export function scrollBehavior(): ScrollBehavior {
  return prefersReducedMotion() ? "auto" : "smooth";
}

function subscribeToMotion(onChange: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribeToMotion, prefersReducedMotion);
}

function subscribeToVisibility(onChange: () => void): () => void {
  document.addEventListener("visibilitychange", onChange);
  return () => document.removeEventListener("visibilitychange", onChange);
}

/** True while the tab is in the background (or the window is minimised). */
export function usePageHidden(): boolean {
  return useSyncExternalStore(subscribeToVisibility, () => document.hidden);
}
