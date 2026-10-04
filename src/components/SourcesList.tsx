import type { Source } from "../types";

function pathOf(url: string): string {
  try {
    const { pathname } = new URL(url);
    return decodeURIComponent(pathname);
  } catch {
    return url;
  }
}

/** The pages the agent read for this item, each with the passage it quoted. */
export function SourcesList({ sources }: { sources: Source[] }) {
  return (
    <section aria-labelledby="sources-heading" className="mt-8">
      <h3 id="sources-heading" className="font-pixel text-[9px] uppercase text-slate">
        Sources
      </h3>
      <ol className="mt-4 space-y-5">
        {sources.map((source, index) => (
          <li key={`${source.url}-${index}`} className="flex gap-4">
            <span className="font-pixel text-[9px] leading-6 text-teal">{index + 1}.</span>
            <div className="min-w-0">
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group inline-flex max-w-full items-baseline gap-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
              >
                <span className="font-medium text-ink">{source.site}</span>
                <span className="truncate text-sm text-slate group-hover:text-teal">
                  {pathOf(source.url)}
                </span>
                <span className="sr-only">(opens in a new tab)</span>
              </a>
              <blockquote className="mt-1.5 border-l-2 border-white/10 pl-3 text-sm leading-relaxed text-ink/80">
                &ldquo;{source.quote}&rdquo;
              </blockquote>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
