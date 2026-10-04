import { BADGES, rankFor } from "../game";
import type { Profile } from "../profile";
import { BadgeChip } from "./BadgeChip";

const NUMBER = new Intl.NumberFormat("en-IE");

/** The player's rank, progress to the next one, and badges. Kept in this browser. */
export function ProfileStrip({ profile }: { profile: Profile }) {
  const rank = rankFor(profile.points);
  const percent = Math.round(rank.progress * 100);
  return (
    <section aria-label="Your progress" className="w-full max-w-xl">
      <div className="flex items-baseline justify-between gap-4">
        <p className="font-heading text-lg font-bold">
          <span className="sr-only">Rank: </span>
          {rank.name}
        </p>
        <p className="text-sm tabular-nums text-slate">
          {NUMBER.format(profile.points)}
          {rank.next ? ` / ${NUMBER.format(rank.next.points)}` : ""} pts
        </p>
      </div>
      <div
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label={rank.next ? `Progress to ${rank.next.name}` : "Top rank reached"}
      >
        <div className="h-full bg-teal transition-[width] duration-700" style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-2 text-xs text-slate">
        {rank.next ? `Next rank: ${rank.next.name}` : "Top rank reached."}
        {profile.answered > 0 &&
          ` · ${profile.correct}/${profile.answered} correct · best streak ${profile.bestStreak}`}
      </p>
      <ul className="mt-4 flex flex-wrap gap-2" aria-label="Badges">
        {BADGES.map((badge) => (
          <BadgeChip key={badge.id} id={badge.id} earned={profile.badges.includes(badge.id)} />
        ))}
      </ul>
    </section>
  );
}
