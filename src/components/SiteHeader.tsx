import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { NAME } from "../brand";
import { matchRoute, PATHS, type Route, useLocation } from "../router";
import { GitHubIcon } from "./GitHubIcon";
import { Link } from "./Link";

const GITHUB_URL = "https://github.com/radiculee/cosmic-quiz-agent";
const GITHUB_LABEL = `${NAME} on GitHub (opens in a new tab)`;
const MENU_ID = "site-menu";

type Section = "learn" | "quiz" | "web";

const NAV: readonly { section: Section; label: string; to: string }[] = [
  { section: "learn", label: "Learn", to: PATHS.learn },
  { section: "quiz", label: "Quiz", to: PATHS.quiz },
  { section: "web", label: "Web", to: PATHS.explore },
];

/** Which navigation entry a page belongs to, if any. */
export function sectionOf(page: Route["page"]): Section | null {
  switch (page) {
    case "learn":
    case "learn-topic":
      return "learn";
    case "quiz":
      return "quiz";
    case "explore":
    case "explore-stats":
      return "web";
    default:
      return null;
  }
}

const NAV_LINK =
  "rounded-sm px-3 py-2 font-pixel text-[9px] uppercase transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal";

/**
 * The bar on every page, stuck to the top of the screen. Row one has the name (home), the three
 * pages, a place for the sign-in button and the GitHub link; on a phone the pages and the GitHub
 * link sit behind a menu button. Row two is the current page's settings, which the page draws
 * there with HeaderSettings (nothing on a page with none, and the row is then hidden).
 */
export function SiteHeader({ onSettingsSlot }: { onSettingsSlot: (element: HTMLElement | null) => void }) {
  const { pathname } = useLocation();
  const current = sectionOf(matchRoute(pathname).page);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);

  // Moving to another page closes the menu.
  useEffect(() => setMenuOpen(false), [pathname]);

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape" && menuOpen) {
      setMenuOpen(false);
      menuButton.current?.focus();
    }
  }

  const links = NAV.map(({ section, label, to }) => (
    <Link
      key={section}
      to={to}
      aria-current={current === section ? "page" : undefined}
      className={`${NAV_LINK} ${current === section ? "bg-white/5 text-teal" : "text-slate"}`}
    >
      {label}
    </Link>
  ));

  return (
    <header
      onKeyDown={onKeyDown}
      className="sticky top-0 z-30 w-full border-b border-white/10 bg-surface"
    >
      <div className="relative mx-auto flex h-14 max-w-3xl items-center gap-2 px-4">
        <Link
          to={PATHS.home}
          className="font-heading text-base font-bold uppercase tracking-tight text-ink hover:text-teal focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal"
        >
          {NAME}
        </Link>
        <nav aria-label="Main" className="ml-4 hidden items-center gap-1 sm:flex">
          {links}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {/* The sign-in button goes here (data's SignInButton). */}
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={GITHUB_LABEL}
            title="GitHub"
            className="hidden rounded-sm p-1 text-ink transition-colors hover:text-teal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal sm:block"
          >
            <GitHubIcon />
          </a>
          <button
            ref={menuButton}
            type="button"
            aria-expanded={menuOpen}
            aria-controls={MENU_ID}
            aria-label={menuOpen ? "Close the menu" : "Open the menu"}
            onClick={() => setMenuOpen((open) => !open)}
            className="rounded-sm border border-white/15 p-2.5 text-ink hover:border-white/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal sm:hidden"
          >
            <svg
              viewBox="0 0 10 8"
              width="16"
              height="13"
              fill="currentColor"
              shapeRendering="crispEdges"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M0 0h10v2H0zM0 3h10v2H0zM0 6h10v2H0z" />
            </svg>
          </button>
        </div>
        {menuOpen && (
          <div
            id={MENU_ID}
            className="absolute inset-x-0 top-full z-10 border-b border-white/10 bg-surface px-4 pb-3 sm:hidden"
          >
            <nav aria-label="Main" className="flex flex-col gap-1">
              {links}
            </nav>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={`${NAV_LINK} mt-1 flex items-center gap-2 text-slate`}
            >
              <GitHubIcon />
              GitHub
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          </div>
        )}
      </div>
      <div ref={onSettingsSlot} className="mx-auto max-w-3xl px-4 pb-2.5 empty:hidden" />
    </header>
  );
}
