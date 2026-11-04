import { describe as suite, expect, it } from "vitest";

import { NAME, ORIGIN, TITLE } from "../../src/brand.ts";
import { QUIZ_HOW_HEADING, QUIZ_HOW_STEPS, QUIZ_SOURCES_TEXT } from "../../src/quizAbout.ts";
import type { PageTopic } from "./bank.ts";
import {
  describe,
  escapeHtml,
  fileFor,
  jsonLdBlock,
  notFoundPage,
  pagesFor,
  renderPage,
  sitemap,
  topicPage,
} from "./render.ts";

// The tags of index.html that the prerender rewrites, as the build leaves them.
const SHELL = `<!doctype html>
<html lang="en">
  <head>
    <title>${TITLE}</title>
    <meta name="description" content="Site description." />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="${TITLE}" />
    <meta property="og:description" content="Site description." />
    <meta property="og:url" content="${ORIGIN}/" />
    <meta property="og:image" content="${ORIGIN}/og-v1.jpg" />
    <meta name="twitter:title" content="${TITLE}" />
    <meta name="twitter:description" content="Site description." />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/assets/index.js"></script>
  </body>
</html>`;

const TOPIC: PageTopic = {
  name: "Europa's hidden ocean",
  slug: "europas-hidden-ocean",
  explanation:
    "Europa is a moon of Jupiter. Under its ice lies a salty ocean.\n\nIt holds more water than Earth <b>combined</b>.",
  sources: [
    { url: "https://science.nasa.gov/europa", site: "science.nasa.gov", quote: "A \"salty\" sea & more" },
    { url: "javascript:alert(1)", site: "bad", quote: "never linked" },
  ],
};

function jsonLd(html: string): Record<string, unknown>[] {
  return [...html.matchAll(/<script type="application\/ld\+json">(.*?)<\/script>/g)].map(
    (found) => JSON.parse(found[1] ?? "{}") as Record<string, unknown>,
  );
}

suite("renderPage", () => {
  const html = renderPage(SHELL, topicPage(TOPIC));

  it("gives the page its own title, description, canonical link and preview tags", () => {
    const url = `${ORIGIN}/learn/europas-hidden-ocean`;
    expect(html).toContain(`<title>Europa's hidden ocean - ${NAME}</title>`);
    expect(html).toContain(`<link rel="canonical" href="${url}" />`);
    expect(html).toContain(`<meta property="og:url" content="${url}" />`);
    expect(html).toContain('<meta property="og:type" content="article" />');
    expect(html).toContain('<meta name="description" content="Europa is a moon of Jupiter.');
    expect(html).not.toContain("Site description.");
    expect(html).toContain(`${ORIGIN}/og-v1.jpg`);
  });

  it("puts the explanation and its sources in the page for a crawler", () => {
    expect(html).toContain("<h1>Europa's hidden ocean</h1>");
    expect(html).toContain("<p>Europa is a moon of Jupiter. Under its ice lies a salty ocean.</p>");
    expect(html).toContain('<a href="https://science.nasa.gov/europa" rel="noopener noreferrer">');
    expect(html).toContain("A &quot;salty&quot; sea &amp; more");
    expect(html).toContain('<script type="module" src="/assets/index.js"></script>');
  });

  it("escapes what the bank sends and never links a non-web address", () => {
    expect(html).toContain("&lt;b&gt;combined&lt;/b&gt;");
    expect(html).not.toContain("<b>");
    expect(html).not.toContain("javascript:");
  });

  it("adds no structured data to a topic page, as Google has no feature for it", () => {
    expect(jsonLd(html)).toEqual([]);
  });

  it("stops if the shell is not the one it expects", () => {
    expect(() => renderPage("<html></html>", topicPage(TOPIC))).toThrow(/shell/);
    expect(() => renderPage(SHELL.replace("og:url", "og:nope"), topicPage(TOPIC))).toThrow(/og:url/);
  });
});

