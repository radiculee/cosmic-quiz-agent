import { learnTopicPath } from "../router";
import type { BankTopic, TopicImage } from "../types";
import { topicVisual } from "../topics";
import { FactGlyph } from "./FactGlyph";
import { Link } from "./Link";

/** A small pixel tick for topics already read. Decorative: the word beside it says it too. */
function Tick() {
  return (
    <svg
      viewBox="0 0 7 7"
      width="12"
      height="12"
      shapeRendering="crispEdges"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
      className="shrink-0"
    >
      <path d="M6 1h1v1h-1zM5 2h1v1h-1zM4 3h1v1h-1zM0 3h1v1h-1zM1 4h1v1h-1zM3 4h1v1h-1zM2 5h1v1h-1z" />
    </svg>
  );
}

const THUMB = "h-24 w-24 shrink-0 rounded-sm sm:h-28 sm:w-28";
const CREDIT_LINK =
  "pointer-events-auto whitespace-nowrap underline underline-offset-2 hover:text-teal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal";

function ExternalLink({ href, children }: { href: string; children: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={CREDIT_LINK}>
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

/** Who made the picture and on what licence, as the licence requires, with the licence and the
 * file's page linked. It sits above the card's stretched link so each link is its own target.
 * The Curator's credit already names the licence (`credit_line` in curator/images.py), so the
 * licence is shown in that place. A hand-written credit does not, so the licence follows it. */
function Credit({ image }: { image: TopicImage }) {
  const licence = image.licence_url ? (
    <ExternalLink href={image.licence_url}>{image.licence}</ExternalLink>
  ) : (
    image.licence
  );
  const at = image.credit.lastIndexOf(image.licence);
  return (
    <p className="pointer-events-none relative z-10 border-t border-white/5 px-3 py-2 text-[11px] leading-relaxed text-slate">
      {at < 0 ? (
        <>
          {image.credit}, {licence}
        </>
      ) : (
        <>
          {image.credit.slice(0, at)}
          {licence}
          {image.credit.slice(at + image.licence.length)}
        </>
      )}
      {" · "}
      <ExternalLink href={image.page_url}>File page</ExternalLink>
    </p>
  );
}

/** The LEARN topics as cards, each opening its explanation at its own address. A card has its
 * picture and credit, or a fact with a plain glyph where there is no picture, or just the name.
 * The title is the link and is stretched over the card; the credit's links sit above it. Each
 * card keeps clear of the site header when keyboard focus scrolls it into view. */
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
        const visual = topicVisual(topic);
        return (
          <li
            key={topic.name}
            className={`relative flex scroll-mt-32 flex-col overflow-hidden rounded-lg border bg-surface transition-colors hover:border-white/30 has-[a[data-title]:focus-visible]:outline-2 has-[a[data-title]:focus-visible]:outline-offset-2 has-[a[data-title]:focus-visible]:outline-teal ${
              read ? "border-teal/50" : "border-white/10"
            }`}
          >
            {read && (
              <span className="absolute right-0 top-0 flex items-center gap-1 rounded-bl-sm bg-teal px-2 py-1 font-pixel text-[8px] uppercase text-void">
                <Tick />
                Read
              </span>
            )}
            <div className="flex items-start gap-3 p-3">
              {visual.kind === "image" && (
                <img
                  src={visual.image.src}
                  width={visual.image.width}
                  height={visual.image.height}
                  alt={topic.name}
                  loading="lazy"
                  decoding="async"
                  className={`${THUMB} bg-void object-cover`}
                />
              )}
              {visual.kind === "fact" && (
                <div className={`${THUMB} flex items-center justify-center bg-void`}>
                  <FactGlyph category={visual.category} />
                </div>
              )}
              <div className={`min-w-0 flex-1 ${read ? "pr-14" : ""}`}>
                {topic.kind !== "evergreen" && (
                  <span
                    className={`mb-1 block font-pixel text-[8px] uppercase ${
                      topic.kind === "news" ? "text-gold" : "text-slate"
                    }`}
                  >
                    {topic.kind === "news" ? "News" : "Web"}
                  </span>
                )}
                <Link
                  to={learnTopicPath(topic.name)}
                  data-title
                  className={`break-words font-heading text-lg font-bold leading-snug after:absolute after:inset-0 after:content-[''] focus-visible:outline-none ${
                    read ? "text-ink/75" : "text-ink"
                  }`}
                >
                  {topic.name}
                </Link>
                {visual.kind === "fact" && (
                  <p className="mt-1.5 text-xs leading-relaxed text-slate">{visual.fact.text}</p>
                )}
              </div>
            </div>
            {visual.kind === "image" && <Credit image={visual.image} />}
          </li>
        );
      })}
    </ul>
  );
}
