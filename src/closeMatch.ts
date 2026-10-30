/**
 * Typo-tolerant addresses: the nearest known path for a mistyped one ("/lern" is "/learn",
 * "/learn/antimater" is "/learn/antimatter"). A near miss with one clear answer is redirected;
 * anything less sure is offered as a suggestion on the 404 page. Pure, so it is unit-tested
 * (closeMatch.test.ts).
 */
import { learnTopicPath, PATHS } from "./router";
import type { BankTopic } from "./types";

/** Edits (insert, delete, replace, or swap two neighbours) between two strings. */
export function editDistance(a: string, b: string): number {
  const rows = a.length + 1;
  const cols = b.length + 1;
  const table: number[][] = Array.from({ length: rows }, (_, i) =>
    Array.from({ length: cols }, (_, j) => (i === 0 ? j : j === 0 ? i : 0)),
  );
  const at = (i: number, j: number): number => table[i]?.[j] ?? 0;
  for (let i = 1; i < rows; i++) {
    for (let j = 1; j < cols; j++) {
      const same = a[i - 1] === b[j - 1] ? 0 : 1;
      let best = Math.min(at(i - 1, j) + 1, at(i, j - 1) + 1, at(i - 1, j - 1) + same);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        best = Math.min(best, at(i - 2, j - 2) + 1);
      }
      const row = table[i];
      if (row) {
        row[j] = best;
      }
    }
  }
  return at(rows - 1, cols - 1);
}

/** How many edits still count as the same word: one in a short path, two in a longer one. */
function redirectLimit(length: number): number {
  return length < 8 ? 1 : 2;
}

/** A looser limit for suggestions, which a person reads and can ignore. */
function suggestLimit(length: number): number {
  return Math.max(2, Math.ceil(length / 3));
}

/** The paths the site has: its pages, and one per bank topic when the topics are known. */
export function knownPaths(topics: readonly BankTopic[]): string[] {
  const pages = Object.values(PATHS).filter((path) => path !== PATHS.home);
  return [...pages, ...topics.map((topic) => learnTopicPath(topic.name))];
}

function cleaned(pathname: string): string {
  let path = pathname.toLowerCase();
  while (path.length > 1 && path.endsWith("/")) {
    path = path.slice(0, -1);
  }
  return path;
}

interface Ranked {
  path: string;
  distance: number;
}

function ranked(pathname: string, candidates: readonly string[]): Ranked[] {
  const path = cleaned(pathname);
  return [...new Set(candidates)]
    .map((candidate) => ({ path: candidate, distance: editDistance(path, candidate) }))
    .sort((x, y) => x.distance - y.distance || x.path.localeCompare(y.path));
}

/** The one known path a mistyped path almost certainly meant, or null when none is close enough
 * or two are equally close. */
export function redirectFor(pathname: string, candidates: readonly string[]): string | null {
  const [best, next] = ranked(pathname, candidates);
  if (!best || best.distance === 0 || best.distance > redirectLimit(cleaned(pathname).length)) {
    return null;
  }
  return next && next.distance === best.distance ? null : best.path;
}

/** Up to `limit` known paths a mistyped path may have meant, nearest first. */
export function suggestionsFor(
  pathname: string,
  candidates: readonly string[],
  limit = 3,
): string[] {
  const typed = cleaned(pathname);
  const allowed = suggestLimit(typed.length);
  // A path that starts with what was typed ("/learn/black") is a good guess, however long it is.
  const starts = (path: string): boolean => path.startsWith(typed) && typed.length > 3;
  return ranked(pathname, candidates)
    .filter(({ path, distance }) => distance > 0 && (distance <= allowed || starts(path)))
    .sort((x, y) => Number(starts(y.path)) - Number(starts(x.path)))
    .slice(0, limit)
    .map(({ path }) => path);
}