suite("jsonLdBlock", () => {
  it("cannot be closed early by text in the data", () => {
    const block = jsonLdBlock({ name: "</script><script>alert(1)</script>" });
    expect(block.match(/<\/script>/g)).toHaveLength(1);
  });
});

suite("pagesFor", () => {
  it("builds the fixed pages with no topics, so a build with no bank access still works", () => {
    const pages = pagesFor([]);
    expect(pages.map((page) => page.path)).toEqual(["/", "/learn", "/quiz", "/explore"]);
    for (const page of pages) {
      const html = renderPage(SHELL, page);
      expect(html).toContain(`<link rel="canonical" href="${ORIGIN}${page.path}" />`);
    }
  });

  it("makes the quiz page say what the quiz is, its levels, run lengths and sources", () => {
    const quiz = renderPage(SHELL, pagesFor([TOPIC])[2]!);
    expect(quiz).toContain("<h1>Astronomy quiz</h1>");
    expect(quiz).toContain(`<h2>${QUIZ_HOW_HEADING}</h2>`);
    for (const step of QUIZ_HOW_STEPS) {
      expect(quiz).toContain(`<li>${step}</li>`);
    }
    expect(quiz).toContain(`<p>${QUIZ_SOURCES_TEXT}</p>`);
    expect(jsonLd(quiz)).toEqual([]);
  });

  it("adds a page per topic and lists each on the Learn page and in the sitemap", () => {
    const pages = pagesFor([TOPIC]);
    expect(pages.map((page) => page.path)).toContain("/learn/europas-hidden-ocean");
    const learn = renderPage(SHELL, pages[1]!);
    expect(learn).toContain('<a href="/learn/europas-hidden-ocean">');
    expect(sitemap(pages)).toContain(`<loc>${ORIGIN}/learn/europas-hidden-ocean</loc>`);
    expect(sitemap(pages)).toContain(`<loc>${ORIGIN}/</loc>`);
  });

  it("gives the home page a WebSite and no search action the site cannot answer", () => {
    const [home] = jsonLd(renderPage(SHELL, pagesFor([])[0]!));
    expect(home).toMatchObject({ "@type": "WebSite", name: NAME, url: `${ORIGIN}/` });
    expect(home).not.toHaveProperty("potentialAction");
  });
});

suite("describe", () => {
  it("keeps a short text whole and cuts a long one at a sentence or a word", () => {
    expect(describe("Short text.")).toBe("Short text.");
    const long = `${"Stars are hot. ".repeat(12)}and then it keeps going without a stop for a while`;
    expect(describe(long).length).toBeLessThanOrEqual(155);
    expect(describe(long).endsWith(".")).toBe(true);
    const run = "word ".repeat(60);
    expect(describe(run).endsWith("...")).toBe(true);
  });
});

suite("files and escaping", () => {
  it("maps an address to a file Vercel serves before its rewrites", () => {
    expect(fileFor("/")).toBe("index.html");
    expect(fileFor("/quiz")).toBe("quiz/index.html");
    expect(fileFor("/learn/black-holes")).toBe("learn/black-holes/index.html");
  });

  it("escapes the five characters that matter in HTML", () => {
    expect(escapeHtml(`<a href="x">&</a>`)).toBe("&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;");
  });
});

suite("notFoundPage", () => {
  const html = renderPage(SHELL, notFoundPage());

  it("has its own title and tells search engines not to index it", () => {
    expect(html).toContain("<title>Not found");
    expect(html).toContain('<meta name="robots" content="noindex" />');
  });

  it("has no canonical link and no address tag that points at the home page", () => {
    expect(html).not.toContain('rel="canonical"');
    expect(html).not.toContain('property="og:url"');
  });

  it("keeps the root element and the app's script, so the app mounts over it", () => {
    expect(html).toContain('<div id="root"><main>');
    expect(html).toContain('src="/assets/index.js"');
  });

  it("is not in the sitemap", () => {
    expect(sitemap(pagesFor([]))).not.toContain("404");
  });
});
