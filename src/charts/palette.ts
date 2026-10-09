/**
 * Chart colours, all from the design tokens (src/index.css). They are CSS values, so the charts
 * set them through `style`: an SVG presentation attribute such as fill="var(...)" is not
 * resolved, and the mark would fall back to black. A split's parts are coloured by
 * what they mean, never by their rank: teal is a pass, gold a doubt, rust a failure and lavender
 * something neutral (did not run, retired). Single-series charts use teal.
 *
 * Checked on the panel's surface (#0D1117) with the data-visualisation palette validator in this
 * order (teal, gold, rust, lavender): neighbours stay apart for colour-blind readers (worst
 * delta E 11.4, target 8) and for everyone else (17.9, floor 15), and every mark has at least 3:1
 * contrast. Gold and lavender are paler than a chart palette would choose, so a split always
 * comes with a legend that names each part and gives its number: colour is never the only cue.
 */
import type { PartTone } from "../stats";

export const TONE_FILL: Record<PartTone, string> = {
  good: "var(--color-teal)",
  doubt: "var(--color-gold)",
  bad: "var(--color-rust)",
  neutral: "var(--color-lavender)",
};

export const SERIES_FILL = "var(--color-teal)";
/** Hairline baselines and rules: one step off the surface. */
export const RULE = "rgb(139 155 170 / 0.3)";
/** Values and labels drawn inside an SVG use the text tokens, never a series colour. */
export const LABEL_FILL = "var(--color-slate)";
export const VALUE_FILL = "var(--color-ink)";
