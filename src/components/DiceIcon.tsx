/** A small die face drawn from squares, matching the pixel accents. Decorative only. */
export function DiceIcon() {
  return (
    <svg
      viewBox="0 0 12 12"
      width="12"
      height="12"
      aria-hidden="true"
      className="shrink-0"
      shapeRendering="crispEdges"
    >
      <rect x="0.5" y="0.5" width="11" height="11" fill="none" stroke="currentColor" />
      <rect x="2.5" y="2.5" width="2" height="2" fill="currentColor" />
      <rect x="5" y="5" width="2" height="2" fill="currentColor" />
      <rect x="7.5" y="7.5" width="2" height="2" fill="currentColor" />
    </svg>
  );
}
