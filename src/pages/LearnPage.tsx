import { useEffect, useId, useMemo, useRef, useState } from "react";

import { ApiError, fetchItem } from "../api";
import { DiceIcon } from "../components/DiceIcon";
import { Dropdown } from "../components/Dropdown";
import { LearnCard } from "../components/LearnCard";
import { Link } from "../components/Link";
import { TopicGrid } from "../components/TopicGrid";
import { afterLearn } from "../profile";
import {
  explorePath,
  learnTopicPath,
  navigate,
  PATHS,
  topicForSlug,
  usePageTitle,
} from "../router";
import { filterTopics, randomTopic, topicStatus } from "../topics";
import { type BankTopic, DIFFICULTIES, type Difficulty, type LearnItem } from "../types";
import { loadedTopics } from "../useTopics";
import {
  LoadFailed,
  loadError,
  MAX_TOPIC_CHARS,
  MIN_TOPIC_CHARS,
  PageHeading,
  type PageProps,
  SECONDARY_BUTTON,
  TopicsNotice,
} from "./common";

/** `/learn` lists the topics; `/learn/<slug>` shows one. */
export function LearnPage({ slug, ...props }: PageProps & { slug?: string | undefined }) {
  return slug === undefined ? <LearnIndex {...props} /> : <LearnTopic slug={slug} {...props} />;
}

// --- The topic grid ---------------------------------------------------------------------------

/**
 * The topics: a difficulty dropdown, a search box and Random, then the grid. The controls sit in
 * one solid bar that sticks to the top of the screen while the grid scrolls under it (decided
 * 2026-10-10), so they are always at hand with a single scroll; a box that scrolled on its own
 * would trap the page's scroll on a phone. The bar is one row at every width (decided
 * 2026-10-17): on a phone, Random shows only its die.
 */
