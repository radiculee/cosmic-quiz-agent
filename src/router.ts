/**
 * A small router over the browser's History API (no routing library, DESIGN.md decision 4):
 * which page a path shows, navigation that updates the address bar without a reload, Back and
 * Forward, and the slug that gives each LEARN topic its own address.
 *
 * The rules are pure and the history is passed in (`createHistoryRouter`), so both are unit-tested
 * without a browser (router.test.ts). Vercel serves index.html for every path outside /api
 * (vercel.json), so a shared link opens the right page.
 */
import { useEffect, useSyncExternalStore } from "react";

import type { BankTopic, Difficulty } from "./types";

export type Route =
  | { page: "home" }
  | { page: "learn" }
  | { page: "learn-topic"; slug: string }
  | { page: "quiz" }
  | { page: "explore" }
  /** The analytics panel, over the web page (which stays mounted, so a search keeps going). */
  | { page: "explore-stats" }
  | { page: "trophies" }
  | { page: "not-found" };

export const PATHS = {
  home: "/",
  learn: "/learn",
  quiz: "/quiz",
  explore: "/explore",
  exploreStats: "/explore/stats",
  trophies: "/trophies",
} as const;

const LEARN_PREFIX = "/learn/";

/** The page a path shows. Trailing slashes are ignored; anything unknown is "not-found". */
export function matchRoute(pathname: string): Route {
  let path = pathname;
  while (path.length > 1 && path.endsWith("/")) {
    path = path.slice(0, -1);
  }
  switch (path) {
    case PATHS.home:
      return { page: "home" };
    case PATHS.learn:
      return { page: "learn" };
    case PATHS.quiz:
      return { page: "quiz" };
    case PATHS.explore:
      return { page: "explore" };
    case PATHS.exploreStats:
      return { page: "explore-stats" };
    case PATHS.trophies:
      return { page: "trophies" };
  }
  if (path.startsWith(LEARN_PREFIX)) {
    const slug = safeDecode(path.slice(LEARN_PREFIX.length)).toLowerCase();
    if (slug && !slug.includes("/")) {
      return { page: "learn-topic", slug };
    }
  }
  return { page: "not-found" };
}

function safeDecode(text: string): string {
  try {
    return decodeURIComponent(text);
  } catch {
    return text;
  }
}

// --- Topic slugs ------------------------------------------------------------------------------

const APOSTROPHES = new Set(["'", String.fromCharCode(0x2019)]);

/** Accents are split off by NFKD normalisation as combining marks (U+0300 to U+036F). */
function isCombiningMark(char: string): boolean {
  const code = char.charCodeAt(0);
  return code >= 0x300 && code <= 0x36f;
}

function isSlugChar(char: string): boolean {
  return (char >= "a" && char <= "z") || (char >= "0" && char <= "9");
}

/**
 * A topic's address: lower case, accents dropped, apostrophes removed, and every other run of
 * characters a single hyphen. "Europa's hidden ocean" is "europas-hidden-ocean".
 */
export function topicSlug(name: string): string {
  let slug = "";
  for (const char of name.normalize("NFKD").toLowerCase()) {
    if (isCombiningMark(char) || APOSTROPHES.has(char)) {
      continue;
    }
    if (isSlugChar(char)) {
      slug += char;
    } else if (slug && !slug.endsWith("-")) {
      slug += "-";
    }
  }
  return slug.endsWith("-") ? slug.slice(0, -1) : slug;
}

/** The bank topic a slug names, if any. */
export function topicForSlug(topics: readonly BankTopic[], slug: string): BankTopic | undefined {
  const wanted = slug.toLowerCase();
  return topics.find((topic) => topicSlug(topic.name) === wanted);
}

export function learnTopicPath(name: string): string {
  return LEARN_PREFIX + topicSlug(name);
}

/** The web page with its form filled in (never started: a link must not spend a search). */
export function explorePath(topic: string, difficulty: Difficulty): string {
  const query = new URLSearchParams({ topic, difficulty });
  return `${PATHS.explore}?${query.toString()}`;
}

// --- History ----------------------------------------------------------------------------------

/** The parts of `window` the router uses, so tests can pass a stand-in. */
export interface RouterHost {
  location: Pick<Location, "pathname" | "search" | "hash" | "href" | "origin" | "assign">;
  history: Pick<History, "pushState" | "replaceState">;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
  dispatchEvent(event: Event): boolean;
  scrollTo(x: number, y: number): void;
}

export interface HistoryRouter {
  /** The current path and query, e.g. "/explore?topic=Pulsars". */
  current(): string;
  navigate(to: string, options?: { replace?: boolean }): void;
  /** Call `listener` after every navigation, including Back and Forward. */
  subscribe(listener: () => void): () => void;
}

const NAVIGATED = "cosmic-quiz:navigated";

export function createHistoryRouter(host: RouterHost): HistoryRouter {
  return {
    current: () => host.location.pathname + host.location.search,
    navigate(to, { replace = false } = {}) {
      const url = new URL(to, host.location.href);
      if (url.origin !== host.location.origin) {
        host.location.assign(url.href);
        return;
      }
      const target = url.pathname + url.search + url.hash;
      const here = host.location.pathname + host.location.search + host.location.hash;
      if (target === here) {
        return;
      }
      if (replace) {
        host.history.replaceState(null, "", target);
      } else {
        host.history.pushState(null, "", target);
        // A new page starts at the top. Back and Forward keep the browser's own scroll handling.
        host.scrollTo(0, 0);
      }
      host.dispatchEvent(new Event(NAVIGATED));
    },
    subscribe(listener) {
      host.addEventListener("popstate", listener);
      host.addEventListener(NAVIGATED, listener);
      return () => {
        host.removeEventListener("popstate", listener);
        host.removeEventListener(NAVIGATED, listener);
      };
    },
  };
}

let browserRouter: HistoryRouter | null = null;

function browser(): HistoryRouter {
  browserRouter ??= createHistoryRouter(window);
  return browserRouter;
}

/** Go to a path in this app without reloading the page. */
export function navigate(to: string, options?: { replace?: boolean }): void {
  browser().navigate(to, options);
}

/** The current path and query, re-rendering on every navigation. */
export function useLocation(): URL {
  const router = browser();
  const current = useSyncExternalStore(router.subscribe, router.current);
  return new URL(current, window.location.origin);
}

/** Whether a click on a link should be handled in the page: a plain left click with no modifier
 * key (those open a new tab or window, which the browser should do itself). */
export function isPlainLeftClick(event: {
  button: number;
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
  defaultPrevented: boolean;
}): boolean {
  return (
    event.button === 0 &&
    !event.defaultPrevented &&
    !event.metaKey &&
    !event.ctrlKey &&
    !event.shiftKey &&
    !event.altKey
  );
}

/** The browser tab's title for a page. */
export function usePageTitle(title: string | null): void {
  useEffect(() => {
    document.title = title ? `${title} - Cosmic Quiz` : "Cosmic Quiz";
  }, [title]);
}
