import { PATHS } from "../router";
import { GitHubIcon } from "./GitHubIcon";
import { Link } from "./Link";

const GITHUB_URL = "https://github.com/radiculee/cosmic-quiz-agent";
const GITHUB_LABEL = "Cosmic Quiz on GitHub (opens in a new tab)";

/** The slim bar on every page (not sticky). Inner pages link home from the name on the left; the
 * home page has the big title instead. */
export function SiteHeader({ showHomeLink }: { showHomeLink: boolean }) {
  return (
    <header className="mx-auto flex h-14 w-full max-w-3xl items-center justify-between px-4">
      {showHomeLink ? (
        <Link
          to={PATHS.home}
          className="on-scene font-heading text-base font-bold uppercase tracking-tight hover:text-teal focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal"
        >
          Cosmic Quiz
        </Link>
      ) : (
        <span />
      )}
      <a
        href={GITHUB_URL}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={GITHUB_LABEL}
        title="GitHub"
        className="rounded-sm p-1 text-ink drop-shadow-[0_1px_2px_rgb(0_0_0/0.6)] transition-colors hover:text-teal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal"
      >
        <GitHubIcon />
      </a>
    </header>
  );
}
