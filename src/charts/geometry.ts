/**
 * Layout for the hand-written SVG charts: where each mark goes and the shape it takes. Pure,
 * so the geometry is tested without a browser.
 *
 * The marks follow one spec: bars at most 24px thick, a 4px rounded data end and a square
 * baseline end, and a 2px gap of the surface between touching marks (never a drawn border).
 */

export const BAR_RADIUS = 4;
export const MAX_BAR = 24;
export const GAP = 2;
/** A part too small to see at its true width still shows as a sliver this wide. */
export const MIN_SEGMENT = 2;

function radius(r: number, ...limits: number[]): number {
  return Math.max(0, Math.min(r, ...limits));
}

/** A horizontal bar growing right from `x`: square at the baseline, rounded at the data end. */
export function horizontalBar(
  x: number,
  y: number,
  width: number,
  height: number,
  r = BAR_RADIUS,
): string {
  const k = radius(r, width, height / 2);
  const end = x + width;
  return [
    `M${x},${y}`,
    `H${end - k}`,
    `A${k},${k} 0 0 1 ${end},${y + k}`,
    `V${y + height - k}`,
    `A${k},${k} 0 0 1 ${end - k},${y + height}`,
    `H${x}`,
    "Z",
  ].join(" ");
}

/** A column growing up from `baseline`: square at the baseline, rounded at the top. */
export function verticalBar(
  x: number,
  baseline: number,
  width: number,
  height: number,
  r = BAR_RADIUS,
): string {
  const k = radius(r, height, width / 2);
  const top = baseline - height;
  return [
    `M${x},${baseline}`,
    `V${top + k}`,
    `A${k},${k} 0 0 1 ${x + k},${top}`,
    `H${x + width - k}`,
    `A${k},${k} 0 0 1 ${x + width},${top + k}`,
    `V${baseline}`,
    "Z",
  ].join(" ");
}

/** A plain rectangle, for the inner parts of a split bar. */
export function block(x: number, y: number, width: number, height: number): string {
  return `M${x},${y} H${x + width} V${y + height} H${x} Z`;
}

export interface Segment {
  /** Which value this is, in the order given. */
  index: number;
  x: number;
  width: number;
}

/**
 * A part-to-whole bar `width` wide: one segment per non-zero value, in order, with a 2px gap
 * between neighbours. A tiny part keeps a visible sliver; the largest part gives up the room.
 */
export function splitLayout(values: readonly number[], width: number, gap = GAP): Segment[] {
  const shown = values
    .map((value, index) => ({ value, index }))
    .filter((entry) => entry.value > 0);
  const total = shown.reduce((sum, entry) => sum + entry.value, 0);
  if (total <= 0 || width <= 0) {
    return [];
  }
  const usable = Math.max(0, width - gap * (shown.length - 1));
  const widths = shown.map((entry) => Math.max(MIN_SEGMENT, (usable * entry.value) / total));
  const excess = widths.reduce((sum, w) => sum + w, 0) - usable;
  if (excess > 0) {
    const largest = widths.indexOf(Math.max(...widths));
    widths[largest] = Math.max(MIN_SEGMENT, (widths[largest] ?? 0) - excess);
  }
  let x = 0;
  return shown.map((entry, position) => {
    const segment = { index: entry.index, x, width: widths[position] ?? 0 };
    x += segment.width + gap;
    return segment;
  });
}

export interface Column {
  x: number;
  width: number;
}

/** `count` columns across `width`: each in the middle of its band, at most 24px wide, with at
 * least a 2px gap between neighbours. */
export function columnLayout(count: number, width: number, max = MAX_BAR, gap = GAP): Column[] {
  if (count <= 0 || width <= 0) {
    return [];
  }
  const band = width / count;
  const columnWidth = Math.max(1, Math.min(max, band - gap));
  return Array.from({ length: count }, (_, index) => ({
    x: index * band + (band - columnWidth) / 2,
    width: columnWidth,
  }));
}

/** How far along a track a value goes, from 0 to 1 (a value over the cap stays at 1). */
export function fillRatio(value: number, cap: number): number {
  if (cap <= 0 || value <= 0) {
    return 0;
  }
  return Math.min(1, value / cap);
}
