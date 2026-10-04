import { BADGES, type BadgeId } from "../game";

/** A badge in the pixel style: gold when earned, dim with how to earn it when not. */
export function BadgeChip({ id, earned }: { id: BadgeId; earned: boolean }) {
  const badge = BADGES.find((entry) => entry.id === id);
  if (!badge) {
    return null;
  }
  return (
    <li
      title={earned ? badge.name : `${badge.name}: ${badge.how}`}
      className={`flex items-center gap-2 rounded-sm border px-2.5 py-1.5 font-pixel text-[8px] uppercase ${
        earned ? "border-gold/60 text-gold" : "border-white/10 text-slate/60"
      }`}
    >
      <span
        aria-hidden="true"
        className={`inline-block size-1 ${earned ? "bg-gold" : "bg-slate/40"}`}
      />
      {badge.name}
      <span className="sr-only">{earned ? "(earned)" : `(not yet: ${badge.how})`}</span>
    </li>
  );
}
