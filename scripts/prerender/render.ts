/**
 * Turns the built page shell (dist/index.html) into one static page per address: its own title,
 * description, canonical link, preview tags, structured data, and the text a crawler can read
 * (the explanation and its sources, for a topic). The React app mounts over that text in the
 * browser, as it did over the empty root. Pure functions, unit-tested (render.test.ts); the
 * file work is in scripts/prerender.mjs.
 */
import {
  ASTRONOMY_LINE,
  DESCRIPTION,
  NAME,
  ORIGIN,
  pageTitle,
  TAGLINE,
  TITLE,
} from "../../src/brand.ts";
import type { PageSource, PageTopic } from "./bank.ts";

export interface PageSpec {
  /** The address, "/" or "/learn/black-holes". */
  path: string;
  title: string;
  description: string;
  ogType: "website" | "article";
  /** What goes inside the app's root element. */
  body: string;
  /** Structured data, one script block each. */
  data: object[];
}

const ROOT_ELEMENT = '<div id="root"></div>';
const SITE = { "@type": "WebSite", name: NAME, url: `${ORIGIN}/` };

export function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/** Structured data as a script block. `<` is escaped so no text can close the block early. The
 * block is data, not code, so the page's script-src policy does not apply to it. */
export function jsonLdBlock(data: object): string {
  const json = JSON.stringify({ "@context": "https://schema.org", ...data }).replaceAll(
    "<",
    "\\u003c",
  );
  return `<script type="application/ld+json">${json}</script>`;
}

function setMeta(html: string, key: string, value: string): string {
  const tag = new RegExp(`(<meta (?:property|name)="${key}" content=")[^"]*(")`);
  if (!tag.test(html)) {
    throw new Error(`the page shell has no <meta> tag for ${key}`);
  }
  return html.replace(tag, (_all, open: string, close: string) => open + escapeHtml(value) + close);
}

/** The shell with this page's head and body. */
export function renderPage(shell: string, page: PageSpec): string {
  if (!shell.includes(ROOT_ELEMENT) || !shell.includes("<title>") || !shell.includes("</head>")) {
    throw new Error("the page shell is not the one the prerender expects");
  }
  const url = `${ORIGIN}${page.path}`;
  let html = shell.replace(
    /<title>[^<]*<\/title>/,
    () => `<title>${escapeHtml(page.title)}</title>`,
  );
  html = setMeta(html, "description", page.description);
  html = setMeta(html, "og:type", page.ogType);
  html = setMeta(html, "og:title", page.title);
  html = setMeta(html, "og:description", page.description);
  html = setMeta(html, "og:url", url);
  html = setMeta(html, "twitter:title", page.title);
  html = setMeta(html, "twitter:description", page.description);
  const head = [
    `<link rel="canonical" href="${escapeHtml(url)}" />`,
    ...page.data.map(jsonLdBlock),
  ].join("\n    ");
  html = html.replace("</head>", () => `  ${head}\n  </head>`);
  return html.replace(ROOT_ELEMENT, () => `<div id="root">${page.body}</div>`);
}

// --- Text -------------------------------------------------------------------------------------

/** About 155 characters of an explanation, cut at the end of a sentence or word, for a search
 * result's snippet. */
export function describe(explanation: string, limit = 155): string {
  const flat = explanation.split(/\s+/).join(" ").trim();
  if (flat.length <= limit) {
    return flat;
  }
  const window = flat.slice(0, limit);
  const sentence = Math.max(
    window.lastIndexOf(". "),
    window.lastIndexOf("? "),
    window.lastIndexOf("! "),
  );
  if (sentence >= limit * 0.5) {
    return window.slice(0, sentence + 1);
  }
  return `${window.slice(0, window.lastIndexOf(" ")).replace(/[ ,;:.-]+$/, "")}...`;
}

function paragraphs(text: string): string {
  return text
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => `<p>${escapeHtml(part)}</p>`)
    .join("");
}

function isWebAddress(url: string): boolean {
  try {
    return ["http:", "https:"].includes(new URL(url).protocol);
  } catch {
    return false;
  }
}

function sourceList(sources: readonly PageSource[]): string {
  const items = sources
    .filter((source) => isWebAddress(source.url))
    .map(
      (source) =>
        `<li><a href="${escapeHtml(source.url)}" rel="noopener noreferrer">${escapeHtml(source.site)}</a>` +
        `: &ldquo;${escapeHtml(source.quote)}&rdquo;</li>`,
    );
  return items.length ? `<h2>Sources</h2><ul>${items.join("")}</ul>` : "";
}

