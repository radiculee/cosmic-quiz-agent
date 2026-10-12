import { learnTopicPath } from "../router";
import type { BankTopic } from "../types";
import { Link } from "./Link";

/** A small pixel tick for topics already read. Decorative: the text says it too. */
function Tick() {
  return (
    <svg
      viewBox="0 0 7 7"
      width="14"
      height="14"
      shapeRendering="crispEdges"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
      className="shrink-0 text-teal"
    >
      <path d="M6 1h1v1h-1zM5 2h1v1h-1zM4 3h1v1h-1zM0 3h1v1h-1zM1 4h1v1h-1zM3 4h1v1h-1zM2 5h1v1h-1z" />
    </svg>
  );
}

/** The LEARN topics as cards, each opening its explanation at its own address. Each card keeps
 * clear of the Learn page's sticky bar when keyboard focus scrolls it into view. */
export function TopicGrid({
  topics,
  learned,
}: {
  topics: readonly BankTopic[];
  learned: ReadonlySet<string>;
}) {
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {topics.map((topic) => {
        const read = learned.has(topic.name);
        return (
          <li key={topic.name}>
            <Link
              to={learnTopicPath(topic.name)}
              className={`flex h-full scroll-mt-40 items-center justify-between gap-3 rounded-lg border bg-surface px-4 py-3.5 transition-colors md:scroll-mt-28 hover:border-white/30 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal ${
                read ? "border-teal/25" : "border-white/10"
              }`}
            >
              <span className={read ? "text-ink/75" : "text-ink"}>{topic.name}</span>
              <span className="flex shrink-0 items-center gap-2">
                {topic.kind === "news" && (
                  <span className="font-pixel text-[8px] uppercase text-gold">News</span>
                )}
                {topic.kind === "custom" && (
                  <span className="font-pixel text-[8px] uppercase text-lavender">Web</span>
                )}
                {read && <Tick />}
                {read && <span className="sr-only">(read)</span>}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