function LearnIndex({ topicsState, retryTopics, profile, difficulty, setDifficulty }: PageProps) {
  usePageTitle("Learn");
  const searchId = useId();
  const [query, setQuery] = useState("");
  const topics = loadedTopics(topicsState);
  const learned = useMemo(() => new Set(profile.learned), [profile.learned]);
  const available = filterTopics(topics, "", "learn", difficulty);
  const shown = filterTopics(topics, query, "learn", difficulty);
  const read = available.filter((topic) => learned.has(topic.name)).length;

  function pickRandom() {
    const topic = randomTopic(topics, "learn", difficulty, "", Math.random, profile.learned);
    if (topic) {
      navigate(learnTopicPath(topic.name));
    }
  }

  return (
    <div>
      <PageHeading title="Learn">
        Pick a topic for a plain-language explanation and the pages it is based on.
      </PageHeading>

      <div className="pixel-border sticky top-0 z-10 mt-10 flex gap-3 rounded-sm bg-surface p-3">
        <Dropdown
          label="Difficulty"
          options={DIFFICULTIES}
          value={difficulty}
          onChange={setDifficulty}
          stretch
        />
        <label htmlFor={searchId} className="sr-only">
          Search topics
        </label>
        {/* 16px text: iOS zooms the page into any smaller input. */}
        <input
          id={searchId}
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="Search topics"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="min-w-0 flex-1 rounded-lg border border-white/10 bg-void px-4 py-3 text-base text-ink placeholder:text-slate/70 focus:border-teal focus:outline-none"
        />
        <button
          type="button"
          onClick={pickRandom}
          disabled={available.length === 0}
          title="A random topic"
          className={`${SECONDARY_BUTTON} shrink-0 px-4 py-3 text-[9px]`}
        >
          <DiceIcon />
          <span className="sr-only sm:not-sr-only">Random</span>
        </button>
      </div>

      <div className="mt-6">
        <TopicsNotice state={topicsState} onRetry={retryTopics} />
        {topicsState.kind === "loaded" && (
          <>
            <p aria-live="polite" className="scene-note mb-4 text-sm">
              {query.trim()
                ? `${shown.length} of ${available.length} topics match.`
                : `${read} of ${available.length} read at ${difficulty.toUpperCase()}.`}
            </p>
            {shown.length > 0 ? (
              <TopicGrid topics={shown} learned={learned} />
            ) : (
              <NoMatch query={query} topics={topics} difficulty={difficulty} />
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** Nothing in the bank matches: say where the topic is, or offer to research it live. */
function NoMatch({
  query,
  topics,
  difficulty,
}: {
  query: string;
  topics: readonly BankTopic[];
  difficulty: Difficulty;
}) {
  const typed = query.trim();
  const status = topicStatus(topics, typed, "learn", difficulty);
  if (status.kind === "elsewhere" && status.difficulties.length > 0) {
    const others = status.difficulties.map((level) => level.toUpperCase()).join(" or ");
    return (
      <p className="scene-note text-sm">
        {status.topic.name} has no explanation at {difficulty.toUpperCase()} yet. Try {others}.
      </p>
    );
  }
  if (typed.length < MIN_TOPIC_CHARS || typed.length > MAX_TOPIC_CHARS) {
    return <p className="scene-note text-sm">No topics match.</p>;
  }
  return (
    <p className="scene-note text-sm">
      &ldquo;{typed}&rdquo; is not in the bank yet.{" "}
      <Link
        to={explorePath(typed)}
        className="text-teal underline underline-offset-4 hover:text-ink"
      >
        Research it live on the web page
      </Link>
      .
    </p>
  );
}

// --- One topic --------------------------------------------------------------------------------

type TopicView =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  | { kind: "loaded"; item: LearnItem };

function LearnTopic({
  slug,
  topicsState,
  retryTopics,
  profile,
  updateProfile,
  celebrate,
  difficulty,
  setDifficulty,
}: PageProps & { slug: string }) {
  const topics = loadedTopics(topicsState);
  const topic = topicForSlug(topics, slug);
  usePageTitle(topic?.name ?? "Learn");
  // The shared difficulty if this topic has it, else the first one it has.
  const level = topic ? (topic.learn.includes(difficulty) ? difficulty : topic.learn[0]) : undefined;
  const [view, setView] = useState<TopicView>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  // Read when a load starts, without making every profile change reload the item.
  const seen = useRef(profile.seenItems);
  useEffect(() => {
    seen.current = profile.seenItems;
  });

  const name = topic?.name;
  useEffect(() => {
    if (name === undefined || level === undefined) {
      return;
    }
    const controller = new AbortController();
    setView({ kind: "loading" });
    fetchItem(name, "learn", level, seen.current, controller.signal)
      .then((item) => {
        if (item.mode !== "learn") {
          throw new ApiError("expected a LEARN item");
        }
        setView({ kind: "loaded", item });
        celebrate(updateProfile((current) => afterLearn(current, item.id, item.topic)));
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setView({ kind: "failed", message: loadError(error) });
        }
      });
    return () => controller.abort();
  }, [name, level, attempt, celebrate, updateProfile]);

  function anotherTopic() {
    if (!name || !level) {
      return;
    }
    const next = randomTopic(topics, "learn", level, name, Math.random, profile.learned);
    if (next) {
      navigate(learnTopicPath(next.name));
    }
  }

  const back = (
    <Link
      to={PATHS.learn}
      className="on-scene-muted font-pixel text-[8px] uppercase hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal"
    >
      &lt; All topics
    </Link>
  );

  if (topicsState.kind !== "loaded") {
    return (
      <div className="pt-8">
        {back}
        <div className="mt-10">
          <TopicsNotice state={topicsState} onRetry={retryTopics} />
        </div>
      </div>
    );
  }
  if (!topic || level === undefined) {
    return (
      <div className="pt-8">
        {back}
        <p className="scene-note mx-auto mt-10 text-center">
          {topic
            ? `${topic.name} has no LEARN explanation yet.`
            : "There is no topic at this address."}{" "}
          <Link to={PATHS.learn} className="text-teal underline underline-offset-4 hover:text-ink">
            See every topic
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="pt-8">
      <h1 className="sr-only">{topic.name}</h1>
      <div className="flex flex-wrap items-center justify-between gap-4">
        {back}
        <Dropdown
          label="Difficulty"
          options={DIFFICULTIES}
          value={level}
          onChange={setDifficulty}
          disabled={DIFFICULTIES.filter((option) => !topic.learn.includes(option))}
        />
      </div>
      <div className="mt-6" aria-live="polite">
        {view.kind === "loading" && (
          <p className="scene-note mx-auto text-center text-sm">Loading {topic.name}...</p>
        )}
        {view.kind === "failed" && (
          <LoadFailed message={view.message} onRetry={() => setAttempt((n) => n + 1)} />
        )}
        {view.kind === "loaded" && <LearnCard item={view.item} onNext={anotherTopic} />}
      </div>
    </div>
  );
}
