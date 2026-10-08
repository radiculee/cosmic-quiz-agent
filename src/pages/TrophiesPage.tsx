import { TIER_TEXT, TrophyIcon } from "../components/TrophyIcon";
import { quizTopicCount } from "../game";
import { usePageTitle } from "../router";
import {
  type BankCounts,
  notYetPossible,
  TIER_COUNT,
  TIERS,
  tierIndex,
  tiersEarned,
  TROPHIES,
} from "../trophies";
import { loadedTopics } from "../useTopics";
import { PageHeading, type PageProps } from "./common";

function counted(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** Every trophy and tier: earned ones in their colour, the rest grey with how to earn them, and a
 * note on any tier the bank cannot support yet. */
export function TrophiesPage({ topicsState, profile }: Pick<PageProps, "topicsState" | "profile">) {
  usePageTitle("Trophies");
  const topics = loadedTopics(topicsState);
  const counts: BankCounts | null =
    topicsState.kind === "loaded"
      ? {
          quiz: {
            easy: quizTopicCount(topics, "easy"),
            medium: quizTopicCount(topics, "medium"),
            hard: quizTopicCount(topics, "hard"),
          },
          learnTopics: topics.filter((topic) => topic.learn.length > 0).length,
        }
      : null;

  return (
    <div>
      <PageHeading title="Trophies">
        {tiersEarned(profile.trophies)} of {TIER_COUNT} tiers earned. Kept in this browser.
      </PageHeading>
      <p className="mt-3 text-center text-xs text-slate">
        {counted(profile.finishedRuns, "run finished", "runs finished")} &middot;{" "}
        {counted(profile.learned.length, "topic read", "topics read")} &middot;{" "}
        {counted(profile.liveRuns, "live topic", "live topics")}
      </p>

      <ol className="mt-10 space-y-3">
        {TROPHIES.map((entry) => {
          const have = profile.trophies[entry.id];
          return (
            <li key={entry.id} className="pixel-border rounded-sm bg-surface/70 px-5 py-4">
              <div className="flex items-center gap-4">
                <TrophyIcon glyph={entry.id} tone={have ?? "locked"} size="lg" />
                <h2 className="font-heading text-xl font-bold">
                  {entry.name}
                  <span className="sr-only">{have ? `, ${have}` : ", not earned yet"}</span>
                </h2>
              </div>
              <ul className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-3">
                {TIERS.map((tier, index) => {
                  const earned = tierIndex(have) >= index;
                  const note = !earned && counts ? notYetPossible(entry.id, tier, counts) : null;
                  return (
                    <li
                      key={tier}
                      className={`flex items-start gap-3 rounded-md border px-3 py-2.5 ${
                        earned ? "border-white/10 bg-void/60" : "border-white/5"
                      }`}
                    >
                      <TrophyIcon glyph={entry.id} tone={earned ? tier : "locked"} size="sm" />
                      <div className="min-w-0">
                        <p
                          className={`font-pixel text-[8px] uppercase ${
                            earned ? TIER_TEXT[tier] : "text-slate/60"
                          }`}
                        >
                          {tier}
                          <span className="sr-only">{earned ? " (earned)" : " (not yet)"}</span>
                        </p>
                        <p className={`mt-1 text-xs leading-snug ${earned ? "text-ink/90" : "text-slate"}`}>
                          {entry.how(entry.goals[index] ?? 0)}
                        </p>
                        {note && <p className="mt-1 text-[11px] leading-snug text-slate/70">{note}</p>}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
