import { PATHS } from "../router";
import { TROPHIES, type TrophyTiers } from "../trophies";
import { Link } from "./Link";
import { TrophyIcon } from "./TrophyIcon";

/** Every trophy in a row, in the tier reached or grey, with a link to the full case. */
export function TrophyShelf({ trophies }: { trophies: TrophyTiers }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <ul className="flex flex-wrap gap-2" aria-label="Trophies">
        {TROPHIES.map((entry) => {
          const tier = trophies[entry.id];
          const label = tier ? `${entry.name}: ${tier}` : `${entry.name}: not earned yet`;
          return (
            <li key={entry.id} title={label}>
              <TrophyIcon glyph={entry.id} tone={tier ?? "locked"} />
              <span className="sr-only">{label}</span>
            </li>
          );
        })}
      </ul>
      <Link
        to={PATHS.trophies}
        className="shrink-0 font-pixel text-[8px] uppercase text-slate hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal"
      >
        All trophies &gt;
      </Link>
    </div>
  );
}
