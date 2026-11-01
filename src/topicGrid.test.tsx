import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { TopicGrid } from "./components/TopicGrid";
import type { BankTopic, TopicImage } from "./types";

const IMAGE: TopicImage = {
  src: "/media/jupiter.jpg",
  width: 640,
  height: 360,
  credit: "Photo: Jane Q. Astronomer",
  licence: "CC BY-SA 4.0",
  licence_url: "https://creativecommons.org/licenses/by-sa/4.0/",
  page_url: "https://commons.wikimedia.org/wiki/File:Jupiter.jpg",
  source: "wikipedia",
};

function topic(name: string, extra: Partial<BankTopic> = {}): BankTopic {
  return { name, kind: "evergreen", learn: ["easy"], quiz: ["easy"], ...extra };
}

function render(topics: BankTopic[], learned: string[] = []): string {
  return renderToStaticMarkup(<TopicGrid topics={topics} learned={new Set(learned)} />);
}

function anchors(html: string): string[] {
  return [...html.matchAll(/<a [^>]*href="([^"]+)"/g)].map((match) => match[1] ?? "");
}

describe("TopicGrid", () => {
  it("shows the picture with its credit, the licence and the file page linked", () => {
    const html = render([topic("Jupiter", { image: IMAGE })]);
    expect(html).toContain('src="/media/jupiter.jpg"');
    expect(html).toContain("Photo: Jane Q. Astronomer");
    expect(anchors(html)).toEqual([
      "/learn/jupiter",
      "https://creativecommons.org/licenses/by-sa/4.0/",
      "https://commons.wikimedia.org/wiki/File:Jupiter.jpg",
    ]);
  });

  it("keeps the topic link first, so the tab order is title, licence, file page", () => {
    const html = render([topic("Jupiter", { image: IMAGE })]);
    expect(html.indexOf("data-title")).toBeLessThan(html.indexOf("creativecommons.org"));
  });

  it("names the licence without a link when it has no address", () => {
    const { licence_url: _unused, ...bare } = IMAGE;
    const html = render([topic("Mars", { image: bare })]);
    expect(html).toContain("CC BY-SA 4.0");
    expect(anchors(html)).toEqual(["/learn/mars", IMAGE.page_url]);
  });

  it("shows the fact and a glyph, and no credit, where there is no picture", () => {
    const html = render([
      topic("Quasar", { fact: { category: "galaxy", text: "Quasars outshine whole galaxies." } }),
    ]);
    expect(html).toContain("Quasars outshine whole galaxies.");
    expect(html).toContain("<svg");
    expect(anchors(html)).toEqual(["/learn/quasar"]);
  });

  it("shows only the name for a topic with neither", () => {
    const html = render([topic("Comet")]);
    expect(html).toContain("Comet");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<svg");
  });

  it("marks a topic already read, and only that one", () => {
    const html = render([topic("Jupiter"), topic("Mars")], ["Mars"]);
    expect(html.match(/>Read</g) ?? []).toHaveLength(1);
    expect(html.indexOf(">Read<")).toBeGreaterThan(html.indexOf("Jupiter"));
  });

  it("labels news and web topics", () => {
    const html = render([topic("Eclipse", { kind: "news" }), topic("Pulsar", { kind: "custom" })]);
    expect(html).toContain(">News<");
    expect(html).toContain(">Web<");
  });
});
