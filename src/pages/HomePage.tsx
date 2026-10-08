import { Link } from "../components/Link";
import { ModeCard } from "../components/ModeCard";
import { ProfileStrip } from "../components/ProfileStrip";
import { quotaShort } from "../quota";
import { PATHS, usePageTitle } from "../router";
import { loadedTopics } from "../useTopics";
import { useQuota } from "../useQuota";
import type { PageProps } from "./common";

/**
 * The front page: Learn and Quiz as two large cards, live research from the web as a smaller one
 * with the visitor's searches left today, then rank, points and the trophy shelf.
 */
export function HomePage({ topicsState, profile }: Pick<PageProps, "topicsState" | "profile">) {
  usePageTitle(null);
  const [quota] = useQuota();
  const topics = loadedTopics(topicsState);
  const learnTopics = topics.filter((topic) => topic.learn.length > 0);
  const learned = new Set(profile.learned);
  const read = learnTopics.filter((topic) => learned.has(topic.name)).length;
  const loaded = topicsState.kind === "loaded";

  return (
    <div className="flex flex-col items-center pt-6">
      <h1 className="text-center font-heading text-5xl font-bold uppercase tracking-tight sm:text-7xl">
        Cosmic Quiz
      </h1>
      <p className="mt-6 max-w-xl text-center text-lg leading-relaxed text-ink/90">
        An AI agent reads NASA, ESA and Wikipedia, writes the questions, and checks every answer
        against the pages it read.
      </p>

      <div className="mt-12 grid w-full grid-cols-1 gap-5 sm:grid-cols-2">
        <ModeCard
          to={PATHS.learn}
          label="Learn"
          title="Read a topic"
          text={
            loaded
              ? `${learnTopics.length} topics, each explained at three levels with the pages it is based on.`
              : "Topics explained at three levels, with the pages each is based on."
          }
          footer={loaded ? `${read} of ${learnTopics.length} read` : null}
        />
        <ModeCard
          to={PATHS.quiz}
          label="Quiz"
          title="Play a run"
          text="10, 30 or 60 questions against the clock, every one on a different topic."
          footer={profile.bestStreak > 0 ? `Best streak ${profile.bestStreak}` : "Not played yet"}
        />
      </div>

      <Link
        to={PATHS.explore}
        className="mt-5 flex w-full flex-col gap-3 rounded-lg border border-white/10 bg-surface px-6 py-4 transition-colors hover:border-white/25 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal sm:flex-row sm:items-center sm:justify-between sm:gap-6"
      >
        <span>
          <span className="block font-medium text-ink">Try a new topic from the web</span>
          <span className="mt-1 block text-xs text-slate">
            The agent researches it live: an explanation and a question at each level, each
            checked against its sources.
          </span>
        </span>
        {quota.kind === "loaded" && (
          <span className="shrink-0 font-pixel text-[9px] uppercase text-teal">
            {quotaShort(quota.quota)}
          </span>
        )}
      </Link>

      <div className="mt-12 w-full">
        <ProfileStrip profile={profile} shelf />
      </div>

      {loaded && (
        <p className="mt-14 text-center text-xs text-slate">
          {topics.length} topics in the bank. Every answer is checked against the pages the agent
          read.
        </p>
      )}
    </div>
  );
}
