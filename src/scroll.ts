/**
 * Small rules for scrolling, pure so they are tested without a browser (scroll.test.ts). The
 * pages only ever scroll the window when the player asked for it (GO, Next, opening the
 * explanation); a stream of new content never moves the window (fixed 2026-10-10: the agent log
 * pulled players back up from the question they were answering).
 */

/** Within this many pixels of the end, a box counts as scrolled to its end. */
export const END_SLACK = 24;

/** Whether a scroll box is showing its end, so new lines should keep it there. */
export function atEnd(
  box: { scrollTop: number; scrollHeight: number; clientHeight: number },
  slack: number = END_SLACK,
): boolean {
  return box.scrollHeight - box.scrollTop - box.clientHeight <= slack;
}

/**
 * Whether a log should keep following its newest line after a scroll event: the box is at its
 * end, or no further up than where the log last put it (`pinnedTop`). The event for the log's own
 * scroll can arrive after more lines were added, so being short of the end does not by itself
 * mean the reader scrolled up.
 */
export function stillFollowing(
  box: { scrollTop: number; scrollHeight: number; clientHeight: number },
  pinnedTop: number,
): boolean {
  return atEnd(box) || box.scrollTop >= pinnedTop - 1;
}

/** Whether an element whose top is at `top` (from the top of the viewport) starts out of view,
 * above or below the screen. */
export function startsOffScreen(top: number, viewportHeight: number): boolean {
  return top < 0 || top >= viewportHeight;
}
