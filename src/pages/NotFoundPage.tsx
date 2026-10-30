import { useEffect } from "react";

import { Link } from "../components/Link";
import { knownPaths, redirectFor, suggestionsFor } from "../closeMatch";
import { navigate, PATHS, useLocation, usePageTitle } from "../router";
import type { BankTopic } from "../types";

/** Tells search engines this address is not a page, since the site answers every path with the
 * app (the status is 200). The tag is removed when the visitor moves on. */
function useNoIndex(): void {
  useEffect(() => {
    const tag = document.createElement("meta");
    tag.name = "robots";
    tag.content = "noindex";
    document.head.append(tag);
    return () => tag.remove();
  }, []);
}

/** Any address the app does not know. A near miss of a real page is taken to that page; anything
 * less sure is offered as a suggestion. Pass the bank's topics, once loaded, to include mistyped
 * topic addresses. */
export function NotFoundPage({ topics = [] }: { topics?: readonly BankTopic[] }) {
  usePageTitle("Not found");
  useNoIndex();
  const location = useLocation();
  const paths = knownPaths(topics);
  const redirect = redirectFor(location.pathname, paths);
  useEffect(() => {
    if (redirect) {
      navigate(redirect + location.search, { replace: true });
    }
  }, [redirect, location.search]);

  const suggestions = redirect ? [] : suggestionsFor(location.pathname, paths);
  return (
    <div className="flex flex-col items-center pt-16 text-center">
      <p className="on-scene-muted font-pixel text-[9px] uppercase">404</p>
      <h1 className="on-scene mt-4 font-heading text-4xl font-bold">Nothing at this address</h1>
      {suggestions.length > 0 && (
        <div className="on-scene mt-4">
          <p>Did you mean:</p>
          <ul className="mt-2 space-y-1">
            {suggestions.map((path) => (
              <li key={path}>
                <Link to={path} className="text-teal underline underline-offset-4 hover:text-ink">
                  {path}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="on-scene mt-4">
        <Link to={PATHS.home} className="text-teal underline underline-offset-4 hover:text-ink">
          Back to the start
        </Link>
      </p>
    </div>
  );
}
