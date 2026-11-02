/** The site's name and the words search engines and link previews show. One place, so the
 * wording changes in one line. index.html and the prerender read it too. */

export const NAME = "Curiosity";

/** The page title on the home page and in search results. */
export const TITLE = "Astronomy Quiz: Test Your Space Knowledge - Curiosity";

export const DESCRIPTION =
  "An astronomy and space quiz written by an AI agent that checks every answer against the pages it read.";

export const TAGLINE =
  "An AI agent reads NASA, ESA and Wikipedia, writes the questions, and checks every answer against the pages it read.";

/** The short visible line saying what the site is, for readers and crawlers. */
export const ASTRONOMY_LINE = "An astronomy and space quiz.";

/** The canonical origin, with no trailing slash. */
export const ORIGIN = "https://curiosity.vedantgaikwad.ie";

/** The link preview, on the site's own domain (1200 x 630). Switch to /og-v2.jpg when it lands. */
export const SOCIAL_IMAGE = "/og-v1.jpg";

/** What the preview shows, for people who cannot see it. Change it with the image. */
export const SOCIAL_IMAGE_ALT =
  "COSMIC QUIZ and the tagline over a white observatory in a pink grass field under a navy sky";

export const THEME_COLOR = "#021a3d";

/** The tab title of an inner page. */
export function pageTitle(title: string | null): string {
  return title ? `${title} - ${NAME}` : TITLE;
}
