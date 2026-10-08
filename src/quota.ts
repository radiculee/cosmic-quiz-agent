/**
 * Words for the live-run quota. The daily count resets at midnight UTC (agent/limits.py), which
 * is 01:00 in Ireland in summer and 00:00 in winter, so the time is shown in Irish time from the
 * server's reset instant rather than written in.
 */
import type { Quota } from "./types";

const IRISH_TIME = new Intl.DateTimeFormat("en-IE", {
  timeZone: "Europe/Dublin",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** "01:00" for a reset at midnight UTC during Irish summer time. */
export function irishTime(iso: string): string {
  return IRISH_TIME.format(new Date(iso));
}

/** The short form, for the home page card: "2 of 3 left today". */
export function quotaShort(quota: Quota): string {
  if (!quota.global_open) {
    return "Paused for now";
  }
  return quota.remaining > 0 ? `${quota.remaining} of ${quota.limit} left today` : "None left today";
}

/** The full line on the web page. */
export function quotaLine(quota: Quota): string {
  const reset = `resets at ${irishTime(quota.resets_at)} Irish time`;
  if (quota.remaining === 0) {
    return `You have used today's ${quota.limit} live topics. The count ${reset}.`;
  }
  return `${quota.remaining} of ${quota.limit} left today, ${reset}.`;
}

/** The notice when the global caps are reached, whoever is asking. */
export const GLOBAL_CAP_NOTICE =
  "Live research has reached its limit for everyone for now. Topics already in the bank are still free to play.";
