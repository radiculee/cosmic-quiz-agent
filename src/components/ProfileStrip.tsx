import { rankFor } from "../game";
import type { Profile } from "../profile";
import { TrophyShelf } from "./TrophyShelf";

const NUMBER = new Intl.NumberFormat("en-IE");

/** The player's rank, progress to the next one, and (on the home page) the trophy shelf. Kept in
 * this browser. */
export function ProfileStrip({ profile, shelf = false }: { profile: Profile; shelf?: boolean }) {
  const rank = rankFor(profile.points);
  const percent = Math.round(rank.progress * 100);
  return (
    <section aria-label="Your progress" className="w-full">
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
        <div
          className="h-full bg-teal transition-[width] duration-700 motion-reduce:transition-none"
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-slate">
        {rank.next ? `Next rank: ${rank.next.name}` : "Top rank reached."}
        {profile.answered > 0 &&
          ` · ${profile.correct}/${profile.answered} correct · best streak ${profile.bestStreak}`}
      </p>
      {shelf && (
        <div className="mt-5">
          <TrophyShelf trophies={profile.trophies} />
        </div>
      )}
    </section>
  );
}
