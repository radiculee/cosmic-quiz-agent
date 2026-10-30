/** The site's name and the words search engines and link previews show. One place, so the
 * wording changes in one line. index.html and the prerender read it too. */

export const NAME = "Curiosity";

/** The page title on the home page and in search results (placeholder until Vedant picks it). */
export const TITLE = "Curiosity: Astronomy Quiz on the Wonders Beyond Earth";

export const DESCRIPTION =
  "An astronomy quiz written by an AI agent that checks every answer against the pages it read.";

export const TAGLINE =
  "An AI agent reads NASA, ESA and Wikipedia, writes the questions, and checks every answer against the pages it read.";

/** The short visible line saying what the site is, for readers and crawlers. */
export const ASTRONOMY_LINE = "An astronomy and space quiz.";

/** The canonical origin, with no trailing slash. */
export const ORIGIN = "https://curiosity.vedantgaikwad.ie";

/** The tab title of an inner page. */
export function pageTitle(title: string | null): string {
  return title ? `${title} - ${NAME}` : TITLE;
}
