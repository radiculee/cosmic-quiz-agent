import type { ReactNode } from "react";

import type { FactCategory } from "../topics";

// Plain outline shapes on a 24 x 24 grid, one per category. No sprites or pixel art
// (CLAUDE.md): a circle, a ring, an arc and the like.
const SHAPES: Record<FactCategory, ReactNode> = {
  "black-hole": (
    <>
      <circle cx="12" cy="12" r="4" fill="currentColor" />
      <ellipse cx="12" cy="12" rx="10" ry="4" />
    </>
  ),
  galaxy: (
    <>
      <ellipse cx="12" cy="12" rx="10" ry="4.5" transform="rotate(-30 12 12)" />
      <ellipse cx="12" cy="12" rx="5.5" ry="2.5" transform="rotate(-30 12 12)" />
      <circle cx="12" cy="12" r="1.2" fill="currentColor" />
    </>
  ),
  cosmology: (
    <>
      <circle cx="12" cy="12" r="2" fill="currentColor" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="10" />
    </>
  ),
  particle: (
    <>
      <circle cx="12" cy="12" r="2.2" fill="currentColor" />
      <ellipse cx="12" cy="12" rx="10" ry="4" />
      <ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)" />
      <ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)" />
    </>
  ),
  mission: (
    <>
      <path d="M12 2 L17 14 L12 12 L7 14 Z" />
      <path d="M9 20 H15 M12 14 V22" />
    </>
  ),
  star: <path d="M12 2 L14 10 L22 12 L14 14 L12 22 L10 14 L2 12 L10 10 Z" />,
  planet: (
    <>
      <circle cx="12" cy="12" r="5.5" />
      <ellipse cx="12" cy="12" rx="11" ry="3.2" transform="rotate(-20 12 12)" />
    </>
  ),
  "small-body": <path d="M5 9 L10 4 L17 5 L20 11 L17 18 L10 20 L4 15 Z" />,
  space: (
    <>
      <circle cx="6" cy="7" r="1.4" fill="currentColor" />
      <circle cx="17" cy="5" r="1" fill="currentColor" />
      <circle cx="13" cy="13" r="2" fill="currentColor" />
      <circle cx="19" cy="18" r="1.4" fill="currentColor" />
      <circle cx="5" cy="18" r="1" fill="currentColor" />
    </>
  ),
};

/** A topic card's art where there is no picture: a plain outline for the fact's category. */
export function FactGlyph({ category }: { category: FactCategory }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="40"
      height="40"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
      className="text-teal"
    >
      {SHAPES[category]}
    </svg>
  );
}