const NAV =
  '<nav aria-label="Ways in"><a href="/learn">Learn</a> <a href="/quiz">Quiz</a> <a href="/explore">Try a new topic</a></nav>';

// --- Pages ------------------------------------------------------------------------------------

export function topicPage(topic: PageTopic): PageSpec {
  const path = `/learn/${topic.slug}`;
  const description = describe(topic.explanation);
  return {
    path,
    title: pageTitle(topic.name),
    description,
    ogType: "article",
    body:
      `<main>${NAV}<p><a href="/learn">All topics</a></p><h1>${escapeHtml(topic.name)}</h1>` +
      `${paragraphs(topic.explanation)}${sourceList(topic.sources)}</main>`,
    data: [],
  };
}

function learnPage(topics: readonly PageTopic[]): PageSpec {
  const description =
    "Plain-language explanations of astronomy and space topics, each with the sources it was checked against.";
  const links = topics
    .map((topic) => `<li><a href="/learn/${topic.slug}">${escapeHtml(topic.name)}</a></li>`)
    .join("");
  return {
    path: "/learn",
    title: pageTitle("Learn astronomy and space topics"),
    description,
    ogType: "website",
    body:
      `<main>${NAV}<h1>Learn astronomy and space</h1><p>${escapeHtml(description)}</p>` +
      `${links ? `<ul>${links}</ul>` : ""}</main>`,
    data: [],
  };
}

function homePage(): PageSpec {
  return {
    path: "/",
    title: TITLE,
    description: DESCRIPTION,
    ogType: "website",
    body:
      `<main><h1>${escapeHtml(NAME)}</h1><p>${escapeHtml(ASTRONOMY_LINE)}</p>` +
      `<p>${escapeHtml(TAGLINE)}</p>${NAV}</main>`,
    data: [{ ...SITE, description: DESCRIPTION, inLanguage: "en" }],
  };
}

function quizPage(topicCount: number): PageSpec {
  const description =
    "Play an astronomy quiz of four-option questions against the clock, at easy, medium or hard. Every answer comes with an explanation and the sources it was checked against.";
  const covered = topicCount
    ? `<p>The question bank covers ${topicCount} astronomy and space topics, and each question is on a different topic.</p>`
    : "";
  return {
    path: "/quiz",
    title: pageTitle("Astronomy quiz against the clock"),
    description,
    ogType: "website",
    body:
      `<main>${NAV}<h1>Astronomy quiz</h1><p>${escapeHtml(description)}</p>` +
      `<h2>How the quiz works</h2><ul>` +
      `<li>Pick a difficulty: easy, medium or hard.</li>` +
      `<li>Pick a run of 10, 30 or 60 questions. A length is offered once the question bank has that many topics at your difficulty.</li>` +
      `<li>Every question has four options and is on a different topic, played against the clock.</li>` +
      `<li>After each answer you see the explanation and the sources it was checked against.</li>` +
      `</ul>${covered}` +
      `<h2>Where the questions come from</h2>` +
      `<p>An AI agent reads pages from sources such as NASA, ESA and Wikipedia and writes each question. ` +
      `A separate check must find a passage in those pages that supports the correct answer before the question is published.</p></main>`,
    data: [],
  };
}

function explorePage(): PageSpec {
  const description =
    "Type any astronomy or space topic and an AI agent researches it live from NASA, ESA and Wikipedia, then checks each answer against the pages it read.";
  return {
    path: "/explore",
    title: pageTitle("Try a new space topic"),
    description,
    ogType: "website",
    body: `<main>${NAV}<h1>Try a new topic</h1><p>${escapeHtml(description)}</p></main>`,
    data: [],
  };
}

/** Every page to build: the fixed ones, then one per topic. With no topics (no bank access at
 * build time) only the fixed pages are made, and a topic address is served by the app alone. */
export function pagesFor(topics: readonly PageTopic[]): PageSpec[] {
  return [homePage(), learnPage(topics), quizPage(topics.length), explorePage(), ...topics.map(topicPage)];
}

/** sitemap.xml for the pages. No dates: nothing here knows when a page last changed. */
export function sitemap(pages: readonly PageSpec[]): string {
  const urls = pages.map((page) => `  <url><loc>${escapeHtml(ORIGIN + page.path)}</loc></url>`);
  return (
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join("\n")}\n</urlset>\n`
  );
}

/** Where a page's file goes under dist/: "/" is index.html, "/quiz" is quiz/index.html. */
export function fileFor(path: string): string {
  return path === "/" ? "index.html" : `${path.replace(/^\/+/, "")}/index.html`;
}
