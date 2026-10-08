import type { Tier, TrophyId } from "../trophies";

export type Glyph = TrophyId | "rank-up";
/** A tier's colour, grey for a tier not earned yet, or teal for a rank-up. */
export type IconTone = Tier | "locked" | "rank";

// Each icon is an 11 x 11 pixel map ("#" is a lit pixel), drawn at whole-pixel sizes so the
// edges stay crisp: the pixel accents of the design, with no emojis or images.
const MAPS: Record<Glyph, readonly string[]> = {
  "first-light": [
    ".....#.....",
    ".....#.....",
    ".....#.....",
    "....###....",
    "...#####...",
    "###########",
    "...#####...",
    "....###....",
    ".....#.....",
    ".....#.....",
    ".....#.....",
  ],
  "hot-streak": [
    "....#......",
    "....##.....",
    "...###.....",
    "...####.#..",
    "..#####.##.",
    "..########.",
    ".####.####.",
    ".###...###.",
    ".###...###.",
    "..##...##..",
    "...#####...",
  ],
  finisher: [
    "#..........",
    "###..##..##",
    "###..##..##",
    "#..##..##..",
    "#..##..##..",
    "###..##..##",
    "###..##..##",
    "#..........",
    "#..........",
    "#..........",
    "#..........",
  ],
  "perfect-run": [
    "...........",
    "...........",
    ".........##",
    "........###",
    ".......###.",
    "##....###..",
    "###..###...",
    ".######....",
    "..####.....",
    "...##......",
    "...........",
  ],
  "speed-runner": [
    ".....#####.",
    "....#####..",
    "...#####...",
    "..#####....",
    ".#########.",
    ".....####..",
    "....####...",
    "...####....",
    "..###......",
    ".##........",
    "#..........",
  ],
  "hard-mode": [
    "...........",
    "#....#....#",
    "##..###..##",
    "###.###.###",
    "###########",
    "##.##.##.##",
    "###########",
    "...........",
    "###########",
    "###########",
    "...........",
  ],
  explorer: [
    "...........",
    ".##.....##.",
    "#..##.##..#",
    "#....#....#",
    "#.##.#.##.#",
    "#....#....#",
    "#.##.#.##.#",
    "#....#....#",
    "###..#..###",
    "...#####...",
    "...........",
  ],
  "web-researcher": [
    "...#####...",
    "..#..#..#..",
    ".#...#...#.",
    "###########",
    "#....#....#",
    "#....#....#",
    "#....#....#",
    "###########",
    ".#...#...#.",
    "..#..#..#..",
    "...#####...",
  ],
  "rank-up": [
    ".....#.....",
    "....###....",
    "...#####...",
    "..###.###..",
    ".###...###.",
    "###.....###",
    ".....#.....",
    "....###....",
    "...#####...",
    "..###.###..",
    ".###...###.",
  ],
};

/** One SVG path per icon: a 1 x 1 square for each lit pixel. */
function pathOf(rows: readonly string[]): string {
  let d = "";
  rows.forEach((row, y) => {
    [...row].forEach((pixel, x) => {
      if (pixel === "#") {
        d += `M${x} ${y}h1v1h-1z`;
      }
    });
  });
  return d;
}

const GLYPH_PATHS = Object.fromEntries(
  Object.entries(MAPS).map(([glyph, rows]) => [glyph, pathOf(rows)]),
) as Record<Glyph, string>;

/** A tier's name in its colour, for labels beside the icon. */
export const TIER_TEXT: Record<Tier, string> = {
  bronze: "text-rust",
  silver: "text-slate",
  gold: "text-gold",
};

const TONES: Record<IconTone, string> = {
  bronze: "border-rust text-rust",
  silver: "border-slate text-slate",
  gold: "border-gold text-gold",
  rank: "border-teal/60 text-teal",
  locked: "border-white/10 text-white/15",
};

// The tile, and the icon inside it at a multiple of 11 pixels.
const SIZES = {
  sm: { tile: "size-[34px]", icon: 22 },
  md: { tile: "size-10", icon: 22 },
  lg: { tile: "size-14", icon: 33 },
} as const;

/** A trophy (or rank-up) in its tier's colour. Decorative: whatever shows it also says it in
 * words. */
export function TrophyIcon({
  glyph,
  tone,
  size = "md",
}: {
  glyph: Glyph;
  tone: IconTone;
  size?: keyof typeof SIZES;
}) {
  const { tile, icon } = SIZES[size];
  return (
    <span
      aria-hidden="true"
      className={`grid shrink-0 place-items-center rounded-sm border bg-void ${tile} ${TONES[tone]}`}
    >
      <svg
        viewBox="0 0 11 11"
        width={icon}
        height={icon}
        shapeRendering="crispEdges"
        fill="currentColor"
        focusable="false"
      >
        <path d={GLYPH_PATHS[glyph]} />
      </svg>
    </span>
  );
}
